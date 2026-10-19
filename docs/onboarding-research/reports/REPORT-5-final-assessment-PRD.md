# REPORT-5: Final Assessment — PRD (Build Mode)
**Type:** Product Requirements Document — Consolidated Findings  
**Audience:** MCP Engineer  
**Scope:** Full onboarding study — PyPI discovery through first workflow (Path B, with API key)  
**Version tested:** 0.1.5 → 0.2.5 (tracked through full changelog)  
**Date:** 2026-07-28  
**Study model:** "Think out loud while using" — novice user, real API key, live testing

---

## Summary of All Issues (Priority-Ordered)

### HIGH PRIORITY

#### H1 — Python Version: Silent Install Failure (I2/I5)
**Status:** OPEN  
Users on macOS system Python 3.9.6 receive "package not found" or a confusing error when running `pip install`. The Python ≥3.10 requirement exists only in a Shields.io badge, not in README prose.  
**Fix:** Add one prose line + venv snippet to Quick Start. See REPORT-3-F1.

#### H2 — `.env` Silently Ignored for Keychain Users (I8)
**Status:** OPEN (workaround: host-config env block)  
Users following the documented pattern of `MI_MCP_FULL=1` in `.env` see no effect when using Keychain. No error. No warning. The security-correct setup path causes the documented config approach to fail.  
**Fix:** Wrapper should source `.env` unconditionally for non-key vars. Docs must clarify `.env` role vs. host-config env for Keychain users. See REPORT-3-F4, registry.md I8.

---

### MEDIUM PRIORITY

#### M1 — `doctor` Conflates Errors and Expected Non-Configurations (I6)
**Status:** OPEN  
Three `[✗]` symbols appear on a clean healthy install (binary not on PATH, cursor not wired, vscode not wired). Only the first is advisory; the other two are expected non-configurations. Novices read this as three failures contradicting the `healthy ✓` verdict.  
**Fix:** Three-symbol system: `[✓]` pass / `[~]` info / `[✗]` action required. See REPORT-3-F3, registry.md I6.

#### M2 — Agent-Assisted Setup: API Key Security Dilemma (I7)
**Status:** OPEN  
Interactive `mi-mcp setup` exposes the API key in agent context. No documentation covers the "store key in Keychain out-of-band, then run `mi-mcp wire`" path for Claude Code users.  
**Fix:** Add "Agent-Assisted Setup" section to README. See REPORT-3-F5, registry.md I7.

#### M3 — Knowledge Receipt Undocumented for End Users (Q-WORKFLOW-1)
**Status:** OPEN  
`mi_ask` returns a `knowledge_receipt` with receipt_id, question_hash, corpus_root, corpus_live_count, and a `mi_verify` path for provenance audit. This is one of the product's strongest differentiators for professional/compliance use — and it's completely invisible in the README.  
**Fix:** Add "Memory Provenance" section to README with worked example. See REPORT-4-W4.

#### M4 — `ownership_verified: false` in mi_verify — No Explanation (Q-WORKFLOW-1)
**Status:** OPEN  
`mi_verify` returns `ownership_verified: false` even when `valid: true` and `hash_chain_valid: true`. There is no documentation explaining what ownership verification is, when it applies, and what `false` means in context.  
**Fix:** Document ownership_verified semantics in README verify section. Is this a cross-session limitation? A different auth requirement?

---

### LOW PRIORITY

#### L1 — Portal Onboarding Entirely Undocumented (Q-PATH-A-1 through Q-PATH-A-5)
**Status:** OPEN  
Path A (no API key yet) testing revealed: no account creation walkthrough, no key format documentation, no generation time expectation, no key validation method, no portal downtime fallback. These are all documented as open questions in registry.md.  
**Fix:** Add portal onboarding section to README. Even a minimal "1. Go to memoryintelligence.io/portal, 2. Create account, 3. Generate key (takes <1 minute), 4. Keys begin with `mi_sk_`" would close most of these.

