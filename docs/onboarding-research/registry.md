# Registry: Living Backlog

## ⏸️ HELD ACTIONS (Awaiting Go-Ahead)

### HELD-1: Submit Generated Output as PR to somewhere11/memoryintelligence-mcp
**Status:** ON HOLD — DO NOT EXECUTE until explicit go-ahead  
**Requested:** 2026-06-09  
**Requested By:** User (identifies as part of somewhere11 team)

**Description:**
- Package contents of `/generated-output/` (and relevant supporting files from the 6-file system) into a PR for the memoryintelligence-mcp repo
- Goal: Hand off findings directly to developer for review and integration
- This converts the engagement from "external beta user reports" to "internal team contribution"

**Blocking Condition:** User has explicitly said "do not do this yet until i give the go ahead"

**Next Action When Unblocked:**
- Confirm target branch / PR conventions for somewhere11/memoryintelligence-mcp
- Determine which files are PR-appropriate (likely generated-output reports, possibly canon.md findings as an issue/doc PR)
- Confirm whether this is a docs PR, an issue-only submission, or code+docs PR
- Ask user for repo write access confirmation / fork workflow preference

---

## Research Questions (Documentation Gaps)

**Note:** These questions arose from Phase 1.5 (documentation search). They are not blockers requiring engineer input, but rather gaps in available documentation. Novice user will attempt to answer these through practical experience in Phase 2 setup attempt.

---

## Path A Questions (No API Key Yet - Pre-Setup)

**Scenario:** User discovered tool, wants to get API key before installing

### Q-PATH-A-1: Portal Account Creation Instructions
**Status:** OPEN  
**Discovery:** Docs say "Free API key from memoryintelligence.io/portal" but no step-by-step account creation guide  
**Missing:** Screenshots, email verification process, waitlist info, alternative signup methods

### Q-PATH-A-2: API Key Format & Generation Time
**Status:** OPEN  
**Discovery:** No documentation about what the key looks like or how long generation takes  
**Missing:** Example key format, immediate vs. email delivery, visibility in portal

### Q-PATH-A-3: Key Validity & Multiple Keys
**Status:** OPEN  
**Discovery:** Unknown if key expires, if user can generate multiple, regenerate, or revoke  
**Missing:** Key lifecycle documentation

### Q-PATH-A-4: Key Testing Before Setup
**Status:** OPEN  
**Discovery:** No way to test key validity before running pip install and mi-mcp setup  
**Missing:** Validation endpoint or test command in portal

### Q-PATH-A-5: Portal Unavailability Handling
**Status:** OPEN  
**Discovery:** No documentation of fallback if portal is down or inaccessible  
**Missing:** Offline signup, alternative methods, status page reference

---

## Resolved Questions (Answered via v0.1.6 PyPI Description, 2026-06-09)

### Q1: API Key Setup Flow ✅ RESOLVED
**Resolution:** `mi-mcp setup` (alias `mi-mcp init`) prompts interactively for API key (hidden input) as step 1 of 5. Sequence is: install package (no key needed) → run `mi-mcp setup` → paste key when prompted. Confirmed via full README description.

**Remaining nuance:** This is clear in the FULL description (retrieved via JSON API), but was lost in earlier WebFetch summaries. Worth checking if the rendered PyPI/GitHub page itself makes this as clear, or if it's buried.

---

### Q2: Host Selection & Configuration ✅ RESOLVED
**Resolution:** Setup wires Claude Desktop + Claude Code by default (`--surfaces desktop,code`). Cursor is opt-in via `--surfaces desktop,code,cursor`. No detection logic — it configures the default targets' config files directly regardless of what's actually installed.

**New Question Raised:** What happens if a user does NOT have Claude Desktop installed, but setup still "wires" it? Does it create a config file for an app that doesn't exist? (See Q-NEW-1 below)

---

### Q3: Setup Verification ✅ RESOLVED
**Resolution:** Step 5 of `mi-mcp setup` automatically runs the equivalent of `mi-mcp doctor`, which checks binary, wrapper, key resolvability, wiring, and opt-in status. Users can also re-run `mi-mcp doctor` or `mi-mcp status` standalone anytime.

**Remaining:** Still haven't seen actual console OUTPUT/formatting of doctor's results — only know what it checks, not what it prints.

---

### Q4: Extended Tools Necessity ✅ RESOLVED
**Resolution:** Explicitly stated: "The three core tools (mi_capture/mi_ask/mi_list) are all you need to get value today. Everything else is opt-in via MI_MCP_FULL=1." This is unambiguous in the full description.

