# Preview PR System - Implementation Roadmap

**Status:** 🟢 Issue #6 Completed - Model Ready  
**Next:** Micro-issues for full PR preview workflow  
**Updated:** 2025-10-19

---

## 🎯 Vision

Enable writers to generate **live preview URLs** for posts via automated Pull Requests, with real-time build status tracking and seamless UI integration.

---

## ✅ Completed: Issue #6 - PreviewSession Model

**Status:** ✅ DONE (2025-10-19)

- ✅ `PreviewSession` model created with all required fields
- ✅ Admin panel registration with filters
- ✅ Migration applied successfully
- ✅ Functional verification completed

**Evidence:** See `docs/ISSUE_6_EVIDENCE.md`

---

## 📋 Micro-Issues Breakdown

### 🔧 Issue #7 - API: Kickoff Preview Endpoint

**Priority:** HIGH  
**Depends on:** Issue #6 ✅  
**Estimated effort:** 4-6h

#### Goal
Implement `POST /api/sites/{site_id}/preview/` endpoint to create preview sessions and open PRs.

#### Tasks

1. **Create ViewSet for PreviewSession**
   - File: `blog_manager/blog/views.py`
   - Add `PreviewSessionViewSet(viewsets.ModelViewSet)`
   - Register in `blog_manager/urls.py` router

2. **Implement Kickoff Action**
   - Custom action: `@action(methods=['post'], detail=True) def kickoff(request, pk)`
   - Steps:
     a. Create `PreviewSession(status="created", site_id=pk)`
     b. Calculate `preview_branch = f"preview/pr-{uuid[:8]}"`
     c. Set `source_branch = site.default_branch`
     d. Export selected posts to working copy (`Site.repo_path` or `BLOG_REPO_BASE/<slug>`)
     e. Git commit on `preview_branch`
     f. Call `GitHubClient.create_pull_request()` → save `pr_number`
     g. Update `status="pr_open"`

3. **Serializer**
   - File: `blog_manager/blog/serializers.py`
   - Create `PreviewSessionSerializer` with fields: `uuid`, `pr_number`, `preview_branch`, `status`, `preview_url`, `last_error`, `created_at`, `updated_at`

4. **Error Handling**
   - Catch `FrontMatterValidationError` → set `status="error"`, `last_error`
   - Validate front-matter: exactly 1 cluster required
   - Path format: `_posts/<cluster>/<subcluster?>/YYYY-MM-DD-<slug>.md`

5. **Service Layer**
   - File: `blog_manager/blog/services/preview_service.py`
   - Function: `kickoff_preview_session(site, post_ids=None)`
   - Extract business logic from view

#### DoD

- ✅ Endpoint returns `{uuid, pr_number, preview_branch, status}` in <1s
- ✅ PR visible on GitHub with correct base/head branches
- ✅ Working copy has new branch with exported content
- ✅ Error states captured in `last_error` field
- ✅ Unit tests for happy path + error cases
- ✅ API documented in OpenAPI schema (drf-spectacular)

#### Files to Create/Modify

```
blog_manager/blog/
├── views.py              # Add PreviewSessionViewSet
├── serializers.py        # Add PreviewSessionSerializer
├── services/
│   └── preview_service.py  # NEW - kickoff logic
└── tests/
    └── test_preview_api.py  # NEW - API tests
blog_manager/urls.py       # Register viewset
```

---

### 🔧 Issue #8 - Webhook Handler for GitHub Events

**Priority:** HIGH  
**Depends on:** Issue #7  
**Estimated effort:** 3-5h

#### Goal
Implement `POST /api/webhooks/github` to receive GitHub events and update `PreviewSession` states.

#### Tasks

1. **Create Webhook Endpoint**
   - File: `blog_manager/blog/views.py`
   - View: `GitHubWebhookView(APIView)`
   - Verify webhook signature (HMAC-SHA256 with `GITHUB_WEBHOOK_SECRET`)

2. **Event Handlers**
   - Map GitHub events to status updates:

   | GitHub Event | Condition | PreviewSession Update |
   |--------------|-----------|----------------------|
   | `pull_request` | opened | `status="pr_open"` |
   | `pull_request` | closed & merged | `status="merged"` |
   | `pull_request` | closed & !merged | `status="closed"` |
   | `workflow_run` | queued/in_progress | `status="building"` |
   | `workflow_run` | completed & success | `status="ready"` |
   | `workflow_run` | failure/cancelled | `status="error"` + extract logs |
   | `deployment_status` | success | `status="ready"` + `preview_url` from env |

3. **PreviewSession Lookup**
   - Match via `pr_number` from webhook payload
   - Handle case where session doesn't exist (log warning, return 200)

4. **Extract Preview URL**
   - From `deployment_status.environment_url`
   - Or parse from workflow output/artifacts
   - Fallback pattern: `https://<org>.github.io/<repo>/pr-preview/pr-{pr_number}/`