#### L2 — Chunking Model Not Explained (W3)
**Status:** OPEN  
`mi_capture` returns `child_count: N` but no explanation of what chunking is, why it happens, or how children relate to the parent in searches. `mi_list` shows parent count only, while `mi_ask` corpus contains all children — users see a discrepancy with no explanation.  
**Fix:** One paragraph in README explaining UMO parent/child model. See REPORT-4-W3, Q-WORKFLOW-3.

#### L3 — `mi_ask` Score vs. Display Order Discrepancy (Q-WORKFLOW-2)
**Status:** OBSERVED — may be by design  
Composite scores shown in `mi_ask` results do not correspond to display order. The highest-scoring result appeared last. If scores ≠ ranking, users relying on scores to interpret relevance are misled.  
**Fix:** Document that shown scores reflect signal breakdown for transparency; display order reflects a separate relevance ranking.

#### L4 — mi_list No Content Preview (W2)
**Status:** OPEN  
`mi_list` returns IDs, topics, entities, timestamps — no content snippet. After a capture, users have no way to confirm what was saved without running `mi_ask`.  
**Fix:** Add `--preview` flag to `mi_list` showing first 100 chars of each UMO. See REPORT-4-W2.

---

## Resolved Issues (Verify Fixes Hold)

| ID | Issue | Resolution |
|----|-------|------------|
| I3 | setup hidden from --help | Fixed in v0.2.5 ✅ |
| I1/I4 | PyPI page "broken" | Root cause: CDN bot-challenge, not package defect — not actionable ✅ |
| Q1 | API key setup sequence | Documented in full README via JSON API ✅ |
| Q2 | Host selection | Default = desktop+code, Cursor opt-in ✅ |
| Q3 | Setup verification output | doctor runs as final step; live output captured ✅ |
| Q4 | Extended tools necessity | Explicitly optional; core 3 sufficient for value ✅ |
| Q5 | Auto recall | Works immediately after wire+restart; no extra config ✅ |

---

## Cumulative Friction Map (Onboarding Journey)

```
[Discovery]    → PyPI page inaccessible to non-browser agents (bot-challenge, not actionable)
                  GitHub works as primary discovery point ✅

[Install]      → Python version silent failure (H1) 🔴
                  No venv/Homebrew guidance for macOS users

[--help]       → Fixed in v0.2.5: setup commands now visible ✅

[API Key]      → Portal process undocumented (L1) 🟡
                  No key format, generation time, or validation method documented

[Agent Setup]  → Security fork: key in agent context vs. out-of-band Keychain (M2) 🟡
                  No documentation for the correct path

[wire]         → Excellent: clear output, backup, no key in configs ✅

[doctor]       → Symbol conflation creates false alarm (M1) 🟡
                  3 [✗] on healthy install

[MI_MCP_FULL]  → .env ignored for Keychain users (H2) 🔴
                  Silent failure, correct path undocumented

[mi_capture]   → Works; chunking model unexplained (L2) 🟡

[mi_ask]       → Works; knowledge receipt unpromoted (M3) 🟡

[mi_verify]    → Works; ownership_verified semantics undocumented (M4) 🟡

[mi_list]      → Works; no content preview (L4) 🟡
                  corpus_live_count vs list count discrepancy unexplained (L2)
```

---

## Highest-Value Quick Wins (Docs Only, No Code)

These five changes require only documentation updates and would close the largest gap in first-hour user experience:

1. **Python ≥3.10 prose** + venv snippet in Quick Start → closes H1 for most users
2. **Agent setup section** (Keychain command + use `wire` not `setup`) → closes M2
3. **MI_MCP_FULL=1 for Keychain users** (use host config, not .env) → closes H2 for Keychain users
4. **Memory provenance section** (knowledge receipt + mi_verify example) → surfaces M3 differentiator
5. **Portal walkthrough** (account creation, key format, generation time) → closes L1

Combined effort estimate: 1–2 hours of writing. Combined impact: closes 3 HIGH/MEDIUM issues and surfaces the product's strongest trust-building feature.

---

## Versioning Note

Tracked through full changelog 0.1.0 → 0.2.5. The cadence (15 versions in ~2 months) reflects an active team. The friction points found are all addressable without slowing that cadence — they're docs-layer gaps, not architectural issues.
