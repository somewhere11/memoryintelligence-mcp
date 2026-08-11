# Canon: Single Source of Truth

## What is MemoryIntelligence MCP?

**Verified:**
- MCP server enabling AI assistants to maintain persistent, searchable memory across sessions
- Integrates with Claude Desktop, Claude Code, and Cursor
- Open source: https://github.com/somewhere11/memoryintelligence-mcp
- Available on PyPI: memoryintelligence-mcp

## Installation Method

**Verified:**
```bash
pip install memoryintelligence-mcp
mi-mcp setup
```

## Core Tools

**Verified:**
- `mi_capture`: Save decisions, facts, and preferences to memory
- `mi_ask`: Semantically search memories with citations to sources
- `mi_list`: Browse recently saved memories

## Extended Tools (Opt-in)

**Verified (available with MI_MCP_FULL=1):**
- `mi_explain`
- `mi_verify`
- `mi_forget`
- `mi_batch`
- `mi_upload`
- `mi_match`
- `mi_account`

## Key Features

**Verified:**
- Automatic memory recall via agent instructions in compatible hosts
- Automatic capture of important information without explicit prompting
- PII redaction on surfaces
- Local execution (subprocess over stdio, no open network ports)
- Key protection (macOS Keychain or encrypted local files)
- Opt-in capture in whitelisted directories
- Confirmation gates for destructive operations
- Untrusted data framing to prevent injection attacks

## Requirements

**Inferred from docs:**
- Python (major versions compatible)
- Free API key from memoryintelligence.io/portal
- One of: Claude Desktop, Claude Code, or Cursor

## Current Test User State

**Inferred:**
- User has MI API key already obtained
- User is testing as beta user
- Focus: Onboarding ease and value-add evaluation

## Setup Process (From Documentation Search)

**Partially Verified from docs:**
- Setup command includes API key storage step
- Setup includes verification of functionality (exact output not documented)
- Setup auto-configures "your assistant" (suggests host auto-detection, but unclear)
- Automatic memory recall happens at task start in compatible hosts
- Extended tools (MI_MCP_FULL=1) are listed separately from core tools (suggests optional, but not explicit)

## Known Friction Points

**From Initial Attempts:**
- PyPI page has client-side rendering issues (not accessible to initial setup)
- GitHub repository is functional and contains complete documentation

**From Documentation Search (Phase 1.5):**
- Setup sequence (when to get API key vs when to install) not explicitly stated
- Which host setup auto-detects is unclear
- What "successful setup" looks like (console output) not shown in docs
- Extended tools necessity for starters not explicitly stated
- How to visually observe auto memory recall not documented

**From Path A Testing (Pre-Setup, No Key):**
- API key portal is referenced but not explained step-by-step
- No walkthrough of account creation process
- No documentation of key format, delivery method, or generation time
- No validation method for key before running pip install
- No fallback if portal is unavailable

**From Path B Testing (With Key, Installation Phase) — UPDATED:**
- Package is on PyPI as version 0.1.5 (released 2026-06-05, Beta)
- **Verified: Python >=3.10 required** — system Python 3.9.6 is too old (NOT in docs)
- Package installs successfully inside Python 3.12 venv via `python3 -m pip install`
- Homebrew Python 3.12 needed as bridge (not documented as prerequisite)
- `mi-mcp` and `memoryintelligence-mcp` both installed as binaries
- 35 dependencies installed including mcp, httpx, pydantic, uvicorn, cryptography

**Setup Command (Verified from --help):**
- Subcommand: `mi-mcp setup`
- **Not visible in top-level `mi-mcp --help`** — only discoverable by knowing to try `mi-mcp setup --help`
- Accepts `--api-key` flag for non-interactive key entry OR prompts interactively
- Default surfaces: `desktop,code` (both Claude Desktop and Claude Code)
- Cursor must be specified explicitly with `--surfaces desktop,code,cursor`
- Stores key in macOS Keychain (auto) or `~/.mi-env` file on other platforms
- Opts in current directory for memory capture by default

