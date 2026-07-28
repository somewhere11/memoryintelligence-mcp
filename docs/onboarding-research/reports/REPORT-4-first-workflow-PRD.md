# REPORT-4: First Workflow — PRD (Build Mode)
**Type:** Product Requirements Document  
**Audience:** MCP Engineer implementing improvements  
**Phase:** Phase 2 — First use of mi_capture, mi_ask, mi_list after setup  
**Version tested:** memoryintelligence-mcp 0.2.5  
**Date:** 2026-07-28  
**Status:** VERIFIED via live testing

---

## Executive Summary

The first workflow (capture → ask → list) works correctly in v0.2.5. The core loop is functional: content is ingested, chunked into UMOs, semantically indexed, and retrievable with multi-signal scoring. The MI_FULL extended tools (mi_explain, mi_batch, mi_match, mi_account) did not activate via the `.env` approach — root cause and fix documented in REPORT-3-F4 and I8. The remaining open items in this report address user feedback surface, toolset discoverability, and the opt-in model UX.

---

## Verified Working (Do Not Break)

### mi_capture — Working ✅
- Accepts arbitrary text/markdown content
- Automatically chunks long content into per-claim child UMOs
- Returns parent UMO ID + child UMO count
- Live test: 12 child UMOs created from onboarding findings capture

### mi_ask — Working ✅
- Semantic + keyword + entity + recency multi-signal scoring
- Returns knowledge_receipt with receipt_id, question_hash, corpus_root, corpus_live_count
- Receipt enables provenance audit: `mi_verify <id>` to confirm memory is untampered
- Live test: recalled onboarding findings with proper citation

### mi_list — Working ✅
- Shows parent UMOs with metadata
- Live test: 2 parent UMOs (our capture + prior "UMO is a verb" file_import)

### mi_verify — Working ✅ (visible by default since v0.2.4)
- Recomputes seal on a specific memory, confirms it's untampered
- Not yet tested in our session but available in default toolset

### Opt-in matching — Working ✅ (source verified)
- `os.path.realpath()` normalizes trailing slashes before prefix matching
- `/Users/gabrielle/projects/` (with trailing slash) correctly covers all subdirectories
- Security: `realpath()` also resolves symlinks before matching (CVE-2025-53110 fix)

---

## Issue W1: Extended Tools (MI_MCP_FULL=1) Not Activating via `.env`

### Priority: HIGH (carries over from REPORT-3-F4)
### Category: Configuration / Feature Discoverability

**Detailed in:** REPORT-3-F4, registry.md I8

**Workflow impact:**
The user specifically wanted to access mi_explain, mi_batch, mi_match, mi_account. These are the "power tools" that differentiate the extended workflow from the basic one. They were inaccessible for the entire first workflow session because the `.env` approach silently failed.

**Requirements:** See REPORT-3-F4. Summary:
1. Fix wrapper to source `.env` unconditionally for all vars (not just as key fallback)
2. Document host-config approach for Keychain users: `claude mcp add -e MI_MCP_FULL=1 ...`

---

## Issue W2: mi_list Returns IDs, Not Inspectable Summaries

### Priority: LOW
### Category: Workflow UX

**What happens:**
`mi_list` returns a list of UMO IDs with some metadata. After `mi_capture` returns a UMO ID and says "12 children created," the user naturally wants to see what they look like. `mi_list` shows they exist, but not what's in them.

**User expectation:**
After capture, the mental model is: "Did it save the right thing?" Users want to see a snippet or summary, not just IDs. The flow of capture → verify is currently: capture → remember the ID → `mi_ask` for something related → hope it comes back.

**Requirements:**
1. `mi_list` option to show a snippet (first 100 chars) of each UMO's content
2. OR: `mi_capture` return value includes a content preview alongside the UMO ID
3. `mi_verify` confirmation output should include the verified content digest in human-readable form

**Acceptance Criteria:**
- [ ] User can see a preview of captured content without querying for it
- [ ] OR: `mi_list` has a `--verbose` or `--preview` mode that includes content snippets

---

## Issue W3: Chunking Transparency

### Priority: LOW
### Category: Mental Model / Onboarding

**What happens:**
A `mi_capture` call on a long input returns: `parent_id: <id>, child_count: 12`. The user doesn't know:
- What criteria drove chunking (per-claim? per-paragraph? by token count?)
- Whether all 12 children are queryable individually or only as a group
- Whether `mi_list` will show 13 items (1 parent + 12 children) or just 1 (parent)

**Live test finding:**
`mi_list` showed 2 parent UMOs (not 13). So children are NOT listed by `mi_list` by default. This is likely the right behavior (parent = the queryable entry), but it creates confusion: "I captured 13 things but only see 2?"

**Requirements:**
1. README should explain the parent/child UMO model briefly: "Long captures are split into per-claim children, all retrievable via `mi_ask`. `mi_list` shows only parent UMOs."
2. `mi_capture` return value could include: `children: 12, note: "each claim searchable individually"`
3. Consider: `mi_list --children` to show child UMOs if the user wants to inspect them

**Acceptance Criteria:**
- [ ] README explains UMO chunking model in plain language
- [ ] `mi_capture` response makes clear that children are queryable but not listed in `mi_list`

---

## Issue W4: Knowledge Receipt — Provenance Not Explained to New Users

### Priority: MEDIUM
### Category: Feature Discovery / Docs

**What happens:**
`mi_ask` returns a `knowledge_receipt` with `receipt_id`, `question_hash`, `corpus_root`, `corpus_live_count`. These are powerful provenance fields — they're the audit trail for "how do you know that?" But a new user seeing these fields has no idea what they mean or why they matter.

The MCP server instructions say: "To prove a single memory is untampered, call `mi_verify` with its id — it recomputes the seal and returns whether the stored meaning still matches what was captured." This is excellent. But it's in the system prompt, not in the user-facing docs.

**Requirements:**
1. Add a "Memory Provenance" section to the README explaining knowledge receipts in plain English
2. Document `mi_verify` in the README with a worked example: capture → ask → verify
3. Consider: `mi_ask` response includes a human-readable note alongside the receipt: "memory verified intact at time of recall"

**Acceptance Criteria:**
- [ ] README explains what `knowledge_receipt` fields mean
- [ ] `mi_verify` has a worked example in the README showing end-to-end provenance chain
- [ ] MCP server description (shown to agents) mentions provenance/verification briefly

---

## What Worked Well in First Workflow (Preserve These)

- Chunking is automatic — no user action needed for long content ✅
- Semantic recall found relevant memories using non-exact wording ✅
- Knowledge receipts returned by default — provenance built-in ✅
- `mi_list` is clean and fast ✅
- `mi_verify` visible in default toolset (v0.2.4+) — no FULL needed ✅
- Opt-in model security: captures in non-opted directories fail gracefully ✅

---

## Summary Table

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| W1 | MI_MCP_FULL=1 not activating via .env | HIGH | Workaround applied (REPORT-3-F4) |
| W2 | mi_list no content preview | LOW | OPEN |
| W3 | Chunking not explained | LOW | OPEN |
| W4 | Knowledge receipt undocumented for users | MEDIUM | OPEN |
