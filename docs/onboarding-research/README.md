# Onboarding Research — MemoryIntelligence MCP

**Study dates:** 2026-06-05 through 2026-07-28  
**Version tested:** 0.1.5 → 0.2.5 (tracked through full changelog)  
**Method:** "Think out loud while using" — novice user lens, real API key, live testing  
**Tester:** Internal team member, novice-user simulation  

---

## What This Is

A structured onboarding study of the full user journey — from first discovery to first `mi_ask` recall. Every report is grounded in real tool outputs, source code inspection, and live testing. No speculation.

Each workflow stage produces two complementary reports:
- **PRD** — for engineers: friction points with requirements and acceptance criteria
- **Narrative** — for writers: first-person empathy-driven perspective for doc improvement

---

## Reports

### Stage 1: Initial Discovery (`reports/REPORT-1-*`)
First encounter — PyPI page, pip install, first impressions.

### Stage 2: Repository Review (`reports/REPORT-2-*`)
GitHub README, doc structure, Q&A coverage.

### Stage 3: Setup Walkthrough (`reports/REPORT-3-*`)
pip install → `mi-mcp wire` → `mi-mcp doctor`. Live outputs captured.

**Highest-priority findings:**
- Python ≥3.10 requirement not in README prose (silent install failure on macOS)
- `.env` silently ignored for Keychain users — `MI_MCP_FULL=1` never applied (see [I8 in registry.md](registry.md))
- Agent-assisted setup (Claude Code) has no documented secure API key path
- `doctor` uses `[✗]` for both errors and expected non-configurations

### Stage 4: First Workflow (`reports/REPORT-4-*`)
`mi_capture` → `mi_ask` → `mi_list` → `mi_verify`. All tools live-tested.

**Key findings:**
- `mi_verify` works; returns full audit chain — strongest differentiator, undocumented for end users
- UMO chunking model (parent/child) not explained; `mi_list` count vs. corpus count confuses new users
- Knowledge receipts from `mi_ask` not explained in README

### Stage 5: Final Assessment (`reports/REPORT-5-*`)
Consolidated findings with priority matrix and friction map across full journey.

### Stage 6: Path A — Portal (No Pre-Existing Key) (`reports/REPORT-6-*`)
Full portal documented via browser inspection.

**Critical finding:**
Portal signup is invite-only ("Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now.") — not documented anywhere in the README. Users following onboarding instructions hit this wall with no path forward.

**Additional portal findings:** In-browser MI Search UI entirely undocumented; "shown once" key copy inconsistency; team-add catch-22 for invite-only product.

### Stage 7: Extended Tools — `MI_MCP_FULL=1` (`reports/REPORT-7-*`)
Live testing of all 4 extended tools after activating via host config (not `.env` — see I8).

**Results:**

| Tool | Status | Key Finding |
|------|--------|-------------|
| `mi_explain` | ✅ Working | 3 levels (human/audit/full); depth gated by capture source — file_import gets 113 SVO triples + full entity graph; claude-connector captures get `svo: null` |
| `mi_match` | ✅ Working | Composite = semantic × entity × topic weighting; 73% semantic → 51.2% composite when entity/topic overlap = 0% |
| `mi_batch` | ✅ Working | Large payloads (4+ long items) cause ConnectTimeout with no error; returns full UMO including pipeline lineage |
| `mi_account` | ❌ 401 | Valid key authenticates all other 9 tools; mi_account alone fails — likely tier gate or auth scope bug (I9, HIGH) |

**Key architectural insight:** Extended tools are a developer/pipeline API, not a user feature. Base 6 tools = daily use; extended 4 tools = pipeline inspection, bulk ingestion, and operational monitoring. This distinction is not articulated in the README.

---

## Raw Logs

- `logs/PHASE-2-PATH-A-no-key-realtime.md` — live think-aloud log, no-key path (complete)
- `logs/PHASE-2-PATH-B-with-key-realtime.md` — live think-aloud log, with-key path (complete)

---

## Supporting Files

- [`canon.md`](canon.md) — single source of truth: verified facts, version history, tool behaviors, env vars
- [`registry.md`](registry.md) — living issue backlog: all friction points with priorities, owners, acceptance criteria

---

## Top 5 Highest-Impact Docs-Only Fixes

These require no code changes and would close the largest first-hour onboarding gaps:

1. **Add "Requires Python ≥3.10" to Quick Start** + venv/Homebrew snippet for macOS
2. **Add "Agent-Assisted Setup" section** with Keychain pre-storage command + "run `wire` not `setup`"
3. **Document `MI_MCP_FULL=1` for Keychain users** — host config, not `.env`
4. **Add "Memory Provenance" section** — knowledge receipts + `mi_verify` worked example
5. **Note invite/beta status** near portal URL with path forward for uninvited users

---

## Versions Tracked

| Version | Date | Notable for Onboarding |
|---------|------|----------------------|
| 0.1.5 | 2026-06-05 | Initial test version |
| 0.1.6 | 2026-06-09 | Security fix: removed key from doctor output |
| 0.2.3 | 2026-07-22 | macOS sandbox fix: Desktop now uses Python direct (wrapper bypassed) |
| 0.2.4 | 2026-07-24 | `mi_verify` visible by default; knowledge receipts in `mi_ask` |
| 0.2.5 | 2026-07-24 | **I3 fixed:** setup commands now in `--help` |