**Q2 Answered (Host Selection):**
- Both Claude Desktop and Claude Code configured by default
- Cursor requires explicit opt-in via `--surfaces` flag
- No host auto-detection needed — it configures all defaults simultaneously

**Q1 Answered (API Key Timing):**
- Key entered during `mi-mcp setup` (either via flag or interactive prompt)
- Can install package first, then run setup — install does not require key

## CLI Updates (From GitHub README, 2026-06-09 review)

**Verified (from updated README):**
- New subcommands documented: `mi-mcp doctor`, `mi-mcp status`, `mi-mcp wire --dry-run`
- `mi-mcp doctor` — validates configuration and connectivity
- `mi-mcp status` — shows wired surfaces and opt-in allowlist
- `mi-mcp wire --dry-run` — previews changes without committing
- Setup variants now explicitly documented:
  - `mi-mcp setup --surfaces desktop,code,cursor`
  - `mi-mcp setup --store file`
  - `mi-mcp setup --no-opt-in`

---

## 🎯 MAJOR UPDATE: Full PyPI Description Retrieved (v0.1.6, via JSON API)

**Method:** Fetched `https://pypi.org/pypi/memoryintelligence-mcp/json` directly (bypasses the bot-challenge that blocks the HTML project page). This returns the FULL `long_description` (14,231 chars) — the complete README as rendered on PyPI.

**METHODOLOGY FINDING:** Our earlier WebFetch-based GitHub README fetches were being summarized/truncated by WebFetch's internal model. The raw JSON API description reveals significantly more detail than any prior fetch surfaced. **For future doc reviews, prefer raw content retrieval over WebFetch summarization when completeness matters.**

### NEW VERSION AVAILABLE: 0.1.6 (we have 0.1.5 installed)
- Releases: 0.1.0 → 0.1.1 → 0.1.4 → 0.1.5 → 0.1.6
- `requires_python: >=3.10` (confirmed in metadata; in README only via Shields.io Python-versions badge, not prose)

### Q1 — FULLY ANSWERED (API Key Timing)
> "`mi-mcp setup` (alias `mi-mcp init`) runs the whole flow interactively: 1. **prompts for your API key** (hidden input)..."

- Sequence confirmed: install package FIRST (no key needed), THEN run `mi-mcp setup`, which prompts for key interactively (hidden input, like a password prompt)
- Key is obtained from portal beforehand, entered when setup asks

### Q2 — FULLY ANSWERED (Host Selection)
> "**wires** the server into Claude Desktop + Claude Code (`--surfaces` to choose `desktop,code,cursor`)"

- Default = Claude Desktop + Claude Code, no user choice needed for the common case
- Cursor is opt-in via `--surfaces desktop,code,cursor`
- No "detection" happens — it just configures both default targets' config files directly

### Q3 — FULLY ANSWERED (Setup Verification)
> "5. **verifies** everything with `doctor`"
> "`mi-mcp doctor` — checks binary, wrapper, key resolvability (prefix only), wiring, opt-in"

- Setup's last step automatically runs the equivalent of `doctor`
- `mi-mcp doctor` can also be run standalone anytime to re-check status
- `mi-mcp status` shows wired surfaces + opt-in allowlist (lighter-weight than doctor)

### Q4 — FULLY ANSWERED (Extended Tools Necessity)
> "The three core tools (`mi_capture`/`mi_ask`/`mi_list`) are **all you need to get value today**. Everything else is opt-in via `MI_MCP_FULL=1`"

- Explicitly confirmed: extended tools are NOT required for beginners
- `MI_MCP_FULL=1` exposes 10 total tools (3 core + 7 extended): mi_explain, mi_verify, mi_forget, mi_batch, mi_upload, mi_match, mi_account
- Tools outside active surface are **enforced not callable** (security boundary, not just hidden)

