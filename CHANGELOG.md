# Changelog

All notable changes to `memoryintelligence-mcp` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/); this project uses [Semantic Versioning](https://semver.org/).

## [0.2.3] — 2026-07-22

### Fixed — Claude Desktop actually launches: the sandbox P0 finally ships (#1135)
The Desktop direct-interpreter wire (merged 2026-07-07) never reached PyPI — the
published 0.2.2 was built from an earlier commit under the same version number,
so `mi-mcp wire`/`setup` on the released package kept writing a Desktop entry
pointing at `run-mi-mcp.sh`, which Claude Desktop's macOS sandbox refuses to
exec. Result: the server never completes the MCP handshake, Desktop kills it at
its 60s timeout ("Server disconnected"), and no tools register — while `doctor`
reported green. This release cuts current `main`, which carries:

- **`wire` emits `{command: <python>, args: ["-m", "mi_mcp"]}` for Desktop** —
  a real Mach-O binary the sandbox allows; the key still never touches the
  config (resolved in-process from the Keychain, time-boxed at 5s).
- **`doctor` now FAILS when the Desktop entry points at a shell script**, with
  the exact remediation printed — the escalated user's hours of debugging
  become one red line.
- **The launcher's Keychain read is time-boxed** (perl alarm, 5s) for the
  surfaces that keep the wrapper (Code/Cursor): a Keychain ACL authorization
  prompt (e.g. after a venv/binary change) can no longer hang the launch
  until the host's timeout.
- Config backup before overwrite (P1) + startup marker line (P2) from the
  onboarding-report arc, also previously unreleased.

**To pick this up:** `pip install -U memoryintelligence-mcp` (or `uv tool
upgrade`), then **re-run `mi-mcp wire`**, then fully quit + reopen Claude
Desktop. `mi-mcp doctor` must show `[✓] desktop entry sandbox-launchable`.

## [0.2.2] — 2026-07-07

### Fixed — `explain` now surfaces the score breakdown through `mi_ask` (MI#482)
`mi_ask`'s `explain` argument was silently dropped: the MCP output shaper projected
every hit down to `{umo_id, summary, source, score}` and discarded the per-signal
`scores` breakdown unconditionally, so passing `explain: "human"` (or any level) had
no observable effect and ranking couldn't be diagnosed (e.g. the entity-channel
contribution). The shaper now **keeps the `scores` block** (semantic/keyword/entity/
recency) on each hit whenever `explain` is anything other than `none`; the default
lean shape is unchanged, so token cost is unaffected unless you ask for the breakdown.

## [0.2.1] — 2026-07-05

### Fixed — one shared vault with the MemorySpace Desktop (MI#653)
`0.2.0` noted that `mi-mcp` defaulted its local `.umo` vault to `~/MemoryIntelligence`
while the MemorySpace Desktop app reads `~/Somewhere` — two separate folders, so a
memory captured or backfilled through `mi-mcp` never showed up in the Desktop app, and
told you to point `MI_VAULT` there by hand. This release makes that automatic.

- **`mi-mcp wire` / `setup` now point the vault at `~/Somewhere`** — they write
  `export MI_VAULT="$HOME/Somewhere"` into the launcher (`run-mi-mcp.sh`), so `mi-mcp`
  and the Desktop resolve **one** vault out of the box. It's a default only: it's
  guarded so an explicit `MI_VAULT` you set yourself (env or MCP config) still wins.
- **`paths.py`'s default is unchanged** (`~/MemoryIntelligence`) — existing installs are
  never silently moved; the unification happens the next time you run `wire`.
- **`mi-mcp doctor` reports the effective vault** and whether it matches the Desktop's,
  reading the value the launcher will actually use — so the check goes green once wired.

**To pick this up:** upgrade, then **re-run `mi-mcp wire`** (upgrading alone doesn't
rewrite the launcher), and restart Claude Desktop. `mi-mcp doctor` should show the vault
as `~/Somewhere`. Files already backfilled into `~/MemoryIntelligence` by `0.2.0` stay
where they are — move them into `~/Somewhere` (or re-run `backfill`) if you want them in
the app; `doctor` flags the mismatch.