5. **Logging & Audit**
   - Log every webhook received with event type and pr_number
   - Store raw payload in `ExportAudit` for debugging

#### DoD

- ✅ Webhook signature verification passes
- ✅ State transitions: `created → pr_open → building → ready`
- ✅ Preview URL extracted and saved
- ✅ Error states captured with logs in `last_error`
- ✅ 200 response to GitHub (prevent retries)
- ✅ Integration test with mock GitHub payloads
- ✅ Idempotent: duplicate events don't break state

#### Files to Create/Modify

```
blog_manager/blog/
├── views.py                    # Add GitHubWebhookView
├── services/
│   └── webhook_service.py      # NEW - event handlers
└── tests/
    ├── test_webhook_handlers.py  # NEW - handler tests
    └── fixtures/
        └── github_payloads.json  # Sample webhook payloads
blog_manager/urls.py             # Add webhook route
```

#### Environment Variables

```bash
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
```

---

### 🔧 Issue #9 - API Endpoints: List & Tail

**Priority:** MEDIUM  
**Depends on:** Issue #7  
**Estimated effort:** 2-3h

#### Goal
Provide API endpoints for listing preview sessions and polling status updates.

#### Tasks

1. **List Endpoint**
   - Route: `GET /api/preview-sessions/`
   - Filters: `?site=<id>`, `?status=<status>`, `?status__ne=closed`
   - Ordering: `-updated_at`
   - Pagination: 20 per page
   - Already available via ViewSet (just configure filters)

2. **Detail Endpoint**
   - Route: `GET /api/preview-sessions/{uuid}/`
   - Returns full session details
   - Include related `site` data

3. **Tail/Status Endpoint**
   - Route: `GET /api/preview-sessions/{uuid}/status/`
   - Custom action for lightweight polling
   - Returns: `{status, preview_url, last_error, updated_at}`
   - Use case: frontend polls every 2s until `status in ['ready', 'error', 'merged', 'closed']`

4. **Filters Configuration**
   - File: `blog_manager/api/filters.py`
   - Add `PreviewSessionFilter` with `site`, `status`, `pr_number`

#### DoD

- ✅ List endpoint returns sessions with filters
- ✅ Status endpoint suitable for polling (minimal payload)
- ✅ Frontend can poll without fetching full session data
- ✅ Pagination works correctly
- ✅ API tests for all endpoints

#### Files to Create/Modify

```
blog_manager/blog/
├── views.py              # Add status action to ViewSet
└── tests/
    └── test_preview_api.py  # Add list/filter tests
blog_manager/api/
└── filters.py            # Add PreviewSessionFilter
```

---

### 🔧 Issue #10 - UI Integration: Preview Button in Writer

**Priority:** MEDIUM  
**Depends on:** Issue #7, #9  
**Estimated effort:** 3-4h

#### Goal
Add "Preview PR" button in Writer UI that kicks off preview and displays URL when ready.

#### Tasks

1. **Add Button to Post Editor**
   - File: `blog_manager/writer/templates/writer/post_new.html` (or equivalent)
   - Button: "🔍 Generate Preview" (disabled if post has validation errors)

2. **JavaScript Client**
   - File: `blog_manager/writer/static/writer/js/preview.js` (NEW)
   - Functions:
     - `kickoffPreview(siteId, postIds)` - Call kickoff endpoint
     - `pollPreviewStatus(uuid)` - Poll status every 2s
     - `displayPreviewUrl(url)` - Show link when ready
     - `handlePreviewError(error)` - Display error message

3. **UI States**
   - **Idle:** Button enabled "Generate Preview"
   - **Loading:** Button disabled, spinner "Creating preview..."
   - **Building:** Progress indicator "Building preview (30s-2m)..."
   - **Ready:** Green badge + "Open Preview" link
   - **Error:** Red badge + error message from `last_error`

4. **Polling Logic**
   - Start polling after kickoff success
   - Poll `GET /api/preview-sessions/{uuid}/status/` every 2s
   - Stop when `status in ['ready', 'error', 'merged', 'closed']`
   - Max 60 attempts (2 minutes timeout)

5. **Toast Notifications**
   - Success: "Preview ready! Click to open"
   - Error: "Preview failed: {last_error}"

#### DoD

- ✅ Button visible in post editor
- ✅ Kickoff triggers and polling starts
- ✅ Preview URL displayed when ready
- ✅ Error messages shown to user
- ✅ Works with existing writer authentication
- ✅ Mobile-responsive UI

#### Files to Create/Modify

```
blog_manager/writer/
├── templates/writer/
│   └── post_new.html         # Add preview button
├── static/writer/
│   ├── css/
│   │   └── preview.css       # NEW - preview UI styles
│   └── js/
│       └── preview.js        # NEW - preview client logic
└── views.py                  # Pass site_id to template context
```

