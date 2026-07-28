# Report 2: Repository Review & Setup Clarification
## Format: Product Requirements Document (Build)

**Date:** 2026-06-05  
**Test User Profile:** Novice beta user with API key, no prior MCP experience  
**Test Scenario:** Initial documentation review and setup readiness assessment  
**Status:** BLOCKED — 5 critical clarifications needed before setup attempt

---

## Executive Summary

After reviewing the GitHub repository documentation, novice user identified strong value proposition and feature set, but encountered 5 blocking questions about the setup process and configuration. These questions represent gaps between current documentation and novice user mental models.

**Impact:** Setup cannot proceed without answers. Affects all new users without MCP background knowledge.

---

## Clarification Questions (Critical Path)

### Q1: API Key Acquisition Timing
**Question:** When should the user obtain their API key relative to pip install?

**Current State:** Documentation says "Free API key from memoryintelligence.io/portal" but doesn't specify:
- Should user create account BEFORE running pip install?
- Should user create account BEFORE running mi-mcp setup?
- Does mi-mcp setup prompt for account creation if not already done?
- Can user complete all steps and get key at the end?

**Impact:** Novice user doesn't know optimal sequence, risks wasting time on install if account isn't ready.

**Requirement:** Clarify in setup documentation:
```
Setup sequence:
1. [Create account at memoryintelligence.io/portal] — required first
2. [Run pip install memoryintelligence-mcp]
3. [Run mi-mcp setup with API key ready]
```

**Acceptance Criteria:**
- [ ] Documentation explicitly states when account creation is needed
- [ ] mi-mcp setup includes link to account creation if key not provided
- [ ] Error message is helpful if user skips account creation step

---

### Q2: Host Selection & Auto-Detection
**Question:** How does setup handle multiple possible hosts (Claude Desktop, Claude Code, Cursor)?

**Current State:** Documentation mentions integration with "Claude Desktop, Claude Code, and Cursor" but doesn't explain:
- How does user specify which host they're using?
- Is it auto-detected?
- Is there user input required?
- What if wrong host is detected?
- Does each host need different setup steps?

**Impact:** Novice user doesn't know if setup is automatic or requires manual host selection.

**Requirement:** Clarify host detection/selection in setup flow:

**Acceptance Criteria:**
- [ ] Setup auto-detects installed hosts (if possible)
- [ ] If auto-detection fails, setup prompts user to select host
- [ ] Different hosts get appropriate setup steps if needed
- [ ] User can verify which host was detected/selected at end of setup
- [ ] Documentation explains host-specific behavior differences

---

### Q3: Setup Success Verification
**Question:** How does user confirm that `mi-mcp setup` completed successfully?

**Current State:** Command description says it "completes configuration in one step" but doesn't specify:
- What does successful completion look like?
- What console output indicates success?
- How does user verify the connection works?
- What should user try as a first test?

**Impact:** Novice user completes setup but doesn't know if it worked. Silent failure is possible.

**Requirement:** Define and document success criteria for setup:

**Acceptance Criteria:**
- [ ] mi-mcp setup produces clear success message (not silent completion)
- [ ] Success message includes: "Setup complete. MCP server is running" or similar
- [ ] Setup prompts user to run a verification test (capture + query)
- [ ] Verification test clearly shows successful memory operation
- [ ] Documentation includes screenshot or example of successful setup output

---

### Q4: Extended Tools (MI_MCP_FULL=1) for Beginners
**Question:** Are extended tools required for basic usage, and if so, when should novice enable them?

**Current State:** Documentation mentions extended tools (mi_explain, mi_verify, mi_forget, mi_batch, mi_upload, mi_match, mi_account) behind MI_MCP_FULL=1 flag, but doesn't clarify:
- Are these required or optional?
- What's the recommended first workflow? (Just 3 core tools? Or should extended be enabled?)
- When should novice enable extended tools? (Immediately or after mastering basics?)
- What breaks if extended tools are not enabled?

**Impact:** Novice doesn't know if configuration is incomplete or if basic setup is sufficient.

**Requirement:** Document recommended configuration for different user types:

**Acceptance Criteria:**
- [ ] Documentation includes "Getting Started" workflow with just 3 core tools (capture, ask, list)
- [ ] Clear statement: "Extended tools are optional and for advanced use cases"
- [ ] Setup defaults to MI_MCP_FULL=0 (basic tools only)
- [ ] Documentation provides checklist: "When to enable extended tools"
- [ ] Example first workflow uses only core tools

---

