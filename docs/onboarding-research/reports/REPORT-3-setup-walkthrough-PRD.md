# REPORT-3: Setup Walkthrough — PRD (Build Mode)
**Type:** Product Requirements Document  
**Audience:** MCP Engineer implementing improvements  
**Phase:** Phase 2 Path B — Full setup from pip install through first verified healthy state  
**Version tested:** memoryintelligence-mcp 0.2.5  
**Date:** 2026-07-28  
**Status:** VERIFIED via live testing

---

## Executive Summary

The Path B (with API key) setup flow reaches a healthy, wired, working state in v0.2.5. However, four friction points emerged that reduce confidence and increase abandonment risk, particularly for users setting up via an AI agent (Claude Code). The issues span: Python version silent failures, environment variable config that silently doesn't apply, doctor output that conflates errors with informational notices, and the absence of any documented "Claude Code agent setup" path for secure API key handling.

---

## Friction Point F1: Python Version Requirement — Silent Failure

### Priority: HIGH
### Category: Onboarding Blocker

**What happens:**
A user with macOS system Python (3.9.6) runs `pip install memoryintelligence-mcp` or `python3 -m pip install memoryintelligence-mcp`. The package fails to install. The error message is not "your Python is too old" — it either says "package not found" (if pip isn't on PATH) or produces a requires-python error that is easy to miss.

**Root cause:**
- Package requires `python >= 3.10`
- macOS ships Python 3.9.6 as system default
- `requires_python` is only communicated via a Shields.io badge in the README — no prose statement

**User experience (tested):**
1. `pip: command not found` → user has no signal about Python version
2. `python3 -m pip install memoryintelligence-mcp` → "Package not found" message
3. Novice user reads this as: "Is this package real? Is it private? Did I mistype the name?"
4. Actual cause: wrong Python version — never surfaced

**Resolution path (tested, works):**
```bash
brew install python@3.12
python3.12 -m venv .venv
.venv/bin/pip install memoryintelligence-mcp
```

**Requirements:**
1. Add explicit prose statement to README Quick Start: `> Requires Python 3.10 or higher. Check: python3 --version`
2. Add venv + Homebrew fallback snippet to Quick Start for macOS users
3. Confirm whether `pip` install with correct Python version shows a clear "requires-python" error — if yes, prioritize surfacing that error path; if not, consider adding a Python version check to `mi-mcp setup` startup

**Acceptance Criteria:**
- [ ] README Quick Start contains prose statement: "Requires Python ≥3.10"
- [ ] README includes venv setup snippet for macOS users on system Python
- [ ] `mi-mcp setup` startup prints a clear error if Python <3.10 detected

---

## Friction Point F2: `mi-mcp --help` Subcommand Visibility

### Priority: RESOLVED in v0.2.5 (documented for history)
### Category: CLI Discoverability

**What happened (v0.1.5–v0.1.6):**
`mi-mcp --help` showed only transport flags, zero subcommands. A novice user running help first (correct behavior) would conclude setup doesn't exist.

**Resolution in v0.2.5:**
```
setup commands (run these first, not shown above):
  mi-mcp setup     store your API key + wire + opt-in + verify (one command)
  mi-mcp wire      wire into Claude Desktop / Code / Cursor
  mi-mcp doctor    verify install, key resolution, and wiring
  mi-mcp status    show wired surfaces + opt-in allowlist

Get a key at https://memoryintelligence.io/portal, then run `mi-mcp setup`.
```
Excellent addition. Portal link in --help is particularly valuable. ✅

**No further action required.** Tracking for completeness.

---

## Friction Point F3: `doctor` Symbol Conflation — `[✗]` for Errors and Non-Configurations

### Priority: MEDIUM
### Category: Output Clarity / Trust

**What happens:**
On a clean, healthy install, `mi-mcp doctor` output shows **three `[✗]` symbols**:

```
[✓] mi-mcp binary       .../.venv/bin/mi-mcp
[✗] binary on PATH       .venv/bin not on PATH — run export PATH=... (or uv tool update-shell)
[✓] wrapper rendered     ~/.memoryintelligence/mcp/run-mi-mcp.sh
[✓] wrapper executable
[✓] MI_API_KEY resolvable   source=keychain
[✓] opt-in allowlist     1 entries
[✓] vault path           /Users/gabrielle/Somewhere  [wrapper (wired)]
[✓] desktop wired        ...claude_desktop_config.json
[✓] desktop entry sandbox-launchable
[✓] code wired           ~/.claude.json
[✗] cursor wired         (not wired)
[✗] vscode wired         (not wired)

  healthy ✓
```

**Problem:**
- `cursor wired [✗]` and `vscode wired [✗]` are expected non-configurations — defaults don't include Cursor/VSCode
- `binary on PATH [✗]` is advisory, not blocking — the wrapper handles launch; `uv tool update-shell` suggestion assumes uv is installed (it isn't for venv users)
- Overall `healthy ✓` verdict contradicts three visible `[✗]` marks — novice reads this as three failures + one overall pass = confusing

**Requirements:**
1. Introduce a third symbol for informational/expected-not-configured states. Options: `[~]` (not applicable), `[·]` (neutral), `[i]` (info), or dim the row color differently.
2. Use `[✗]` ONLY for states that require user action to fix before the tool functions correctly
3. The PATH advisory (`uv tool update-shell`) should check whether uv is installed before suggesting it; fall back to `export PATH="$(dirname $(which mi-mcp)):$PATH"` for venv users
4. Consider making Cursor/VSCode rows appear only when `--surfaces cursor` or `--surfaces vscode` was used during wire

**Acceptance Criteria:**
- [ ] Three-symbol system implemented: pass / info / fail
- [ ] Clean healthy install shows zero `[✗]` symbols (all expected non-configurations use info symbol)
- [ ] PATH advisory doesn't suggest `uv` commands to non-uv users
- [ ] `doctor --verbose` option exists for showing all rows including expected non-configurations

---

## Friction Point F4: `.env` Config Silently Ignored When Using Keychain

### Priority: HIGH
### Category: Configuration / Security Trap

**What happens:**
User follows documented approach: write `MI_MCP_FULL=1` to `~/.memoryintelligence/.env` to enable extended tools. Restart Claude. Extended tools do not appear. No error. No warning. Silent failure.

**Root cause (traced to source):**
The wrapper script sources `.env` conditionally:
```bash
for __mi_envf in "$HOME/.memoryintelligence/.env" "$HOME/.mi-env"; do
  if [[ -z "${MI_API_KEY:-}" && -f "$__mi_envf" ]]; then
    set -a; . "$__mi_envf"; set +a
  fi
done
```
When Keychain resolves `MI_API_KEY`, the condition `[[ -z "${MI_API_KEY:-}" ]]` is FALSE. The `.env` file is never sourced. `MI_MCP_FULL=1` never reaches the process.

Additionally, Claude Desktop runs `python3.12 -m mi_mcp` directly (v0.2.3 macOS sandbox fix) — the wrapper is not involved at all. Even if this were fixed in the wrapper, Desktop users would still need to configure the json env block.

**Security trap:**
The documented "best practice" (use Keychain) causes the documented "extra config" approach (`.env`) to silently fail. Users who correctly secured their setup are punished with a broken config path, with no feedback.

**Workaround applied by tester:**
- Claude Code: re-added MCP entry with `MI_MCP_FULL=1` via `claude mcp add -e MI_MCP_FULL=1 ...`
- Claude Desktop: added `"MI_MCP_FULL": "1"` to `env` block in `claude_desktop_config.json`

**Requirements:**
1. **Wrapper fix (option A):** Source `.env` unconditionally for ALL env vars, not just as a key fallback. Move key-fallback logic to a separate step:
   ```bash
   # Source .env first for any config vars
   for __mi_envf in "$HOME/.memoryintelligence/.env" "$HOME/.mi-env"; do
     if [[ -f "$__mi_envf" ]]; then set -a; . "$__mi_envf"; set +a; fi
   done
   # Then resolve key if not already set
   if [[ -z "${MI_API_KEY:-}" ]]; then
     MI_API_KEY="$(... keychain ...)"
   fi
   ```

2. **Wrapper fix (option B):** Keep current logic but add explicit warning if `.env` exists but is being skipped. For example: `# MI_MCP_FULL in .env is only applied when Keychain is not in use`

3. **Docs fix (required regardless of wrapper fix):** Document the correct way to set `MI_MCP_FULL=1` for each setup type:
   - Keychain users (Claude Code): `claude mcp add -e MI_MCP_FULL=1 ...`
   - Keychain users (Desktop): add to `env` block in `claude_desktop_config.json`
   - File-key users: `.env` approach works

4. **Clarify `.env`'s role** in all documentation: it is a key fallback, not a general env config file (as currently described).

**Acceptance Criteria:**
- [ ] Wrapper sources `.env` for all vars regardless of Keychain state, OR
- [ ] Wrapper logs a warning when `.env` is skipped due to Keychain
- [ ] README documents how to set `MI_MCP_FULL=1` for both Keychain and file-key users
- [ ] `.env` documentation explicitly states its role as key-fallback vs. general config

---

## Friction Point F5: Agent-Assisted Setup — API Key Security Dilemma

### Priority: MEDIUM
### Category: Documentation Gap / Use Case Coverage

**What happens:**
User is setting up MI MCP while inside an AI agent session (Claude Code). They're following docs that say "run `mi-mcp setup`". The interactive prompt asks for the API key. The user now faces a fork:

- **Option A:** Type key into agent prompt → key appears in agent's context/transcript → against product's security model
- **Option B:** Exit agent flow, store key in Keychain out-of-band, re-enter agent flow for `mi-mcp wire` → secure, but not documented, breaks the "one command" narrative

Neither path is documented for this increasingly common setup scenario.

**Workaround used (tested):**
```bash
# Run this in your OWN terminal (not the agent's terminal):
read -s K; security add-generic-password -a "$USER" -s "MI_API_KEY" -w "$K" -U; unset K
# Then tell the agent: "run mi-mcp wire"
```

**Requirements:**
1. Add a "Setting up via Claude Code or another AI agent" section to README
2. Include the out-of-band Keychain storage command (copy-pasteable, one-liner)
3. Instruct agent users to run `mi-mcp wire` (not `mi-mcp setup`) after key is stored
4. Consider adding a `mi-mcp setup --skip-key-prompt` flag that assumes key is already in Keychain

**Acceptance Criteria:**
- [ ] README includes "Agent-Assisted Setup" section with Keychain pre-storage instructions
- [ ] `mi-mcp setup` or `mi-mcp wire` handles "key already in Keychain" case gracefully with confirmation output
- [ ] Security guidance clearly frames why key-in-agent-context is bad

---

## Summary Table

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| F1 | Python version not in prose | HIGH | OPEN |
| F2 | Setup hidden from --help | RESOLVED | ✅ v0.2.5 |
| F3 | doctor [✗] conflation | MEDIUM | OPEN |
| F4 | .env silently ignored (Keychain) | HIGH | Workaround applied |
| F5 | Agent setup key dilemma | MEDIUM | OPEN |

---

## What Works Well (Preserve These)

- `mi-mcp wire` output: clear, step-by-step, shows exactly what changed, backs up configs ✅
- `mi-mcp wire` uses `claude mcp add -s user` (official CLI method) — not raw JSON editing ✅
- `wire` confirms "no API key written to any config" explicitly in output ✅
- `wire` includes "next steps" list directly in output ✅
- Config backup created before modification (`*.mi-bak`) ✅
- `doctor` source=keychain confirmation — user knows key resolution path ✅
- `healthy ✓` verdict visible even with advisory items ✅
- Portal link in `--help` output (v0.2.5) ✅
