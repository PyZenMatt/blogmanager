# Preview PR System - Issue Tracker

Quick reference for tracking implementation progress of the PR preview system.

---

## 🎯 Epic: PR Preview System for BlogManager

Enable writers to generate live preview URLs via automated Pull Requests with real-time build tracking.

---

## ✅ Issue #6 - PreviewSession Model

**Status:** ✅ COMPLETED (2025-10-19)  
**Evidence:** `docs/ISSUE_6_EVIDENCE.md`

Created `PreviewSession` model with:
- UUID tracking
- PR metadata (number, branches, URL)
- Status state machine
- Admin registration with filters
- Migration applied successfully

---

## 🟡 Issue #7 - API: Kickoff Preview Endpoint

**Status:** 📋 READY TO START  
**Priority:** HIGH  
**Depends on:** #6 ✅  
**Estimate:** 4-6h

### Goal
`POST /api/sites/{site_id}/preview/` creates preview session and opens PR.

### Acceptance Criteria
- [ ] Endpoint returns `{uuid, pr_number, preview_branch, status}` in <1s
- [ ] PR visible on GitHub with correct branches
- [ ] Exports posts to preview branch in working copy
- [ ] Front-matter validation catches invalid categories
- [ ] Error states in `last_error` field
- [ ] Unit tests for happy path + errors
- [ ] OpenAPI schema updated

### Implementation Checklist
- [ ] Create `PreviewSessionViewSet` in `views.py`
- [ ] Add `PreviewSessionSerializer` in `serializers.py`
- [ ] Create `services/preview_service.py` with kickoff logic
- [ ] Extend `GitHubClient` with `create_pull_request()` method
- [ ] Add front-matter validation (exactly 1 cluster)
- [ ] Register viewset in router
- [ ] Write unit tests
- [ ] Manual test: create PR and verify on GitHub

### Files
```
blog_manager/blog/
├── views.py                      # NEW: PreviewSessionViewSet
├── serializers.py                # NEW: PreviewSessionSerializer
├── services/preview_service.py   # NEW: kickoff_preview_session()
├── tests/test_preview_api.py     # NEW: API tests
└── github_client.py              # EXTEND: create_pull_request()
blog_manager/urls.py               # MODIFY: register viewset
```

---

## 🟡 Issue #8 - Webhook Handler for GitHub

**Status:** 📋 READY TO START  
**Priority:** HIGH  
**Depends on:** #7  
**Estimate:** 3-5h

### Goal
`POST /api/webhooks/github` receives events and updates `PreviewSession` states.

### Acceptance Criteria
- [ ] Webhook signature verification (HMAC-SHA256)
- [ ] State transitions: `created → pr_open → building → ready`
- [ ] Preview URL extracted from `deployment_status`
- [ ] Error logs captured in `last_error`
- [ ] Returns 200 to GitHub (prevents retries)
- [ ] Integration tests with mock payloads
- [ ] Idempotent handling (duplicate events OK)

### Event Mapping

| Event | Action | Status Update |
|-------|--------|---------------|
| `pull_request.opened` | Save PR number | `pr_open` |
| `workflow_run.queued` | Build starting | `building` |
| `workflow_run.completed` (success) | Build done | `ready` |
| `workflow_run.failure` | Build failed | `error` + logs |
| `deployment_status.success` | Preview deployed | `ready` + URL |
| `pull_request.closed` (merged) | PR merged | `merged` |
| `pull_request.closed` (!merged) | PR closed | `closed` |

### Implementation Checklist
- [ ] Create `GitHubWebhookView` in `views.py`
- [ ] Implement signature verification
- [ ] Create event handlers in `services/webhook_service.py`
- [ ] Extract preview URL from deployment payload
- [ ] Add webhook route to `urls.py`
- [ ] Create test fixtures with sample payloads
- [ ] Write integration tests
- [ ] Configure webhook in GitHub repo settings