---

### Q5: Automatic vs Manual Memory Recall ✅ RESOLVED
**Resolution:** Concrete worked example provided in description: capture a fact in session 1, ask about it in session 2 (new session), assistant auto-recalls via `mi_ask` and cites the source. Works immediately after wiring + restart, no extra config. Capture still requires per-directory opt-in.

---

## New Questions (Raised by v0.1.6 Findings)

### Q-NEW-1: Setup Wires Hosts That May Not Be Installed
**Status:** OPEN  
**Priority:** MEDIUM  
**Description:** Default `--surfaces desktop,code` configures BOTH Claude Desktop and Claude Code regardless of whether the user has both installed. What happens if only one is present?
- Does it create orphaned config entries?
- Does `doctor` flag this as a problem or silently ignore?
- Should default behavior detect installed hosts instead of blanket-configuring both?

**Owner:** MCP Engineer  
**Next Action:** Test setup on a machine with only ONE host installed; observe `doctor`/`status` output

---

### Q-NEW-2: What Does `doctor` Output Actually Look Like?
**Status:** ✅ RESOLVED — captured live (2026-07-28)

**Real output captured** — see PHASE-2-PATH-B-with-key-realtime.md for full console output.

**New Issue Raised from doctor output → I6 below.**

---

### I6: `doctor` Uses `[✗]` for Both Failures and Expected Non-Configurations
**Status:** OPEN  
**Priority:** MEDIUM  
**Discovered:** 2026-07-28, live doctor run on 0.2.5

**Details:**
- Three `[✗]` items appear in doctor output on a clean install
- Only ONE is a real advisory (`binary not on PATH`) — and even that isn't blocking (wrapper handles launch)
- The other two (`cursor wired`, `vscode wired`) are expected non-configurations: defaults don't include Cursor/VSCode
- A novice sees three `[✗]` marks on a perfectly healthy install and reads it as three failures
- Overall verdict `healthy ✓` contradicts the visual impression of three red items

**Suggested Fix:** Use distinct symbols:
- `[✓]` = passing
- `[~]` or `[-]` = informational / expected non-configuration (not wired by choice, binary in venv)
- `[✗]` = actual error requiring action

**Owner:** MCP Engineer  
**Next Action:** Review doctor symbol logic; only use `[✗]` for states that are genuinely unhealthy

---

### I8: `.env` Is Silently Ignored When Using Keychain — MI_MCP_FULL=1 Never Applied
**Status:** OPEN (workaround applied)  
**Priority:** HIGH  
**Discovered:** 2026-07-28, Session 2 — diagnosing why MI_MCP_FULL=1 had no effect after restart

**Details:**
The wrapper script (`run-mi-mcp.sh`) sources `~/.memoryintelligence/.env` conditionally:
```bash
if [[ -z "${MI_API_KEY:-}" && -f "$__mi_envf" ]]; then
    set -a; . "$__mi_envf"; set +a
fi
```
When Keychain resolves `MI_API_KEY` (the recommended secure path), the condition is FALSE and `.env` is NEVER sourced. Any config in `.env` (including `MI_MCP_FULL=1`) is silently ignored.

Additionally, Claude Desktop bypasses the wrapper entirely (v0.2.3 sandbox fix) — so `.env` has zero effect for Desktop regardless.

**Impact:**
- README documents `.env` as the place to set env config, but this only works for users on the insecure key path (no Keychain)
- A user who correctly uses Keychain and follows the docs to set `MI_MCP_FULL=1` in `.env` will see no error, no warning, and no extended tools — completely silent failure
- Affects any env var documented as going in `.env` (MI_MCP_FULL, potentially others)

**Workaround Applied (2026-07-28):**
- Claude Code: re-added MCP entry with `MI_MCP_FULL=1` in host config via `claude mcp add -e MI_MCP_FULL=1`
- Claude Desktop: added `"MI_MCP_FULL": "1"` to `env` block in `claude_desktop_config.json`
- Restart required for changes to take effect

**Recommendation:**
Two-part fix needed:
1. **Wrapper fix**: Source `.env` unconditionally for non-key env vars (separate the key-fallback role from the general env config role, OR source .env first and let it set any vars including key)
2. **Docs fix**: Document that Keychain users must set `MI_MCP_FULL` in their host config, not in `.env`. Clarify `.env`'s role is specifically as a key-fallback file.

**Owner:** MCP Engineer + Documentation  
**Next Action:** Fix wrapper conditional; update README with Keychain-aware instructions for MI_MCP_FULL

---