## [0.2.0] — 2026-07-04

### Added — the local vault (Path A), previously built on `main` but never released
The published `0.1.12` shipped as a thin cloud client; the entire local-vault stack
landed on `main` afterward **under the same version number** and was never cut into a
release. This release publishes it (release-hygiene fix — no new code, just a version
bump over what `main` already carried).

- **`backfill --execute` now writes the local vault** (`cli.py`): the cloud → local
  migration re-embeds each memory locally, encrypts to the owner's key, and writes a
  signed `.umo`. The prior published build's `--execute` was a dry-run stub.
- **Offline reads** — `local_index.py` + `localreads.py` + `indexer.py`: a flat-numpy
  cosine index over the decrypted vault, mirroring the hosted ranking, so `mi_ask` works
  network-free (needs the `[local]` extra: `cryptography` + `numpy`).
- **`mi-mcp index {build,stat,path}`** — build/inspect the local vector index.
- **On-device redaction** (`scrub.py`) applied on the local read path.
- **`embedder.py`** — local bge-small embeddings for backfill + query.
- Note (MI#653): `mi-mcp` still defaults its vault to `~/MemoryIntelligence`; the
  MemorySpace Desktop vault is `~/Somewhere`. Until `wire`/`setup` sets
  `MI_VAULT=~/Somewhere`, point it there manually so the two surfaces share one vault.

## [0.1.12] — 2026-06-16

### Fixed
- **The MCP client now retries on transient failures instead of failing the
  first time the API is slow to wake.** The Railway `sdk-api` is a single small
  instance that intermittently cold-starts or saturates (CPU-bound embedding +
  pgvector rerank), and the client had a hard 30s budget with **no retry** — the
  source of the "MCP keeps timing out" reports. Now:
  - **Idempotent reads** (`mi_ask`, `mi_list`, `mi_explain`, `mi_verify`,
    `mi_match`, account lookup) retry up to 2× on a read timeout or a transient
    5xx (502/503/504), with exponential backoff (0.5s, 1.0s).
  - **Writes** (`mi_capture`, `mi_upload`, `mi_forget`, batch) are **not**
    read-retried — a timeout after the request body landed could double-apply.
  - **Connection-level retries** (transport `retries=2`) cover the cold-start
    `ConnectError` case for *every* verb, since no body is re-sent when the
    connection never established.

  This is a client-side reliability mitigation. The durable fix is local-vault
  reads (no network round-trip on recall) — tracked separately.

## [0.1.11] — 2026-06-16

### Added
- **`mi_upload` is now part of the default tool surface** — file-capture parity
  with the API. The MCP previously exposed only text capture; `mi_upload` now
  ships in the visible tool set and its description covers the full capture
  matrix: structured files (csv/tsv/xlsx/json → typed claims), documents
  (pdf/docx), images (→ OCR), and audio/video (→ transcription).

## [0.1.10] — 2026-06-15

### Changed
- **`mi_forget` now enforces its `confirm=true` gate.** The tool advertised a
  confirmation step but the handler ignored it and deleted immediately. It now
  returns `confirmation_required` (and deletes nothing) unless `confirm=true` is
  passed — so an injected or accidental call can't silently destroy a memory.
  (Pairs with the API-side delete fix: deletes now actually persist.)

### Fixed
- **Release CI is green on the public mirror again.** `test_contract_endpoints.py`
  asserted the monorepo's `api/contract/openapi.json` exists; the mirror is a
  subtree of `mcp-server/` only, so that file is absent and the test errored on
  every release. It now **skips** when the contract isn't present (monorepo-only
  test), instead of failing the mirror's build.

## [0.1.9] — 2026-06-13

