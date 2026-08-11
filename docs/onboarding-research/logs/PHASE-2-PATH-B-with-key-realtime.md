# Phase 2: Real-Time Testing Report - Path B (With API Key)

**Date:** 2026-06-05  
**Test Scenario:** Novice user with API key proceeds through full setup and first workflow  
**Model:** Think out loud; document friction and success in real-time  
**Status:** IN PROGRESS

---

## Step 0: Pre-Flight Check

**What I Have:**
- ✅ API key ready (provided by user)
- ✅ GitHub documentation reviewed
- ✅ Understanding of core tools: mi_capture, mi_ask, mi_list
- ✅ Terminal/command line access
- ✅ Python installed (assumed)

**What I'm About to Do:**
1. Run: `pip install memoryintelligence-mcp`
2. Run: `mi-mcp setup`
3. Verify setup succeeded
4. Run first `mi_capture` command
5. Run first `mi_ask` command

**My Confidence Level:** 🟡 MEDIUM
- The docs say setup is "one command" (good)
- But I don't know what that command outputs (gap)
- I don't know if I need to configure anything after install (gap)
- I'm assuming everything "just works" (risky assumption)

**Questions Before I Start:**
- Should I activate a virtual environment or use system Python?
- Will `pip install` work on first try, or are there dependencies?
- Will `mi-mcp setup` prompt me for the API key, or does it search for it in my environment?
- After setup, how do I test that it actually worked?

**My Internal Monologue:**
> "Okay, I have a key. I have the docs. The installation looks simple. Let me try this and see what happens. The docs say setup is one command, so I'm expecting: pip install → mi-mcp setup → done. If it's more complicated, that's a friction point."

---

## Step 1: Install via pip

**What I'm Doing:**
Running: `pip install memoryintelligence-mcp`

**What I Expect:**
- pip downloads the package
- Installs dependencies
- Completes with "Successfully installed memoryintelligence-mcp-X.X.X"
- Takes ~30-60 seconds

**What Happens Next (My Assumption):**
- The `mi-mcp` command becomes available in my shell
- I can run `mi-mcp setup` next

**Status:** [ATTEMPTING - requires actual command execution]

**Friction Tracking:**
- If pip install fails, what troubleshooting steps are documented? 
- Are there platform-specific issues (macOS vs Linux vs Windows)?
- Will the docs help me if something goes wrong?

---

## Step 2: Run Setup Command

**What I'm Doing:**
Running: `mi-mcp setup`

**What I Expect (From Docs):**
The docs say: "The setup command completes configuration in one step: stores your API key securely, configures your assistant, enables the current directory for memory capture, and verifies functionality."

Breaking that down, I expect:
1. Prompt for API key (or auto-detect from environment?)
2. Detect which assistant I'm using (Claude Desktop? Code? Cursor?)
3. Configure current directory for memory
4. Run verification test
5. Print success message

**What I'm Uncertain About:**
- Will it prompt me for input, or do I pass arguments? (e.g., `mi-mcp setup --key=xxxxx` or interactive prompt?)
- How does it know which host I'm using?
- What's the "verify functionality" step? Is it automated or manual?
- What does success look like?

**My Internal Monologue:**
> "The docs say 'one command' but I'm not sure if that means one command line, or one interactive process. If it's interactive, I'll need to know what to input. If it takes arguments, they should be documented."

**Status:** [PREPARING - awaiting pip install success]

---

## Step 3: Verify Setup Success

**What I'm Looking For:**
- Clear success message (e.g., "Setup complete!" or "MCP server ready")
- Confirmation of API key storage (e.g., "Key stored securely in Keychain")
- Confirmation of host detection (e.g., "Configured for Claude Code")
- Instructions for next steps

**What Would Indicate Failure:**
- Error messages
- Silent completion (unclear if success or failure)
- Partial configuration (some steps done, some not)
- No verification output

**My Internal Monologue:**
> "If the setup completes silently, I won't know if it worked. I need clear feedback. After this, I want to know: 'Is my API key stored? Is my host configured? Can I start using the memory tools?'"

**Status:** [PENDING - awaiting setup execution]

---

## Step 4: First Test - Capture a Memory

**What I'll Do:**
Run something like: `mi_capture "My first memory: I prefer detailed explanations"`

**What I Expect:**
- Command accepts the memory text
- Prints confirmation (e.g., "Memory saved")
- Returns to prompt
- Execution time <1 second

