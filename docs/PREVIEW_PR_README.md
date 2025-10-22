# Preview PR System - Documentation Index

This directory contains the complete documentation for the PR Preview System implementation in BlogManager.

---

## 📚 Documentation Files

### 1. `ISSUE_6_EVIDENCE.md` ✅ COMPLETED
**Purpose:** Evidence and verification of PreviewSession model implementation  
**Status:** Completed 2025-10-19  
**Contains:**
- Model definition verification
- Admin panel registration proof
- Migration status
- Functional tests output
- Database records verification

**Use this when:** You need to verify Issue #6 completion or reference the base model implementation.

---

### 2. `PREVIEW_PR_ROADMAP.md` 📋 REFERENCE
**Purpose:** Comprehensive technical specification and implementation guide  
**Status:** Living document  
**Contains:**
- Detailed breakdown of Issues #7-11
- Technical architecture decisions
- API endpoint specifications
- Webhook event mappings
- Testing strategy
- CI/CD integration notes
- Error handling patterns
- Performance targets

**Use this when:** 
- Planning implementation of specific issues
- Need detailed technical specs
- Designing API contracts
- Writing tests
- Troubleshooting integration issues

---

### 3. `PREVIEW_PR_ISSUES.md` 📊 TRACKER
**Purpose:** Quick reference issue tracker with progress monitoring  
**Status:** Updated as issues progress  
**Contains:**
- Issue summaries (#6-11)
- Acceptance criteria checklists
- Implementation checklists
- File modification lists
- Progress tracking table
- Implementation phases
- Testing plan

**Use this when:**
- Starting work on a new issue
- Checking what's left to implement
- Reviewing acceptance criteria
- Tracking overall progress
- Planning sprints

---

## 🎯 Quick Navigation

### I want to...

**Start implementing Issue #7 (Kickoff API)**
1. Read acceptance criteria in `PREVIEW_PR_ISSUES.md` → Issue #7
2. Check detailed specs in `PREVIEW_PR_ROADMAP.md` → Issue #7
3. Follow implementation checklist step-by-step
4. Reference existing patterns in `.github/copilot-instructions.md`

**Understand the webhook flow**
1. Read event mapping table in `PREVIEW_PR_ISSUES.md` → Issue #8
2. Study detailed handlers in `PREVIEW_PR_ROADMAP.md` → Issue #8
3. Review state machine diagram in roadmap

**Verify Issue #6 is complete**
1. Open `ISSUE_6_EVIDENCE.md`
2. Check all ✅ marks in Definition of Done section

**Track overall progress**
1. Open `PREVIEW_PR_ISSUES.md`
2. Check "Progress Tracker" table
3. Review implementation phases

---

## 🔄 Document Lifecycle

### When to Update

**`ISSUE_6_EVIDENCE.md`**
- ✅ Complete - No further updates needed
- Archive reference for model implementation

**`PREVIEW_PR_ROADMAP.md`**
- Update when technical decisions change
- Add lessons learned after issue completion
- Expand sections based on implementation discoveries
- Add troubleshooting patterns

**`PREVIEW_PR_ISSUES.md`**
- ✅ Check off items as completed
- Update progress percentages
- Add blockers or notes in status column
- Mark issues as DONE when all acceptance criteria met

---

## 📋 Implementation Workflow

### For Each Issue (#7-11)

1. **Planning Phase**
   ```
   Read: PREVIEW_PR_ISSUES.md → [Issue Section]
   Review: Acceptance Criteria
   Check: Dependencies satisfied
   ```

2. **Design Phase**
   ```
   Study: PREVIEW_PR_ROADMAP.md → [Detailed Specs]
   Review: Technical Infrastructure section
   Plan: File structure and modifications
   ```

3. **Implementation Phase**
   ```
   Follow: Implementation Checklist (PREVIEW_PR_ISSUES.md)
   Reference: Code patterns in existing files
   Test: As you build (TDD approach)
   ```

4. **Verification Phase**
   ```
   Check: All Acceptance Criteria ✅
   Run: Tests (unit + integration)
   Test: Manual verification checklist
   Update: Progress tracker
   ```

5. **Documentation Phase**
   ```
   Update: PREVIEW_PR_ISSUES.md progress
   Add: Lessons learned to ROADMAP.md
   Create: Evidence doc (like ISSUE_6_EVIDENCE.md)
   ```

---

## 🧪 Testing References

### Test Locations

**Unit Tests**
- `blog_manager/blog/tests/test_preview_api.py` - API endpoints
- `blog_manager/blog/tests/test_webhook_handlers.py` - Webhook processing
- `blog_manager/blog/tests/test_preview_service.py` - Business logic
- `blog_manager/blog/tests/test_frontmatter_validation.py` - Validation

**Integration Tests**
- `blog_manager/blog/tests/test_preview_workflow.py` - End-to-end flows

**Test Data**
- `blog_manager/blog/tests/fixtures/github_payloads.json` - Webhook samples

---

## 🔗 Related Files

### Project Configuration
- `.github/copilot-instructions.md` - Architecture and conventions
- `blog_manager/settings/` - Django settings (dev/prod)
- `.env.example` - Required environment variables

### Existing Code to Reference
- `blog_manager/blog/models.py` - PreviewSession model
- `blog_manager/blog/admin.py` - Admin configuration
- `blog_manager/blog/github_client.py` - GitHub API client
- `blog_manager/blog/exporter.py` - Export logic
- `blog_manager/blog/views.py` - Existing API endpoints

### CI/CD
- `.github/workflows/` - GitHub Actions workflows
- Look for `pr-preview.yml` or `pr-artifact.yml` patterns

---

## 💡 Tips for Implementation

### Best Practices

1. **Start Small**
   - Implement Issue #7 first (core functionality)
   - Get feedback before moving to #8
   - Iterate quickly

2. **Test Driven**
   - Write tests before implementation (TDD)
   - Use existing test patterns as templates
   - Mock external services (GitHub API)

3. **Reference Existing Code**
   - `SiteViewSet` for ViewSet patterns
   - `ExportAudit` for audit logging
   - `sync_repos` command for git operations

4. **Error Handling**
   - Use `FrontMatterValidationError` for validation
   - Log all external API calls
   - Return user-friendly error messages

5. **Performance**
   - Use `select_related()` for foreign keys
   - Add database indexes (already in model)
   - Cache GitHub API responses when possible

---

## 🚨 Common Pitfalls to Avoid

### From Existing Codebase Patterns

1. **Git Operations**
   - Always check if working copy exists before git commands
   - Use absolute paths (not relative)
   - Handle missing credentials gracefully

2. **GitHub API**
   - Rate limiting is real - implement backoff
   - Not all repos have webhooks configured
   - PR numbers are per-repo, not globally unique

3. **Front-Matter**
   - YAML parsing can fail silently
   - CRLF line endings cause issues
   - Categories must be validated before export

4. **Django Patterns**
   - Use transactions for multi-step operations
   - `auto_now` fields update on every save
   - Signals can cause unexpected side effects

---

## 📞 Getting Help

### If you're stuck...

1. **Check existing implementations**
   - Search codebase for similar patterns
   - Review `blog/exporter.py` for export logic
   - Study `blog/github_client.py` for API usage

2. **Review documentation**
   - Re-read relevant roadmap section
   - Check acceptance criteria
   - Review technical decisions

3. **Test incrementally**
   - Break problem into smaller pieces
   - Test each piece in isolation
   - Use Django shell for quick experiments

4. **Check logs**
   - Enable DEBUG logging
   - Review `reports/logs/` for sync operations
   - Use `ExportAudit` for operation history

---

## 🎯 Success Criteria

### You'll know you're done when...

**Issue #7 Complete:**
- ✅ Can kickoff preview via API
- ✅ PR appears on GitHub
- ✅ Working copy has preview branch

**Issue #8 Complete:**
- ✅ Webhooks update status automatically
- ✅ States transition correctly
- ✅ Preview URL captured

**Issue #9 Complete:**
- ✅ Can list/filter sessions
- ✅ Poll endpoint responds fast
- ✅ Pagination works

**Issue #10 Complete:**
- ✅ Button visible in Writer UI
- ✅ Preview URL displayed when ready
- ✅ Errors shown to user

**Issue #11 Complete:**
- ✅ Can close/merge PRs
- ✅ Cleanup removes old sessions
- ✅ Admin actions work

**System Complete:**
- ✅ End-to-end: button → PR → build → URL (< 3 min)
- ✅ All tests passing
- ✅ Documentation updated
- ✅ Production-ready

---

**Last Updated:** 2025-10-19  
**Status:** Issue #6 complete, ready for #7  
**Next Steps:** Begin implementation of Issue #7 (Kickoff API)
