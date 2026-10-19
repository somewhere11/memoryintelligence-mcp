# REPORT-6: Path A Portal Experience — PRD (Build Mode)
**Type:** Product Requirements Document  
**Audience:** MCP Engineer + Product/Portal team  
**Phase:** Path A — User with no API key navigates portal for the first time  
**Source:** Browser inspection of memoryintelligence.io/portal (2026-07-28)  
**Date:** 2026-07-28

---

## Executive Summary

Path A testing revealed the portal is invite-only with no README documentation of that status. Users following the README to "get a free API key" hit an invite wall at first contact with no guidance on how to proceed. Beyond this critical gap, the portal itself is substantially more capable than the README implies (in-browser MI Search, team management, usage analytics, pricing) — but none of this is surfaced in onboarding documentation.

---

## Issue P1: Invite-Only Status Not Documented in README

### Priority: CRITICAL
### Category: Onboarding Blocker

**What happens:**
User reads README: "Get a free API key at https://memoryintelligence.io/portal". They navigate there. Signup form shows: "Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now." No guidance on how to request access.

**User experience:**
1. Follow README instruction → portal
2. Attempt to create account → "invite-only" notice
3. User thinks: "Am I in the wrong place? Is this a different product? Is it still in pre-launch?"
4. No call to action: no waitlist link, no email to contact, no invite request form
5. **User abandons**

**Requirements:**
1. README must state invite/beta status near the "get your API key" instruction
2. Portal signup page must provide a path forward for uninvited users: waitlist form, invite request, or "reach out at [email]"
3. Optionally: add invite request link to `mi-mcp --help` portal URL line

**Acceptance Criteria:**
- [ ] README contains invite/waitlist status notice near portal URL
- [ ] Portal signup page has a "request access" or "join waitlist" call to action for users without invites
- [ ] `mi-mcp doctor` or `mi-mcp setup` outputs a useful message if API key validation fails (key expired, not yet activated, wrong format)

---

## Issue P2: Key "Shown Once" Language Inconsistency

### Priority: MEDIUM
### Category: Trust / UI Clarity

**What happens:**
Key creation modal says: "Copy your secret key now. You won't be able to see it again."
But: Keys tab has a "Reveal" button for existing keys.

Users who miss copying their key at creation believe it's permanently lost. Some may create a new key, revoke the old one, update all their configs — unnecessary panic and churn.

**Requirements:**
1. Align copy with reality. Choose one:
   - **Option A (Keep Reveal):** Change creation modal to say "Your key is shown here for convenience. You can always reveal it again from the Keys tab."
   - **Option B (Truly Once):** Remove Reveal button and document that keys are shown once (aligns with security best practice)
2. Add a tooltip or note on the Keys tab explaining the Reveal function

**Acceptance Criteria:**
- [ ] Creation modal copy and Keys tab Reveal behavior are consistent
- [ ] Users can determine key recoverability without trial-and-error

---

## Issue P3: In-Browser MI Search Not Documented

### Priority: MEDIUM
### Category: Feature Discovery

**What it is:**
The portal Dashboard has a full MI Search interface:
- Semantic search over all captured memories
- Channel filters (API, Slack, Google Drive)
- Date range filters
- Quick query chips
- "Build summary" panel with "Run MI Ask" — synthesizes selected memories
- "Ask from memory" floating dialog — session-based conversation with memory corpus
- PII detection dialog — catches PII before capture, offers redact/keep options

This is a complete alternative interface to the MCP tools — usable by anyone with portal access, no local setup required.

**Why it matters:**
- Users who can't set up the MCP (Python issues, unsupported environment) can still use MI via portal
- Users wanting a visual interface for memory management have one
- Teams sharing a workspace can search memories collaboratively in the portal

**Requirements:**
1. README should mention the portal's memory interface as a second access path
2. Consider adding a "Web Interface" section to the README with 1-2 sentences describing portal capabilities
3. Portal Dashboard should have a link to the MCP setup guide (both surfaces, one product)

**Acceptance Criteria:**
- [ ] README references portal UI as an alternative/complementary interface
- [ ] Portal Dashboard has a link to MCP onboarding instructions

---

## Issue P4: Health Endpoint Not in README

### Priority: LOW
### Category: Documentation Gap

**What it is:**
Portal Quickstart tab documents: `curl -s https://api.memoryintelligence.io/health | python3 -m json.tool`

This is the best way to validate an API key is working before running `mi-mcp setup`. It's in the portal Quickstart but not in the README or CLI help.

**Requirements:**
1. Add health endpoint to README under "Verify your key" or "Troubleshooting" section
2. Consider: `mi-mcp doctor` could optionally call health endpoint to verify API key is valid (not just resolvable)

**Acceptance Criteria:**
- [ ] Health endpoint URL documented in README or `mi-mcp --help` output
- [ ] `mi-mcp doctor` key check includes a connectivity test (not just local resolution)

---

## Issue P5: Plans/Pricing Invisible Pre-Portal

### Priority: LOW
### Category: Conversion / Evaluation

**What it is:**
Full pricing (Tier 01 $29/mo, Tier 02 $49/mo, Tier 03 $99/mo) with feature matrices is visible only inside the portal Billing tab. Users evaluating the product from GitHub/PyPI cannot see pricing.

**Requirements:**
1. Add a brief pricing/plans section to README or GitHub page
2. Or link to a pricing page at memoryintelligence.io

**Acceptance Criteria:**
- [ ] Users can find tier pricing without creating a portal account

---

## What the Portal Does Well (Preserve)

- Clean signup form — minimal, no card required ✅
- Two verification methods (link + 6-digit code) — reduces email delivery friction ✅
- Key revealable from Keys tab — reduces lost-key panic (once copy is corrected) ✅
- Key rotation and expiration options — enterprise-ready ✅
- PII detection dialog with redact option — proactive, not reactive ✅
- Beta offer statement ("all tiers free during beta") — clear, trust-building ✅
- Workspace + team role system — ready for team use ✅

---

## Summary Table

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| P1 | Invite-only not documented | CRITICAL | OPEN |
| P2 | "Shown once" inconsistency | MEDIUM | OPEN |
| P3 | In-browser MI Search undocumented | MEDIUM | OPEN |
| P4 | Health endpoint not in README | LOW | OPEN |
| P5 | Pricing invisible pre-portal | LOW | OPEN |
