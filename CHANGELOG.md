# Changelog

All notable changes to `memoryintelligence-mcp` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/); this project uses [Semantic Versioning](https://semver.org/).

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