### Q5 — FULLY ANSWERED (Auto Memory Recall)
> "**It remembers on its own (no extra setup)** — The server ships agent instructions... a compatible host will, on its own: **recall first** — call `mi_ask` when you begin a task or refer to something from before... **capture what matters** — call `mi_capture` when you state a decision, fact, or preference worth keeping."

- Concrete example given: Save "Remember we picked Postgres for billing — we needed transactions" → New session, ask "What did we decide about the billing database?" → Assistant auto-recalls and cites the memory
- Works immediately after wiring, "no hooks, no extra config"
- Capture still requires per-directory opt-in (set during setup)
- Recalled content always treated as untrusted data (security framing)

---

## New Details Discovered (v0.1.6 description)

### Environment Variables (Full Table)
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MI_API_KEY` | Yes | — | Resolved by launcher from Keychain/`~/.mi-env`, never set inline |
| `MI_BASE_URL` | No | `https://api.memoryintelligence.io` | API base URL |
| `MI_MCP_FULL` | No | off | `1` = all 10 tools; else 3 core |
| `MI_TRANSPORT` | No | `stdio` | Only stdio supported this version |
| `MI_HOST` / `MI_PORT` | No | `127.0.0.1` / `8100` | Reserved for future networked transports |
| `MI_DEFAULT_SCOPE` | No | `user` | Governance scope |
| `MI_DEFAULT_RETENTION` | No | `meaning_only` | Retention policy |
| `MI_DEFAULT_PII_HANDLING` | No | `extract_and_redact` | PII handling default |

### Key Storage & Resolution Order
1. Inherited environment variable
2. macOS Keychain (`security find-generic-password -s MI_API_KEY`)
3. `~/.mi-env` (chmod 600), gitignored

**Explicit warning in docs:** "Do NOT put your API key in a config file" — addresses a common but insecure pattern shown in other MCP guides.

### Manual/Cross-Platform Setup
- macOS: `security add-generic-password` + `mi-mcp wire`
- Linux/Windows: `~/.mi-env` keyfile + `mi-mcp wire`
- Or plain env var export

### "Honest Status" Table (v0.1.5, transparency about beta limitations)
| Capability | Status |
|---|---|
| Proactive memory (auto recall+capture) | ✅ Works on all 3 hosts |
| `mi_capture`, `mi_ask`, `mi_list` | ✅ Works |
| `mi_upload` (PDF) | ✅ Works (MI_MCP_FULL=1) |
| `mi_upload` (audio/image) | 🚧 Not yet functional — coming |
| Local `.umo` vault (offline) | 🔭 Planned |

This "Honest Status" framing is itself notable — it's a doc pattern other tools rarely use, and it directly preempts "is this fully working?" anxiety.

### Quick Start is Now Concrete (Not Abstract)
```bash
pip install memoryintelligence-mcp     # or: pipx install memoryintelligence-mcp
mi-mcp setup                           # paste your key once — wires everything
# restart your assistant, then just talk to it:
#   "remember we picked Postgres for billing — we needed transactions"
#   (new session)  "what did we decide about the billing database?"
```
This single block essentially answers the "what does success/value look like" question with a concrete example a novice can mentally simulate.

---

## Version History (Full Changelog, Retrieved 2026-07-28)