---

### 🔧 Issue #11 - Cleanup & Merge Operations

**Priority:** LOW  
**Depends on:** Issue #7  
**Estimated effort:** 2-3h

#### Goal
Provide endpoints to close/merge PRs and clean up preview branches.

#### Tasks

1. **Close Preview Endpoint**
   - Route: `POST /api/preview-sessions/{uuid}/close/`
   - Actions:
     - Call `GitHubClient.close_pull_request(pr_number)`
     - Delete remote branch `preview_branch`
     - Update `status="closed"`
     - Clean up local working copy branch

2. **Merge Preview Endpoint**
   - Route: `POST /api/preview-sessions/{uuid}/merge/`
   - Actions:
     - Call `GitHubClient.merge_pull_request(pr_number)`
     - Update `status="merged"`
     - Optionally delete branch after merge

3. **Auto-Cleanup Service**
   - Management command: `python manage.py cleanup_preview_sessions`
   - Delete sessions older than 7 days with `status in ['merged', 'closed']`
   - Celery task (optional): run daily

4. **Batch Operations in Admin**
   - Admin action: "Close selected previews"
   - Admin action: "Merge selected previews"

#### DoD

- ✅ Close endpoint closes PR and deletes branch
- ✅ Merge endpoint merges PR successfully
- ✅ Cleanup command removes old sessions
- ✅ Admin actions work on bulk selections
- ✅ Error handling for already-closed PRs

#### Files to Create/Modify

```
blog_manager/blog/
├── views.py                  # Add close/merge actions
├── services/
│   └── preview_service.py    # Add cleanup logic
├── management/
│   └── commands/
│       └── cleanup_preview_sessions.py  # NEW
└── admin.py                  # Add batch actions
```

---

## 🛠 Technical Infrastructure

### GitHubClient Extensions

Add methods to `blog_manager/blog/github_client.py`:

```python
class GitHubClient:
    def create_pull_request(
        self, 
        owner: str, 
        repo: str, 
        title: str, 
        head: str, 
        base: str, 
        body: str = ""
    ) -> dict:
        """Create PR and return {number, html_url}"""
        
    def close_pull_request(
        self, 
        owner: str, 
        repo: str, 
        pr_number: int
    ) -> dict:
        """Close PR"""
        
    def merge_pull_request(
        self, 
        owner: str, 
        repo: str, 
        pr_number: int,
        merge_method: str = "squash"
    ) -> dict:
        """Merge PR"""
```

### Export Service Extensions

Add to `blog_manager/blog/services/preview_service.py`:

```python
def export_posts_to_preview_branch(
    site: Site,
    post_ids: List[int],
    branch_name: str
) -> ExportResult:
    """
    Export posts to preview branch in working copy.
    
    Returns:
        ExportResult with commit_sha, files_changed
    
    Raises:
        FrontMatterValidationError: if categories invalid
        GitOperationError: if git operations fail
    """
```

### Front-Matter Validation

Add to `blog_manager/blog/utils.py`:

```python
class FrontMatterValidationError(Exception):
    """Raised when front-matter is invalid"""
    
def validate_post_frontmatter(post: Post) -> None:
    """
    Validate post front-matter for export.
    
    Rules:
    - Exactly 1 cluster in categories
    - Valid YAML syntax
    - No CRLF line endings
    
    Raises:
        FrontMatterValidationError with descriptive message
    """
```

---

## 🧪 Testing Strategy

### Unit Tests

- `test_preview_api.py` - API endpoints (kickoff, list, status, close, merge)
- `test_webhook_handlers.py` - GitHub webhook event processing
- `test_preview_service.py` - Business logic for preview creation
- `test_frontmatter_validation.py` - Validation rules

### Integration Tests

- `test_preview_workflow.py` - End-to-end: kickoff → webhook → ready
- Mock GitHub API responses
- Test with real git operations in temporary repos

### Manual Testing Checklist

- [ ] Kickoff creates PR on GitHub
- [ ] PR build triggers via existing CI workflows
- [ ] Webhook updates status correctly
- [ ] Preview URL is accessible
- [ ] Error states display in UI
- [ ] Close/merge operations work
- [ ] Admin panel shows sessions correctly

---

## 📊 CI/CD Integration

### Existing Workflows to Leverage

**File:** `.github/workflows/pr-preview.yml` (if exists)

Expected behavior:
1. Triggered on PR open/sync to `preview/*` branches
2. Build Jekyll site
3. Deploy to GitHub Pages or Netlify
4. Comment on PR with preview URL
5. Send deployment_status webhook

### Webhook Configuration

**GitHub Repository Settings → Webhooks**