### Q5: Automatic Memory Recall Behavior
**Question:** What triggers automatic memory recall, and does it work immediately after setup?

**Current State:** Documentation mentions "agent instructions so compatible hosts automatically recall relevant memories" but doesn't explain:
- What exactly triggers automatic recall? (Every task start? Every query?)
- Does automatic behavior work immediately after setup?
- Is automatic recall per-host, or does it work identically across Claude Desktop/Code/Cursor?
- How does user see that automatic recall happened?
- Can automatic behavior be disabled if unwanted?

**Impact:** Novice has high expectations for magical automatic behavior but doesn't know if/when it works.

**Requirement:** Clarify automatic memory recall in documentation:

**Acceptance Criteria:**
- [ ] Documentation explains: "When does automatic memory recall trigger?"
- [ ] Include example: "Starting a new task, the MCP server automatically searches for relevant previous memories and surfaces them"
- [ ] Document any host-specific limitations
- [ ] Provide screenshot or example showing automatic recall in action
- [ ] Document how to disable if user prefers manual control

---

## Feature Gaps (vs. Ideal Onboarding)

### F1: Setup Wizard Interactivity
**Issue:** mi-mcp setup may not provide enough guidance for novice users.

**Recommendation:** Enhance setup to:
- [ ] Explain each step before executing it
- [ ] Validate API key before proceeding
- [ ] Handle account creation workflow if needed
- [ ] Verify host detection with user confirmation
- [ ] Run automatic verification test at end
- [ ] Provide "next steps" recommendations based on host

**Owner:** MCP Engineer  
**Priority:** HIGH

---

### F2: First-Time User Workflow
**Issue:** No documented "hello world" workflow for testing basic functionality.

**Recommendation:** Create and document:
- [ ] Simple "capture a memory" example (2-3 sentences)
- [ ] Query that memory back
- [ ] Show results with source citation
- [ ] Explain what just happened in plain language
- [ ] Suggest next steps (more complex workflows)

**Owner:** Documentation  
**Priority:** HIGH

---

### F3: Host-Specific Setup Guides
**Issue:** Novice user doesn't know if setup differs by host.

**Recommendation:** Create separate quick-start guides:
- [ ] "Getting started with Claude Desktop"
- [ ] "Getting started with Claude Code"
- [ ] "Getting started with Cursor"
- [ ] Link to appropriate guide after user specifies host

**Owner:** Documentation  
**Priority:** MEDIUM

---

## Value Assessment

**Verified Features (Strong Value Proposition):**
- Persistent memory across sessions (genuinely useful)
- Semantic search with citations (addresses real AI use case)
- Automatic memory recall (if it works) (powerful if seamless)
- PII redaction and security features (responsible design)
- Local execution, no open ports (security plus)
- Opt-in capture, confirmation gates (user control)

**Value Realization Blocked By:** Setup clarity. Users can't test value without understanding setup prerequisites.

---

## Risks if Clarifications Not Provided

1. **Silent Setup Failures:** Users complete setup, don't know it failed, have poor experience
2. **Host Mismatch:** User configures for wrong host, reports bugs that don't exist
3. **Unused Extended Tools:** Users either disable tools unnecessarily or enable prematurely
4. **Unmet Expectations:** Automatic recall doesn't work as expected due to misconfiguration
5. **High Support Load:** All Q1-Q5 answered in support issues instead of documented

---

## Success Metrics (Post-Clarification)

- [ ] 90%+ novice users complete setup successfully without support
- [ ] Setup takes <10 minutes from pip install to first memory capture
- [ ] 100% of users understand host-specific behavior after setup
- [ ] Automatic memory recall works without additional configuration
- [ ] Zero support issues about "how do I know if setup worked"

---

## Timeline Recommendations

**Immediate (before next beta user):**
- [ ] Answer Q1-Q5 definitively
- [ ] Update setup documentation with answers
- [ ] Enhance mi-mcp setup UX based on answers

**Short-term (within 1 week):**
- [ ] Implement F1 (wizard interactivity)
- [ ] Document F2 (hello world workflow)
- [ ] Create F3 (host-specific guides)

**Medium-term (before public launch):**
- [ ] User testing on complete flow
- [ ] Iterate based on testing feedback
- [ ] Finalize onboarding documentation

---

## Related Items

- **Registry:** Q1-Q5 (all open, HIGH priority)
- **Registry:** IMP1-IMP3 (feature improvements to support clarity)
- **Next Phase:** Setup attempt (blocked until Q1-Q5 answered)