| Version | Date | Key Change |
|---|---|---|
| 0.1.0 | 2026-06-01 | Initial release |
| 0.1.5 | 2026-06-05 | `mi-mcp setup` one-command onboarding introduced |
| 0.1.6 | 2026-06-09 | Removed API key printing from `doctor` (security fix) |
| 0.1.7 | 2026-06-09 | Config files migrated to `~/.memoryintelligence/` |
| 0.1.8 | 2026-06-10 | Server ID changed: `memory-intelligence` → `memoryintelligence` |
| 0.1.9 | 2026-06-13 | `--capture-anywhere` flag introduced for Claude Desktop |
| 0.1.10 | 2026-06-15 | `mi_forget` confirmation gate enforced |
| 0.1.11 | 2026-06-16 | `mi_upload` moved to DEFAULT surface (no longer requires MI_MCP_FULL=1) |
| 0.1.12 | 2026-06-16 | Retry logic with exponential backoff on read failures |
| 0.2.0 | 2026-07-04 | Local vault stack released; `backfill --execute`; `mi-mcp index` commands |
| 0.2.1 | 2026-07-05 | Vault location unified to `~/Somewhere` (matches MemorySpace Desktop) |
| 0.2.2 | 2026-07-07 | `explain` score breakdowns fixed |
| 0.2.3 | 2026-07-22 | **CRITICAL macOS fix**: sandbox refused shell scripts; wire now emits Python command |
| 0.2.4 | 2026-07-24 | Knowledge receipts in `mi_ask`; `mi_verify` visible by default; 3-layer injection defense |
| 0.2.5 | 2026-07-24 | Capture fixed for GUI/remote surfaces; I3 FIXED (setup commands listed in --help) |

## Current Installed Version
**0.2.5** in `/Users/gabrielle/projects/mcp-test/.venv/`

## CLI State (0.2.5 Verified)

**I3 RESOLVED: `mi-mcp --help` now shows setup commands:**
```
setup commands (run these first, not shown above):
  mi-mcp setup     store your API key + wire + opt-in + verify (one command)
  mi-mcp wire      wire into Claude Desktop / Code / Cursor
  mi-mcp doctor    verify install, key resolution, and wiring
  mi-mcp status    show wired surfaces + opt-in allowlist

Get a key at https://memoryintelligence.io/portal, then run `mi-mcp setup`.
```

**New in 0.2.5 setup:**
- `--surfaces` now includes `vscode` as a new option (default still `desktop,code`)
- `--capture-anywhere` / `--no-capture-anywhere` flag now in setup
- Key storage default path updated: `~/.memoryintelligence/.env` (was `~/.mi-env`)

## Portal Documentation (2026-07-28 Browser Inspection)

**Current status:** Invite-only ("Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now.")

**Signup flow:** Email + optional name/purpose + password (8+ chars) → email verification (link or 6-digit code) → key revealed on Dashboard

**Key format:** `mi_sk_beta_...` (confirmed via portal Quickstart: `export MI_KEY="mi_sk_beta_your_key_here"`)

**Key lifecycle:** Never / 30 / 90 / 365 days expiration. Revoke, rotate supported. Multiple keys per workspace. Up to 3 workspaces in beta.

**Key re-revelation:** Keys can be revealed again from Keys tab ("Reveal" button). Contradicts "You won't be able to see it again" copy in creation modal.

**Health endpoint:** `https://api.memoryintelligence.io/health` — documented in portal Quickstart but NOT in README.

**Portal features beyond key management:**
- MI Search (in-browser semantic search with channel/date filters)
- Build Summary + Run MI Ask (synthesize selected memories in browser)
- "Ask from memory" dialog (floating chat UI)
- PII detection dialog (redact/keep before capture)
- Usage analytics (per-key, workspace-level)
- Team management (Viewer/Member/Admin roles)
- Plans and pricing (Tier 01 $29, Tier 02 $49, Tier 03 $99 — all free during beta)

**Plans (all free during beta):**
| Tier | Launch | UMOs | Key Features |
|------|--------|------|-------------|
| 01 Capture | $29/mo | 500 | Manual only, 1 user |
| 02 Automate | $49/mo | 5,000 | Auto capture, signal rules, ML feedback |
| 03 Control | $99/mo | Unlimited | Admin, compliance — coming soon |

## Tool Behavior — Full Surface Documented (Session 2, 2026-07-28)

### mi_forget
- Requires `confirm: true` (without it: confirmation_required prompt, nothing deleted)
- Soft-delete: immediately hidden, permanent purge after 7-day grace window
- Returns: `{forgotten: true, umo_id, deleted_at, receipt}` where receipt is SHA256 hash
- Ownership-checked: can only delete your own UMOs
- **GDPR-compliant** — deletion receipt kept permanently as proof