### Files
```
blog_manager/blog/
├── views.py                           # NEW: GitHubWebhookView
├── services/webhook_service.py        # NEW: event handlers
└── tests/
    ├── test_webhook_handlers.py       # NEW: handler tests
    └── fixtures/github_payloads.json  # NEW: sample events
blog_manager/urls.py                   # MODIFY: add webhook route
```

### Environment Variables
```bash
GITHUB_WEBHOOK_SECRET=your_secret_here
```

---

## 🟡 Issue #9 - API: List & Status Endpoints

**Status:** 📋 READY TO START  
**Priority:** MEDIUM  
**Depends on:** #7  
**Estimate:** 2-3h

### Goal
Provide list and polling endpoints for preview sessions.

### Acceptance Criteria
- [ ] `GET /api/preview-sessions/` with filters (site, status)
- [ ] `GET /api/preview-sessions/{uuid}/status/` for lightweight polling
- [ ] Pagination (20 per page)
- [ ] Poll-friendly: minimal payload, fast response
- [ ] API tests for filters and pagination

### Implementation Checklist
- [ ] Configure filters in `api/filters.py`
- [ ] Add `@action` for status polling to ViewSet
- [ ] Test list with various filter combinations
- [ ] Verify pagination
- [ ] Document in OpenAPI schema

### Files
```
blog_manager/api/
└── filters.py                    # NEW: PreviewSessionFilter
blog_manager/blog/
├── views.py                      # MODIFY: add status action
└── tests/test_preview_api.py     # EXTEND: list/filter tests
```

---

## 🟡 Issue #10 - UI: Preview Button in Writer