- Payload URL: `https://your-domain.com/api/webhooks/github`
- Content type: `application/json`
- Secret: `GITHUB_WEBHOOK_SECRET`
- Events:
  - [x] Pull requests
  - [x] Workflow runs
  - [x] Deployment statuses

---

## 🔐 Environment Variables

### Required

```bash
# GitHub Integration
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_WEBHOOK_SECRET=your_secret_here

# Repository
BLOG_REPO_BASE=/path/to/repos
BLOG_EXPORT_GIT_BRANCH=main

# Optional: Custom preview URL pattern
PREVIEW_URL_TEMPLATE=https://{org}.github.io/{repo}/pr-preview/pr-{pr_number}/
```

### Site Model Configuration

Each `Site` must have:
- `repo_owner` - GitHub org/user
- `repo_name` - Repository name
- `repo_path` - Local working copy path (or use BLOG_REPO_BASE fallback)
- `default_branch` - Base branch for PRs (usually `main`)

---

## 📈 Success Metrics

### Performance Targets

- Kickoff response: <1s
- PR creation: <5s
- Build completion: 30s-2m (depends on Jekyll build)
- Total preview time: <3m from kickoff to URL ready

### User Experience

- Writer sees progress updates every 2s
- Clear error messages for common failures:
  - Invalid front-matter
  - GitHub API rate limits
  - Build failures
  - Network errors

---

## 🚨 Error Handling

### Common Failure Scenarios

1. **Invalid Front-Matter**
   - Detection: Validation before export
   - Recovery: Show specific YAML error + line number
   - Status: `error` + `last_error = "Invalid YAML: ..."`

2. **GitHub API Rate Limit**
   - Detection: HTTP 429 from GitHub
   - Recovery: Retry with exponential backoff
   - Status: `error` + `last_error = "Rate limited, retry in Xs"`

3. **Build Failure**
   - Detection: Webhook `workflow_run.conclusion=failure`
   - Recovery: Link to GitHub Actions logs
   - Status: `error` + `last_error = "Build failed: {url}"`

4. **Network Timeout**
   - Detection: Webhook not received in 5 minutes
   - Recovery: Fallback polling of GitHub API
   - Status: Keep `building`, add warning in UI

---

## 📚 Documentation

### API Documentation

Auto-generated via `drf-spectacular`:
- Kickoff: `POST /api/sites/{id}/preview/`
- List: `GET /api/preview-sessions/`
- Status: `GET /api/preview-sessions/{uuid}/status/`
- Close: `POST /api/preview-sessions/{uuid}/close/`
- Merge: `POST /api/preview-sessions/{uuid}/merge/`

### User Guide

**File:** `docs/USER_GUIDE_PREVIEW.md` (create in Issue #10)

Topics:
- How to generate a preview
- Interpreting status badges
- Troubleshooting common errors
- Merging vs closing previews

---

## 🎯 Implementation Order

**Recommended sequence:**

1. ✅ **Issue #6** - Model (DONE)
2. 🟡 **Issue #7** - Kickoff API (NEXT - Core functionality)
3. 🟡 **Issue #8** - Webhooks (High priority for automation)
4. 🟡 **Issue #9** - List/Tail API (Needed for UI)
5. 🟡 **Issue #10** - UI Integration (User-facing)
6. 🟢 **Issue #11** - Cleanup (Nice-to-have)

**Parallel tracks:**
- Issues #7 and #8 can be developed in parallel
- Issue #9 can start after #7 is 50% done
- Issue #10 requires #7 and #9 complete

---

## 📝 Notes & Decisions

### Path Format Decision

Export path pattern: `_posts/<cluster>/<subcluster?>/YYYY-MM-DD-<slug>.md`

**Rationale:**
- Consistent with existing routing conventions
- Enforces exactly 1 cluster per post (front-matter validation)
- Subcluster is optional but encouraged for organization

### Branch Naming Convention

Pattern: `preview/pr-{uuid[:8]}`

**Rationale:**
- Short UUID (8 chars) is collision-resistant for reasonable scale
- Prefix `preview/` allows GitHub branch protection rules
- Matches with potential CI workflow triggers

### Status State Machine

```
created → pr_open → building → ready
                ↓       ↓         ↓
              error   error     merged/closed
```

**Terminal states:** `ready`, `error`, `merged`, `closed`  
**Poll until:** status in terminal states

---

## 🔗 Related Documentation

- `docs/ISSUE_6_EVIDENCE.md` - PreviewSession model implementation
- `.github/copilot-instructions.md` - Project architecture guide
- `blog_manager/blog/exporter.py` - Existing export logic
- `blog_manager/blog/github_client.py` - GitHub API client

---

**Last Updated:** 2025-10-19 19:30 UTC  
**Status:** 🟢 Ready for Issue #7 implementation  
**Maintainer:** PyZenMatt