### I7: Agent-Assisted Setup Creates API Key Security Dilemma (Undocumented)
**Status:** OPEN  
**Priority:** MEDIUM  
**Discovered:** 2026-07-28, Phase 2 Path B keychain step

**Details:**
- `mi-mcp setup` (interactive happy path) prompts for API key as hidden terminal input
- When an AI agent (e.g., Claude Code) is running the setup, the user faces a fork:
  - **Option A:** Let agent run `mi-mcp setup` → key appears in agent's terminal context / transcript → against product's own security advice
  - **Option B:** Store key in Keychain out-of-band (user runs `read -s K; security add-generic-password...` in own terminal), then agent runs `mi-mcp wire` → secure, but undocumented, breaks the "one command" narrative
- Neither option is documented for the agent-assisted setup scenario

**Recommendation:** Add a note to docs for "Setting up via Claude Code or another AI agent":
> "Because your API key should not appear in the agent's context, we recommend storing it in Keychain before your agent session. Run this in your own terminal: `read -s K; security add-generic-password -a "$USER" -s "MI_API_KEY" -w "$K" -U; unset K`, then ask your agent to run `mi-mcp wire`."

**Owner:** Documentation  
**Next Action:** Add "Claude Code / agent setup" section to README

---

## First Workflow Observations (Session 2, Live Testing)

### Q-WORKFLOW-1: What Does `ownership_verified: false` Mean in mi_verify?
**Status:** OPEN  
**Priority:** LOW  
**Discovery:** `mi_verify` on UMO `019faa0a-e342-e42d-6800-4ca21e21f27f` returned `valid: true`, `hash_chain_valid: true`, but `ownership_verified: false`  
**Question:** Is ownership verification a separate auth step? Does it require the same credential that created the UMO? Is this expected for cross-session verify calls?  
**Impact:** If users see `ownership_verified: false` alongside `valid: true`, they may not know whether to trust the result. Docs should explain what ownership verification is and when it applies.

### Q-WORKFLOW-2: `mi_ask` Results Appear Ordered by Relevance, Not Composite Score
**Status:** OBSERVED (may be by design)  
**Priority:** LOW  
**Discovery:** `mi_ask` returned "UMO is a verb" with composite score 0.3228 (highest in set) but placed it LAST in the results array. Keychain-relevant results with scores 0.09–0.19 were listed first.  
**Hypothesis:** Results are sorted by a relevance ranking separate from the composite score shown. The composite score may be for transparency/audit, not ordering.  
**Impact:** If composite score ≠ display order, users/agents relying on the shown scores to understand ranking priority may be misled. Documentation should clarify: "scores reflect signal breakdown; display order reflects relevance ranking."

### Q-WORKFLOW-3: corpus_live_count (28) >> mi_list parent count (3)
**Status:** RESOLVED (working as designed, but undocumented)  
**Discovery:** `mi_ask` knowledge receipt shows 28 live memories. `mi_list` shows 3 parent UMOs. The 25-item gap = child UMOs from chunked captures.  
**Confirmation:** Children are individually searchable via `mi_ask` but not listed in `mi_list` by default.  
**Docs gap:** No README explanation of why these counts differ. Users who check `mi_list` after a large capture may think their memories "didn't save." Worth a one-liner in docs.

---

## Path A Questions — RESOLVED (2026-07-28 Browser Inspection)

### Q-PATH-A-1: Portal Account Creation Instructions ✅ RESOLVED
Email + optional name + optional "what are you building?" + password (8+ chars). Verification via email link OR 6-digit code. Key revealed immediately post-verification.
**Critical gap:** Portal is currently **invite-only** — "Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now." This is not in the README.

### Q-PATH-A-2: API Key Format & Generation Time ✅ RESOLVED
Format: `mi_sk_beta_...` (confirmed from portal Quickstart tab). Key generated immediately after email verification. Can be re-revealed from Keys tab (contradicts "shown once" language in creation modal — see A3 below).

### Q-PATH-A-3: Key Validity & Multiple Keys ✅ RESOLVED
Expiration options: Never / 30 / 90 / 365 days. Can revoke or rotate keys. Multiple keys per workspace. Up to 3 workspaces per beta user.

### Q-PATH-A-4: Key Testing Before Setup ✅ RESOLVED
Health endpoint: `curl -s https://api.memoryintelligence.io/health | python3 -m json.tool` — this is in the portal Quickstart tab, not the README.

### Q-PATH-A-5: Portal Unavailability Fallback ⚠️ PARTIAL
No status page referenced in portal or README. No offline signup. Email delivery dependency (verification link). This remains undocumented.