### Added
- **`--capture-anywhere` for `wire`/`setup`** — opt capture in for **Claude Desktop**,
  which has no project folder for the per-folder consent gate to match. Sets
  `MI_MCP_OPT_IN_ALL=1` on the **desktop entry only**; Claude Code and Cursor keep
  per-folder consent. Default **off** (explicit opt-in is the ownership stance).
  `--no-capture-anywhere` turns it back off; a plain re-wire preserves the choice.
  Desktop captures are tagged `source=claude-desktop` (new `MI_DEFAULT_SOURCE`) so
  they're identifiable apart from project captures, and `wire` prints a consent
  warning while it's on. **No API key is ever written to a config.**

### Changed
- **Proactive-capture guidance tightened** — the server instructs the host to
  capture *sparingly* (the user's own durable facts — not third parties' details,
  venting, or half-formed ideas), reducing over-capture.

### Fixed
- **Launch wrapper self-heals a stale binary path** — `run-mi-mcp.sh` tries the
  wire-time path first, then re-resolves via `PATH` and the common install dirs,
  and exits with one actionable error if none resolve — instead of failing
  silently when a reinstall/upgrade moves the `mi-mcp` binary.

## [0.1.8] — 2026-06-10

### Changed
- **The MCP server id is now `memoryintelligence`** (was `memory-intelligence`).
  This is the id under `mcpServers` in your config and the name in
  `claude mcp add …`. It now matches the brand/package token everywhere else
  (`MemoryIntelligence`, `memoryintelligence-mcp`) instead of splitting the word
  with a dash.
- **Auto-migration:** `mi-mcp wire`/`setup` removes the old `memory-intelligence`
  entry from every surface (file configs **and** `claude mcp remove`) before
  adding the new id, so an upgrade leaves no duplicate/orphan. `mi-mcp doctor`
  flags a leftover legacy entry and tells you to re-wire. **Action on upgrade:
  run `mi-mcp wire` once.** (Hand-edited configs: rename the key yourself.)

## [0.1.7] — 2026-06-09

### Changed
- **Hidden files now live under `~/.memoryintelligence/`** (was `~/.mi/`), matching
  the visible `~/MemoryIntelligence/` vault — one on-brand namespace:
  - launcher → `~/.memoryintelligence/mcp/run-mi-mcp.sh`
  - capture opt-in allowlist → `~/.memoryintelligence/mcp/opt-in-paths`
  - keyfile (the Keychain fallback) → `~/.memoryintelligence/.env`

  `mi-mcp setup`/`wire` write the new layout and migrate an existing
  `~/.mi/opt-in-paths` forward non-destructively. The legacy `~/.mi/` launcher
  and `~/.mi-env` keyfile are still **read** for one release, so existing
  installs keep working until you re-run `wire`. `paths.py` is now the single
  source of truth for the layout (it previously declared the new layout while the
  CLI still wrote `~/.mi/` — that split is fixed here).

### Added
- **README "Names & locations" map** — explains the package / command / server-id
  names (`memoryintelligence-mcp` / `mi-mcp` / `memory-intelligence`) and where
  every file lives, so the naming no longer looks arbitrary.

## [0.1.6] — 2026-06-09

### Security
- **`doctor` no longer prints any bytes of your API key.** `mi-mcp doctor`
  previously logged an 11-character prefix of the resolved key (CodeQL
  `py/clear-text-logging-sensitive-data`, high). It now reports only *where*
  the key resolved from (Keychain / keyfile / env), never the key itself.

### Added
- **MCP ↔ API contract tests** (`tests/test_api_contract.py`, run in CI — not
  shipped in the published package) — pin that every client method sends only
  parameter values the API accepts (`explain`, `pii_handling`,
  `retention_policy`, `scope`), so an API enum/type change can never silently
  422 a real call. This is the general form of the `explain` bool→enum bug
  fixed in 0.1.3.

### Changed
- Internal code-quality cleanups (narrowed a few broad `except` clauses, removed
  an unused import). No behavior change.

## [0.1.5] — 2026-06-05