**Status:** 📋 BLOCKED (needs #7, #9)  
**Priority:** MEDIUM  
**Estimate:** 3-4h

### Goal
Add "Preview PR" button in Writer UI with status polling and URL display.

### Acceptance Criteria
- [ ] Button visible in post editor
- [ ] Kickoff triggers on click
- [ ] Status polling (2s interval) until ready/error
- [ ] Preview URL displayed when ready
- [ ] Error messages from `last_error` shown
- [ ] Mobile-responsive UI
- [ ] Works with Writer authentication

### UI States
- **Idle:** "🔍 Generate Preview" (enabled)
- **Loading:** "Creating preview..." (spinner)
- **Building:** "Building preview..." (progress bar)
- **Ready:** "✅ Open Preview" (green link)
- **Error:** "❌ Preview failed: {error}" (red badge)

### Implementation Checklist
- [ ] Add preview button to post editor template
- [ ] Create `static/writer/js/preview.js` (client logic)
- [ ] Implement polling function (max 60 attempts)
- [ ] Add CSS for status badges
- [ ] Toast notifications for success/error
- [ ] Manual test: full flow from button to URL

### Files
```
blog_manager/writer/
├── templates/writer/post_new.html    # MODIFY: add button
├── static/writer/
│   ├── css/preview.css               # NEW: styles
│   └── js/preview.js                 # NEW: client logic
└── views.py                          # MODIFY: pass site_id
```

---

## 🟢 Issue #11 - Cleanup & Merge Operations

**Status:** 📋 NICE TO HAVE  
**Priority:** LOW  
**Depends on:** #7  
**Estimate:** 2-3h

### Goal
Provide endpoints and tools for closing/merging PRs and cleaning up old sessions.

### Acceptance Criteria
- [ ] `POST /api/preview-sessions/{uuid}/close/` closes PR + deletes branch
- [ ] `POST /api/preview-sessions/{uuid}/merge/` merges PR
- [ ] Management command: `cleanup_preview_sessions` (7+ days old)
- [ ] Admin batch actions: close/merge selected
- [ ] Error handling for already-closed PRs

### Implementation Checklist
- [ ] Add close/merge actions to ViewSet
- [ ] Extend `GitHubClient` with close/merge methods
- [ ] Create management command
- [ ] Add admin batch actions
- [ ] Write tests for edge cases
- [ ] Optional: Celery task for daily cleanup

### Files
```
blog_manager/blog/
├── views.py                                    # MODIFY: add actions
├── services/preview_service.py                 # EXTEND: cleanup logic
├── github_client.py                            # EXTEND: close/merge PR
├── admin.py                                    # MODIFY: batch actions
└── management/commands/
    └── cleanup_preview_sessions.py             # NEW: cleanup command
```

---

## 📊 Progress Tracker

| Issue | Status | Priority | Depends On | Estimate | Progress |
|-------|--------|----------|------------|----------|----------|
| #6 | ✅ Done | HIGH | - | - | 100% |
| #7 | 📋 Ready | HIGH | #6 | 4-6h | 0% |
| #8 | 📋 Ready | HIGH | #7 | 3-5h | 0% |
| #9 | 📋 Ready | MEDIUM | #7 | 2-3h | 0% |
| #10 | ⏸️ Blocked | MEDIUM | #7, #9 | 3-4h | 0% |
| #11 | 📋 Nice-to-have | LOW | #7 | 2-3h | 0% |

**Total estimated effort:** 14-20 hours  
**Critical path:** #6 → #7 → #8 → #9 → #10  
**Can parallelize:** #8 and #9 after #7 is 50% done

---

## 🚀 Implementation Phases

### Phase 1: Core API (Issues #6-7)
**Goal:** Create preview sessions and open PRs programmatically  
**Duration:** ~6h  
**Deliverable:** Working kickoff endpoint

### Phase 2: Automation (Issue #8)
**Goal:** Automatic status updates via webhooks  
**Duration:** ~4h  
**Deliverable:** End-to-end preview flow (kickoff → webhook → ready)

### Phase 3: Frontend Integration (Issues #9-10)
**Goal:** User-facing preview button with status tracking  
**Duration:** ~6h  
**Deliverable:** Writers can generate previews from UI

### Phase 4: Operations (Issue #11)
**Goal:** Cleanup and merge tools  
**Duration:** ~3h  
**Deliverable:** Admin tools for managing previews

---

## 🧪 Testing Plan

### Per Issue
- **#7:** Unit tests for kickoff, front-matter validation, git ops
- **#8:** Integration tests with mock GitHub payloads
- **#9:** API tests for filters and pagination
- **#10:** Manual UI testing + JS unit tests (optional)
- **#11:** Tests for cleanup edge cases

### End-to-End
Manual test checklist:
- [ ] Create preview from Writer UI
- [ ] Verify PR on GitHub
- [ ] Wait for build to complete
- [ ] Check preview URL is accessible
- [ ] Simulate build failure (verify error handling)
- [ ] Close preview (verify branch deleted)
- [ ] Merge preview (verify merge success)

---

## 📝 Notes

### Key Technical Decisions
1. **Branch naming:** `preview/pr-{uuid[:8]}` for uniqueness
2. **Path format:** `_posts/<cluster>/<subcluster?>/YYYY-MM-DD-<slug>.md`
3. **Front-matter rule:** Exactly 1 cluster required (validated at export)
4. **Polling interval:** 2s until terminal state (ready/error/merged/closed)

### Dependencies
- `GITHUB_TOKEN` or `GIT_TOKEN` (already in use)
- `BLOG_REPO_BASE` or `Site.repo_path` configured
- GitHub webhook secret for signature verification
- Existing CI workflows for PR builds (`.github/workflows/pr-preview.yml`)

### Future Enhancements
- Real-time updates via WebSockets (replace polling)
- Preview comments posted to PR automatically
- Screenshot capture of preview site
- Multi-post preview bundles
- Preview expiration with auto-cleanup

---

**Last Updated:** 2025-10-19  
**Next Action:** Start Issue #7 (Kickoff API)  
**Documentation:** See `PREVIEW_PR_ROADMAP.md` for detailed specs