---

## New Issues from Portal Inspection (2026-07-28)

### A1: Invite-Only Status Not in README (CRITICAL)
**Status:** OPEN  
**Priority:** HIGH  
The portal signup form shows: "Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now." The README says "Get a free API key at memoryintelligence.io/portal" with no mention of invite status. New users hit a wall with no guidance on requesting access.
**Fix:** Add invite/beta status note near "get your API key" in README.

### A2: In-Browser Memory UI Undocumented
**Status:** OPEN  
**Priority:** MEDIUM  
Portal has MI Search (semantic search), Build Summary, Run MI Ask, and "Ask from memory" dialog — a complete web interface for memory management. Not mentioned in README. Users who only read the README don't know this exists, and can't use it without discovering the portal independently.

### A3: "Shown Once" Key Language Inconsistency
**Status:** OPEN  
**Priority:** MEDIUM  
Key creation modal says "Copy your secret key now. You won't be able to see it again." But the Keys tab has a "Reveal" button for existing keys. The "shown once" language causes unnecessary panic. One of these needs to match the other: either keys are truly shown once (remove Reveal button) or update the creation modal copy to say "You can reveal your key again from the Keys tab anytime."

### A4: Team Addition Catch-22 (Beta Limitation, Undocumented)
**Status:** OPEN  
**Priority:** LOW  
"The person must already have an MI account. Email invites for new users are coming soon." Invite-only + must-have-account-to-be-added = users can't bring new team members. Not documented. Should be surfaced in team management UI and possibly README.

### A5: Plans Visible Only in Portal (Not README)
**Status:** OPEN  
**Priority:** LOW  
Tier 01 ($29), Tier 02 ($49), Tier 03 ($99) with full feature matrices exist in portal Billing tab. Not in README. Users evaluating the product before signing up can't see pricing without portal access. Consider adding a pricing section to README or GitHub.

---

## Issues (Product/UX)

### I1 / I4: PyPI Page "Inaccessible" — ✅ ROOT CAUSE IDENTIFIED, REFRAMED
**Status:** RESOLVED (root cause known) — Recommend CLOSE for this package, possibly file upstream with PyPI  
**Priority:** LOW (was MEDIUM/HIGH when assumed to be a packaging defect)  
**Discovered:** 2026-06-05, recurred 2026-06-09, root-caused 2026-06-09

**Root Cause:**
The PyPI project page (`pypi.org/project/memoryintelligence-mcp/`) returns a **"Client Challenge"** stub page (3KB, title "Client Challenge") to non-browser clients (curl, WebFetch). This is a CDN-level bot/anti-automation JS challenge (asset path `/_fs-ch-XXXXX/`) — NOT a defect in this package's PyPI listing.

**Evidence:**
- `curl -L` to the HTML page → 200 OK but returns "Client Challenge" stub (3038 bytes)
- `curl` to `pypi.org/pypi/memoryintelligence-mcp/json` (the API pip uses) → 200 OK, full 26KB response with complete metadata + README

**Reframed Impact:**
- Real users in real browsers (JS-enabled) almost certainly never see this — the challenge resolves transparently
- This likely affects automated/scraping access to ALL PyPI project pages, not just this package
- NOT actionable for the MCP engineer — this is PyPI platform behavior

**Recommendation:** Close as "not applicable to this project." If desired, could file feedback to PyPI about bot-challenge UX for legitimate automated tooling (low priority, out of scope for memoryintelligence-mcp team).

---

### I2/I5: Python Version Requirement — Badge-Only, Not Prose
**Status:** OPEN (downgraded from "undocumented" to "documented but low-visibility")  
**Priority:** MEDIUM (downgraded from HIGH)  
**Impact:** Silent install failure for users on Python <3.10 (macOS default is 3.9.6)  
**Discovered:** 2026-06-05, refined 2026-06-09

**Details:**
- Package requires Python >=3.10 (`requires_python` metadata field — pip WILL enforce this correctly)
- Communicated in README only via Shields.io badge: `![Python](...pyversions/memoryintelligence-mcp.svg)`
- No prose statement of "Requires Python 3.10+" anywhere in the body text
- macOS ships with Python 3.9.6 as system default

**Correction from earlier finding:** Originally we saw `pip install` fail with "package not found" — but that was because `pip` itself wasn't on PATH (system pip missing), not a Python-version-triggered failure message. With proper pip (3.12 venv), behavior with an OLD pip + new-enough Python would likely show a clearer "requires-python" error. Need to re-test: what error does pip give on Python 3.9 specifically (not "command not found")?