### Added
- **`mi-mcp setup` (alias `mi-mcp init`)** — one-command onboarding. It prompts for your API key (hidden input), stores it **outside every config** (macOS Keychain, or a `chmod 600 ~/.mi-env` keyfile on Linux/Windows or via `--store file`), runs `wire`, opts the current directory in for capture, then runs `doctor`. Collapses the old five-step quickstart (and the macOS-only Keychain incantation) into a single frictionless command. The secure model is unchanged: **no API key is ever written into an MCP config** — the launcher resolves it at runtime.
- `mi-mcp --version` flag (matches the bug-report template).

### Changed
- **Branding:** the product is now written as **MemoryIntelligence** (no space) throughout the docs, package metadata, and agent-facing strings.
- **README** rewritten to lead with a 30-second copy-paste start, an honest "what works today" matrix (Tier 0 + `mi_capture`/`mi_ask`/`mi_list` work; audio/image upload is not yet functional on the backend; the local `.umo` vault is a later release), and cross-platform setup guidance (the macOS-only `security` command is no longer presented as the only way).

## [0.1.4] — 2026-06-04

### Added
- **Tier 0 agent-mediated memory** — the server now ships an MCP `instructions` field, surfaced to the host agent at initialize time. The agent proactively calls `mi_ask` to recall relevant memories before answering and `mi_capture` to persist durable decisions/facts/preferences — on every host (Claude Desktop, Cursor, Claude Code), with no file hooks required. Recalled content is explicitly framed as untrusted data.

### Changed
- `X-MI-Source: mcp` is now documented as the **context-aware PII-redaction signal**: the API redacts PII for the agent/MCP surface, while the owner's reads in the developer portal are returned raw. (Server-side enforcement ships with the privacy fix; the MCP already sends the signal.)
- User-Agent now derives from the package version instead of a hardcoded string (was stuck at `0.1.0`).

## [0.1.3] — 2026-06-04

### Fixed
- `mi_ask` `explain` parameter type mismatch (HTTP 422). The tool schema exposed `explain` as a boolean, but the API (`/v1/memories/query`) expects an enum string (`none`/`human`/`audit`/`full`). `explain: true` was rejected with "Input should be 'none', 'human', 'audit' or 'full'". The schema is now the enum (matching `mi_match`), and the client coerces any legacy boolean (`true`→`full`, `false`→`none`) and omits the no-op `none` so an illegal boolean can never reach the API. Regression-tested in `tests/test_ask_explain.py`.

## [0.1.2] — 2026-06-03

### Added
- `uvx memoryintelligence-mcp` support — a `memoryintelligence-mcp` console-script alias so the package name resolves as a runnable command (zero-install one-liner).
- Adoption docs: per-client setup (Claude Desktop, Claude Code, Cursor), tool table with example prompts, badges, `LICENSE`, `CHANGELOG`, `CONTRIBUTING`.

## [0.1.1] — 2026-06-03

### Security
- Removed the networked transports (`sse`/`streamable-http`) — they shipped without inbound auth/TLS/CORS. Selecting one now exits with an error. Eliminates the DNS-rebinding / browser-CSRF / unauthenticated attack surface. Networked transports return in a later release with OAuth 2.1 + TLS.
- Consent-gate path matching now canonicalizes with `os.path.realpath` (resolves symlinks before allowlist comparison) — closes a path-traversal/symlink-bypass class.
- Added MCP tool annotations (`title`, `readOnlyHint`, `destructiveHint`) to all tools; `mi_forget` is flagged destructive.

## [0.1.0] — 2026-06-01

### Added
- Initial release. MCP server exposing MemoryIntelligence as tools: `mi_capture`, `mi_ask`, `mi_list` (default surface); `MI_MCP_FULL=1` exposes the full 10-tool surface.
- `mi-mcp wire` / `doctor` / `status` — wires the server into Claude Desktop & Code with **no API key in any config** (the launcher resolves `MI_API_KEY` from the macOS Keychain at launch).
- Capture consent gate (`~/.mi/opt-in-paths`); destructive-op confirmation; untrusted-data framing on retrieved content.