**What Would Be Confusing:**
- Silent success (no confirmation)
- Cryptic output (IDs or technical info I don't understand)
- Unexpected prompts or requirements
- Error messages I can't interpret

**My Internal Monologue:**
> "This is the moment where I see value. If I run a command and my memory is saved, that's tangible. That's when I start believing this tool works."

**Status:** [PENDING - awaiting setup verification]

---

## Step 5: First Test - Query a Memory

**What I'll Do:**
Run something like: `mi_ask "What did I say about my preferences?"`

**What I Expect:**
- Command returns my saved memory
- Shows it found the relevant memory
- Displays the text I saved
- Maybe shows a confidence score or source

**What Would Indicate Value:**
- Got back the exact memory I saved (proof of search working)
- Got back related memories even if I used different wording (semantic search)
- Can see citations to sources

**What Would Be Confusing:**
- Returns nothing (did it fail silently?)
- Returns unrelated memories (search isn't working?)
- Complex output format I don't understand
- No clear "here's your answer"

**My Internal Monologue:**
> "If this works, I'll immediately see the value: I can save something and get it back. That's genuinely useful. This is where I'll form my opinion on whether this tool is worth using."

**Status:** [PENDING - awaiting first memory capture]

---

## Unknowns to Resolve During Path B

1. Does `mi-mcp setup` accept arguments or require interactive input?
2. How does the host detection work (auto-detect vs. manual)?
3. What does successful setup output look like?
4. Can I actually run mi_capture and mi_ask commands directly, or do they work differently?
5. How long do commands take?
6. What happens if I run setup twice (overwrite keys?)
7. Can I see my memories somewhere (in a file, in the MCP system, etc.)?

---

## LIVE DISCOVERIES - Path B Execution

### Step 1: Installation Attempt

**Attempt 1: `pip install memoryintelligence-mcp`**
- **Result:** ❌ FAILED
- **Error:** `pip: command not found`
- **Friction:** Direct pip command not available in environment

**Attempt 2: `python3 -m pip install memoryintelligence-mcp`**
- **Result:** ❌ FAILED  
- **Error:** `WARNING: Package(s) not found: memoryintelligence-mcp`
- **Friction:** Package not found on PyPI (in this environment)

**What I Checked for Alternatives:**
- Checked GitHub for additional installation methods
- Found: docs mention pip, pipx, uvx, and source install
- Attempted pipx: ❌ Not available
- Attempted uvx: ❌ Not available
- Environment: Python 3.9.6 available, but limited tools

### 🚨 CRITICAL FRICTION POINT

**Problem:** All documented installation methods fail to work in this environment.

**User Experience (Novice):**
1. Read docs: "pip install memoryintelligence-mcp"
2. Try: nothing happens / package not found
3. Reaction: "Is this project real? Do I need special access? Did I misunderstand?"
4. Attempts alternatives from docs: also fail
5. Next action: ???

**What a Novice Would Do:**
- Check if they misread the package name (did)
- Check GitHub for alternative instructions (found, tried, failed)
- Check for setup.py or requirements.txt to install from source (not attempted yet)
- Give up and ask for help (high likelihood)

**Documentation Gap:** No troubleshooting guide for installation failures

---

### Next Steps

**Option A:** Clone repo and attempt source installation
**Option B:** Continue narration about what WOULD happen if installation succeeded
**Option C:** Document this as critical blocker for Path B

**Current Status:** ✅ UNBLOCKED VIA ENVIRONMENT FIX

**What Unblocked It:**
- System Python 3.9.6 too old (requires >=3.10) — not documented
- Homebrew was available → installed Python 3.12 via Homebrew
- Created venv: `python3.12 -m venv .venv`
- Install succeeded: `Successfully installed memoryintelligence-mcp-0.1.5`

**Novice User Assessment:**
- 🔴 A true novice without Homebrew knowledge would be stuck here
- 🔴 Python version requirement NOT mentioned in docs (major gap)
- 🟡 With Homebrew + guidance it was solvable (3 steps, ~2 minutes)

---

### Step 1b: Verify Installation & Discover Setup Command

**Ran:** `mi-mcp --help`
**Result:** ❌ FRICTION — `setup` subcommand NOT shown in top-level help
- Only shows transport flags (stdio, sse, port, host, log-level)
- A novice would see this and conclude there is NO setup command
- Docs say `mi-mcp setup` — but `--help` doesn't surface it

**Ran:** `mi-mcp setup --help`
**Result:** ✅ Setup command EXISTS and is comprehensive

```
One command: store your key, wire hosts, opt in this dir, verify.

Options:
  --api-key API_KEY     provide the key non-interactively (else prompted)
  --store {auto,keychain,file}  where to keep the key
  --surfaces SURFACES   comma list of: desktop, code, cursor (default: desktop,code)
  --opt-in DIR          directory to allow captures from (default: current dir)
  --no-opt-in           don't opt any directory in
  --home HOME           override HOME (for testing)
```

**Answers Discovered from Setup Help:**
- Q2 (Host Selection): DEFAULT is `desktop,code` — both Claude Desktop AND Claude Code configured automatically
- Q1 (API Key Timing): Can be passed via `--api-key` flag OR prompted interactively
- Q3 (Setup Verification): Description says "verify" is built in

**New Friction Found:**
- Setup subcommand hidden from main `--help` output
- A novice who runs `mi-mcp --help` would miss the setup entirely

---

**Next Update:** After Step 2 (running mi-mcp setup with API key)

---

## Steps 2–4: Keychain, Wire, Doctor — COMPLETED (2026-07-28, v0.2.5)

### Versioning Note
Between initial install (0.1.5) and this step, package progressed through 0.1.6 → 0.2.5. We upgraded at each stage and tested continuously. Full changelog documented in canon.md.

### Step 2: API Key — Keychain Method (Out-of-Band)

**Path taken:** Manual Keychain storage (user ran command in own terminal):
```bash
read -s K; security add-generic-password -a "$USER" -s "MI_API_KEY" -w "$K" -U; unset K
```

**Why this path:** User wanted to use Keychain securely without key appearing in agent session.

**Verification (agent-side):**
```
security find-generic-password -s "MI_API_KEY" -a "$USER"
→ keychain: login.keychain-db
→ acct: gabrielle
→ svce: MI_API_KEY
✅ Keychain entry found
```

**Onboarding Finding — Agent Setup Dilemma:**
When an AI agent (Claude Code) is doing your setup, the interactive `mi-mcp setup` prompt creates a real security fork:
- Option A: Paste key into agent session (key appears in context/transcript) — against the product's own advice
- Option B: Do the Keychain step yourself out-of-band — keeps key secure, but requires user to leave the agent flow

This is not documented anywhere in the current docs. Worth a dedicated note for users setting up via Claude Code specifically.

---

### Step 3: Wire Output (actual console)

```
wiring memoryintelligence MCP server
  wrapper → /Users/gabrielle/.memoryintelligence/mcp/run-mi-mcp.sh
           execs /Users/gabrielle/projects/mcp-test/.venv/bin/mi-mcp
           resolves MI_API_KEY at launch (no key in configs)
  desktop  .../claude_desktop_config.json  [add]  ·  capture-anywhere off
           backed up prior config → claude_desktop_config.json.mi-bak
  code     via `claude mcp add -s user` (official; avoids racing ~/.claude.json)
           ✓ added via claude CLI

  ✓ no API key written to any config — resolved from the Keychain at launch

Next steps:
  1. opt in a project directory
  2. restart Claude
  3. mi-mcp doctor
```

**What worked well:**
- Config backed up before modification ✅ (safe to re-run)
- Clear confirmation that no key was written to config ✅
- `mi-mcp wire` uses `claude mcp add -s user` — official CLI method, not raw JSON editing ✅
- "Next steps" listed directly in output ✅

---

### Step 4: Doctor Output (actual console, Q-NEW-2 RESOLVED)

```
  [✓] mi-mcp binary       .../mcp-test/.venv/bin/mi-mcp
  [✗] binary on PATH       .venv/bin not on PATH — run export PATH=... (or uv tool update-shell)
  [✓] wrapper rendered     ~/.memoryintelligence/mcp/run-mi-mcp.sh
  [✓] wrapper executable
  [✓] MI_API_KEY resolvable   source=keychain
  [✓] opt-in allowlist     1 entries
  [✓] vault path           /Users/gabrielle/Somewhere  [wrapper (wired)]
  [✓] desktop wired        .../claude_desktop_config.json
  [✓] desktop entry sandbox-launchable
  [✓] code wired           ~/.claude.json
  [✗] cursor wired         (not wired)
  [✗] vscode wired         (not wired)

  healthy ✓
```

**Analysis:**
- `[✗] binary on PATH` — uses `[✗]` symbol but is NOT a failure. Wrapper handles launch; binary PATH only matters for running `mi-mcp` from terminal. The suggested fix (`uv tool update-shell`) implies uv is installed, which we don't have. **Friction: novice will see [✗] and panic.**
- `cursor wired [✗]` and `vscode wired [✗]` — expected (not wired by default), correctly labeled as "(not wired)" vs an error
- `source=keychain` — key resolution confirmed ✅
- `sandbox-launchable` — 0.2.3 macOS fix confirmed working ✅
- `healthy ✓` — overall system confirmed operational

**Friction: `[✗]` symbol used for both real errors and expected non-errors**
A novice sees three `[✗]` items and reads them as three failures. The doctor should distinguish:
- `[✗]` = actual problem requiring action
- `[~]` or `[i]` = informational / expected non-configuration

---

**Status: READY FOR FIRST USE**

Remaining: restart Claude Desktop + Claude Code, then test mi_capture / mi_ask workflow.

---

## Step 5: Diagnosing MI_MCP_FULL=1 — Root Cause Found (2026-07-28, Session 2)

### The Symptom
After writing `MI_MCP_FULL=1` to `~/.memoryintelligence/.env` and restarting Claude, the 4 extended tools (mi_explain, mi_batch, mi_match, mi_account) did NOT appear. Only 6 default tools active.

### Root Cause #1: Wrapper Conditional Sourcing
```bash
for __mi_envf in "$HOME/.memoryintelligence/.env" "$HOME/.mi-env"; do
  if [[ -z "${MI_API_KEY:-}" && -f "$__mi_envf" ]]; then
    set -a; . "$__mi_envf"; set +a
  fi
done
```
The wrapper only sources `.env` if `MI_API_KEY` is still empty. Since Keychain resolves the key, `MI_API_KEY` is populated and the condition `[[ -z "${MI_API_KEY:-}" ]]` is FALSE. The `.env` file is never sourced. `MI_MCP_FULL=1` silently ignored.

**This is not documented anywhere in the setup docs.** A user following the documented pattern of "store extra config in .env" will get no error but no effect.

### Root Cause #2: Claude Desktop Bypasses Wrapper Entirely
Desktop config uses `python3.12 -m mi_mcp` directly (v0.2.3 macOS sandbox fix). The wrapper script is not involved. The Desktop's own `env` block in `claude_desktop_config.json` is the ONLY place to set env vars for Desktop.

### Fix Applied
**Claude Code** (`~/.claude.json`):
```bash
claude mcp remove memoryintelligence -s user
claude mcp add memoryintelligence /Users/gabrielle/.memoryintelligence/mcp/run-mi-mcp.sh -e MI_MCP_FULL=1 -s user
```
Result: `env: {"MI_MCP_FULL": "1"}` now present in Claude Code MCP config ✅

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
Added `"MI_MCP_FULL": "1"` to the existing `env` block alongside `MI_VAULT` ✅

### What This Means for Documentation
The current README describes `.env` as the place to put env config, but this is only true for users who:
1. Don't use Keychain (key is in .env), AND
2. Are using a surface that goes through the wrapper

For anyone using Keychain (the recommended, secure approach), the correct way to enable MI_MCP_FULL is to set it in each host's native config — NOT in .env.

**Gap:** No documentation of this. The `.env` file's role is ambiguous (key fallback vs. general config). Users following the docs will be confused when MI_MCP_FULL=1 in .env has no effect.

**Pending:** Restart Claude Code + Claude Desktop for extended tools to appear.

---

## Step 6: Opt-in Nesting — CONFIRMED with Source Verification

User's assumption: `/Users/gabrielle/projects/` (with trailing slash) nests ALL subdirectories.

**Source code verification** (`config.py`, line 163):
```python
base = os.path.realpath(os.path.expanduser(p))
if cwd_abs == base or cwd_abs.startswith(base + os.sep):
    return True
```

`os.path.realpath()` normalizes trailing slashes — `/Users/gabrielle/projects/` → `/Users/gabrielle/projects` (no slash). Then the prefix match works correctly. Tested in Python:
```python
>>> import os
>>> base = os.path.realpath('/Users/gabrielle/projects/')
>>> base
'/Users/gabrielle/projects'
>>> '/Users/gabrielle/projects/mcp-test'.startswith(base + '/')
True
```

**Confirmed: The `/projects/` entry (with or without trailing slash) covers all subdirectories.** ✅