**Resolution Path (for users):**
```bash
brew install python@3.12
python3.12 -m venv .venv
.venv/bin/pip install memoryintelligence-mcp
```

**Docs Gap:** Add prose "Requires Python 3.10+" near Quick Start; consider venv guidance for macOS users on system Python 3.9

**Owner:** Documentation  
**Next Action:** Add explicit Python version prose statement to README Quick Start; test actual pip error message on Python <3.10

---

### I3: `mi-mcp setup` Hidden from Top-Level --help
**Status:** ✅ RESOLVED in 0.2.5 (2026-07-28)  
**Priority:** MEDIUM  
**Impact:** Novice user runs `mi-mcp --help`, sees no setup command, may give up  
**Discovered:** 2026-06-05 (v0.1.5), RE-VERIFIED 2026-06-09 on v0.1.6 — unchanged

**Details:**
- `mi-mcp --help` on 0.1.6 STILL shows only transport/server flags — zero subcommands listed
- All 5 subcommands confirmed WORKING via direct invocation:
  - `mi-mcp setup --help` ✅ (full options shown)
  - `mi-mcp doctor --help` ✅ (takes --home only)
  - `mi-mcp status --help` ✅ (takes --home only)
  - `mi-mcp wire --help` ✅ (--surfaces, --dry-run, --home)
  - `mi-mcp init --help` ✅ (confirmed alias — identical output to `setup --help`)
- This is a real, reproducible gap: argparse subparsers exist and work, but the top-level parser's help doesn't advertise them (likely missing `metavar`/subparser help text registration in `__main__.py`)

**Why This Matters Most For Novices:**
- A user who does the "responsible" thing (`mi-mcp --help` before guessing at commands) gets NO indication that `setup`/`doctor`/`status`/`wire`/`init` exist
- The README says "run `mi-mcp setup`" — works ONLY if user trusts the README over `--help`
- Easy fix: this is almost certainly a one-line argparse fix (add subparser help / `dest` display)

**Resolution:** 0.2.5 now displays a full "setup commands" block in top-level --help including descriptions and a portal link. One of the clearest fixes in the changelog from a novice UX standpoint.

**Note for PRD report:** Also documents `vscode` as a new surface, and adds the portal link directly in the --help output — excellent onboarding addition.

---

### I5: Python Version Requirement Still Not in README
**Status:** OPEN  
**Priority:** HIGH  
**Impact:** Even after doc update (2026-06-09), Python >=3.10 requirement not explicit in README excerpt  
**Discovered:** 2026-06-05 (I2), confirmed still missing 2026-06-09

**Details:**
- We empirically confirmed Python >=3.10 requirement via PyPI metadata (Phase 2 Path B)
- Updated README (2026-06-09) still does not explicitly state this in the Quick Start
- This remains the most likely silent-failure point for new users on macOS (default Python 3.9.6)

**Owner:** Documentation  
**Next Action:** Add "Requires Python >=3.10" prominently to Quick Start section, with venv setup snippet

---

## Improvements (Feature/Doc)

### IMP1: Setup Wizard Clarity
**Status:** BACKLOG  
**Priority:** HIGH  
**Improvement:** mi-mcp setup should:
- Explain what it's doing at each step
- Handle API key retrieval as part of flow
- Verify successful connection before completing
- Provide "next steps" recommendation based on host

**Owner:** MCP Engineer  
**Next Action:** Review current setup wizard UX

---

### IMP2: First-Time User Workflow
**Status:** BACKLOG  
**Priority:** HIGH  
**Improvement:** Create clear "hello world" for new users:
- Capture a simple memory
- Ask a query about it
- See results with source citation

**Owner:** Documentation/UX  
**Next Action:** Design and test starter workflow guide

---

### IMP3: Host Detection & Verification
**Status:** BACKLOG  
**Priority:** MEDIUM  
**Improvement:** Auto-detect host and confirm:
- Detect which host is running the MCP
- Surface clear confirmation in UI/CLI
- Link to host-specific setup if needed

**Owner:** MCP Engineer  
**Next Action:** Implement host detection in setup

---

## Testing Artifacts

### TA1: Novice User Report - PyPI Friction
**Status:** COMPLETED  
**Artifact:** /generated-output/onboarding-report-1-initial-friction.md  
**Date:** 2026-06-05

### TA2: Novice User Report - Repository Review
**Status:** IN PROGRESS  
**Artifact:** /generated-output/onboarding-report-2-repo-review.md  
**Date:** 2026-06-05

---

## Resolutions Log

*(To be updated as items are resolved)*