### mi_upload
- Accepts: csv/tsv/xlsx/json/jsonl, pdf/docx/txt/md, png/jpg/gif/webp, audio/video
- `.md` files: categorized as `media_type: "data"`, `source: "upload-data"`
- Very fine-grained chunking: 17KB .md file → 205 child claims
- `origin_asserted` fields all UNKNOWN for `.md` (no embedded metadata reader for .md; upload path uses browser multipart, not local filesystem xattr access)
- `extracted_text_length` reflects actual parsed content (slightly less than file_size_bytes)
- No topics/entities extracted at parent level for .md files (different from mi_capture)
- Returns `claim_count` field (total per-claim children) alongside child_ids array

### mi_ask with explain modes
- `explain=none` — results only, no per-field scores
- `explain=human` and `explain=audit` — both return `scores: {semantic, keyword, entity, recency}` breakdown
- No visible additional fields distinguish human vs. audit in JSON response (server-side difference may exist)
- Scoring formula: `rerank/composite-v1 sem.60-kw.15-ent.15-rec.10` (60% semantic, 15% keyword, 15% entity, 10% recency)
- **Display order ≠ composite score**: results ordered by relevance ranking; shown scores are for transparency, not ordering

## MI_MCP_FULL=1 Activation — Corrected Method (2026-07-28 Session 2)

**Initial approach (incorrect for Keychain users):** Writing `MI_MCP_FULL=1` to `~/.memoryintelligence/.env`

**Why it failed:**
- Wrapper script (`run-mi-mcp.sh`) only sources `.env` when `MI_API_KEY` is still empty after Keychain lookup
- Since Keychain resolves the key, `.env` is conditionally skipped
- Claude Desktop bypasses the wrapper entirely (v0.2.3 direct Python launch)

**Correct method — set in host config directly:**

Claude Code (`~/.claude.json` via CLI):
```bash
claude mcp add memoryintelligence /path/to/run-mi-mcp.sh -e MI_MCP_FULL=1 -s user
```

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
"env": {
  "MI_VAULT": "/Users/gabrielle/Somewhere",
  "MI_MCP_FULL": "1"
}
```

**Status as of 2026-07-28:** Both configs updated. Restart required before extended tools (mi_explain, mi_batch, mi_match, mi_account) will appear.

**Issue logged:** I8 in registry.md — wrapper conditional sourcing is a documentation gap for Keychain users.

## Opt-In Nesting — VERIFIED (2026-07-28 Session 2)

**Claim:** `/Users/gabrielle/projects/` (with trailing slash) nests all subdirectories.

**Verification:** `config.py` line 163 uses `os.path.realpath(os.path.expanduser(p))` — `realpath` strips trailing slash. The prefix check `cwd_abs.startswith(base + os.sep)` correctly matches all subdirectories regardless of trailing slash in stored path.

**Status: VERIFIED ✅** — `/Users/gabrielle/projects/` covers `/projects/mcp-test`, `/projects/somewhere-content-world`, and any future subdirectory.

## Remaining Open Items (Re-Assessed)

- **I2/I5 (Python version):** Requirement exists in metadata + Shields badge, but NOT in prose. A novice reading the markdown body top-to-bottom would still miss it. Badge-only communication is insufficient for accessibility/skimmers.
- **I3 (setup hidden from --help):** Still unverified against actual installed CLI. README confirms `mi-mcp init` is an alias for `setup` — also worth checking if `--help` surfaces aliases.
- **I4 (PyPI page bot-challenge):** Confirmed root cause = CDN bot-challenge (`Client Challenge` page), not a packaging defect. Likely affects ALL PyPI project pages for automated/non-JS clients, not specific to this package.
- **NEW:** We have 0.1.5 installed; 0.1.6 is latest. Should upgrade to test against current version.
