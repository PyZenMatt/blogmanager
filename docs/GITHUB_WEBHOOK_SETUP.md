# GitHub Webhook Integration for Preview Sessions

This document describes how to configure GitHub webhooks to automatically update PreviewSession statuses based on GitHub events.

## Overview

The webhook endpoint receives events from GitHub and updates `PreviewSession` records in the database. This enables automatic status transitions throughout the preview lifecycle without manual intervention.

## Webhook URL

```
POST https://your-domain.com/api/blog/webhooks/github/
```

**Local development:**
```
POST http://localhost:8000/api/blog/webhooks/github/
```

For local testing with real GitHub webhooks, use a tunnel service like:
- [ngrok](https://ngrok.com/): `ngrok http 8000`
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/): `cloudflared tunnel --url http://localhost:8000`

## Configuration

### 1. Generate Webhook Secret

Generate a secure random secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Add to Environment

Add the secret to your `.env` file:

```bash
GITHUB_WEBHOOK_SECRET=your-generated-secret-here
```

### 3. Configure GitHub Webhook

In your GitHub repository settings:

1. Go to **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**: `https://your-domain.com/api/blog/webhooks/github/`
3. **Content type**: `application/json`
4. **Secret**: Paste your `GITHUB_WEBHOOK_SECRET`
5. **Events**: Select individual events:
   - ✅ Pull requests
   - ✅ Deployment statuses
6. **Active**: ✅ Checked
7. Click **Add webhook**

## Supported Events

### `pull_request`

Updates PreviewSession status based on PR lifecycle:

| GitHub Action | PreviewSession Status | Description |
|---------------|----------------------|-------------|
| `opened` | `pr_open` | PR was created |
| `reopened` | `pr_open` | PR was reopened after being closed |
| `closed` (not merged) | `closed` | PR was closed without merging |
| `closed` (merged) | `merged` | PR was merged into base branch |

**Example payload** (abbreviated):
```json
{
  "action": "opened",
  "number": 42,
  "pull_request": {
    "number": 42,
    "state": "open",
    "merged": false,
    "html_url": "https://github.com/owner/repo/pull/42"
  }
}
```

**Correlation**: Matches `PreviewSession.pr_number` to `pull_request.number`

### `deployment_status`

Updates PreviewSession when deployment completes:

| GitHub State | PreviewSession Status | Updates |
|--------------|----------------------|---------|
| `success` | `ready` | Sets `preview_url` from `deployment_status.environment_url` |

**Example payload** (abbreviated):
```json
{
  "deployment_status": {
    "state": "success",
    "environment_url": "https://preview-pr-42.netlify.app"
  },
  "deployment": {
    "ref": "refs/pull/42/head",
    "environment": "Preview"
  }
}
```

**Correlation**: 
1. Tries to extract PR number from `deployment.ref` (format: `refs/pull/42/head`)
2. Falls back to matching `PreviewSession.preview_branch` with `deployment.ref`

## Signature Validation

All webhook requests are validated using HMAC-SHA256:

1. GitHub computes: `HMAC-SHA256(payload, GITHUB_WEBHOOK_SECRET)`
2. Sends signature in header: `X-Hub-Signature-256: sha256=<hash>`
3. BlogManager verifies signature before processing

**Security**: If `GITHUB_WEBHOOK_SECRET` is set, requests without valid signatures are rejected with `400 Bad Request`.

## Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `200 OK` | Processed | Event was handled and session updated |
| `204 No Content` | Ignored | Event type not relevant or no matching session |
| `400 Bad Request` | Invalid | Signature verification failed or malformed JSON |

**Example 200 response:**
```json
{
  "status": "processed",
  "event": "pull_request",
  "session": {
    "uuid": "abc-123-def",
    "status": "pr_open",
    "pr_number": 42,
    "preview_url": "https://preview-pr-42.netlify.app"
  }
}
```

## Testing Webhooks

### Manual Testing with curl

Generate a test signature:

```python
import hmac
import hashlib
import json

secret = "your-webhook-secret"
payload = {"action": "opened", "pull_request": {"number": 42}}
payload_str = json.dumps(payload)

signature = hmac.new(
    secret.encode('utf-8'),
    payload_str.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"sha256={signature}")
```

Send test request:

```bash
curl -X POST http://localhost:8000/api/blog/webhooks/github/ \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=YOUR_SIGNATURE" \
  -d '{"action":"opened","pull_request":{"number":42}}'
```

### Automated Tests

Run the test suite:

```bash
pytest blog/tests/test_webhook.py -v
```

Tests cover:
- ✅ pull_request events (opened, closed, merged)
- ✅ deployment_status.success
- ✅ Signature validation (valid, invalid, missing)
- ✅ Unknown event types
- ✅ PR events for non-preview PRs
- ✅ Invalid JSON payloads

## GitHub Actions Integration

Example workflow to trigger deployment status:

```yaml
name: Deploy Preview

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to Netlify
        id: netlify
        uses: netlify/actions/cli@master
        with:
          args: deploy --dir=_site --prod=false
        env:
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
      
      - name: Create deployment status
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.repos.createDeploymentStatus({
              owner: context.repo.owner,
              repo: context.repo.repo,
              deployment_id: context.payload.deployment.id,
              state: 'success',
              environment_url: '${{ steps.netlify.outputs.deploy-url }}',
            });
```

## Monitoring & Debugging

### Check Webhook Deliveries

In GitHub repo settings → Webhooks → Recent Deliveries:
- View request/response for each delivery
- Redeliver failed webhooks
- Check response codes and timing

### Application Logs

Webhook events are logged at various levels:

```python
# Info: Successful status transitions
logger.info(f"Preview session {uuid} status: {old} → {new}")

# Warning: Signature failures
logger.warning("GitHub webhook signature verification failed")

# Debug: Ignored events
logger.debug(f"Ignoring pull_request action '{action}'")
```

### Common Issues

**400 Bad Request - Invalid signature**
- Verify `GITHUB_WEBHOOK_SECRET` matches GitHub settings
- Check secret doesn't have trailing whitespace
- Ensure Content-Type is `application/json`

**204 No Content - Event ignored**
- PR number doesn't match any PreviewSession
- Event type not supported (e.g., `issues`, `push`)
- Deployment ref doesn't match any preview branch

**No status update**
- Check webhook was delivered (GitHub UI)
- Verify PreviewSession exists with matching `pr_number`
- Check application logs for errors

## Required GitHub Permissions

If using a GitHub App instead of webhooks:

**Repository permissions:**
- Pull requests: Read & Write
- Deployments: Read

**Subscribe to events:**
- Pull request
- Deployment status

## Security Considerations

1. **Always set GITHUB_WEBHOOK_SECRET** in production
2. Use HTTPS for webhook URL (required by GitHub in production)
3. Rotate webhook secret periodically
4. Monitor failed signature validations (possible attack)
5. Rate limit webhook endpoint if needed (DRF throttling)

## See Also

- [GitHub Webhooks Documentation](https://docs.github.com/webhooks)
- [Securing Webhooks](https://docs.github.com/webhooks/using-webhooks/validating-webhook-deliveries)
- [PreviewSession Model](../blog_manager/blog/models.py)
- [Webhook Handler Code](../blog_manager/blog/webhook_handlers.py)
- [Webhook Tests](../blog_manager/blog/tests/test_webhook.py)
