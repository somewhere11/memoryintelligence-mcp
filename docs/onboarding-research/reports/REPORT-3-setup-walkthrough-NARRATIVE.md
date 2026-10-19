# REPORT-3: Setup Walkthrough — Narrative (Documentation Mode)
**Type:** Empathy-Driven User Perspective  
**Audience:** Technical writers improving public-facing docs  
**Phase:** Phase 2 Path B — Full setup from pip install through first verified healthy state  
**Version tested:** memoryintelligence-mcp 0.2.5  
**Date:** 2026-07-28

---

## As If I Was This Person

I'm a developer who found MemoryIntelligence on GitHub. I've used pip before, I know what a terminal is, but I've never set up an MCP server. The README looks clean. The one-command promise ("pip install → mi-mcp setup → done") is what got me interested. I have my API key ready. Let's go.

---

### The First Wall: pip Doesn't Work

My first try is exactly what the docs say:

```
pip install memoryintelligence-mcp
```

Nothing. `pip: command not found`.

Okay, I know about `python3 -m pip`. I try that:

```
python3 -m pip install memoryintelligence-mcp
WARNING: Package(s) not found: memoryintelligence-mcp
```

My first thought is that I typed the name wrong. I go back to the README and copy-paste it. Same result.

My second thought is that this is a private package or something in beta that isn't published yet. I'm ready to give up.

What I don't know — what the docs never told me — is that my Python is too old. macOS ships with Python 3.9.6. This package requires 3.10. That's the entire issue. But I have zero signal pointing me there.

A power user would look at the Shields.io badge in the README — there's one that says "Python 3.10+." But I'm reading the Quick Start, not the badge bar. And even if I did read the badge, "Python 3.10+" next to a green checkmark isn't the same as "Requires Python ≥3.10 — your system Python 3.9 won't work, here's how to fix it."

**What the docs need here:**

A single sentence, in the Quick Start, before the install command:

> **Prerequisites:** Python 3.10 or higher. (`python3 --version` to check.) On macOS, you may need: `brew install python@3.12 && python3.12 -m venv .venv && . .venv/bin/activate`

That's it. One block. I'd have been unblocked in 30 seconds.

---

### The Homebrew Detour

With some searching (outside the docs), I found that Homebrew can install newer Python. I already had Homebrew. I ran:

```bash
brew install python@3.12
python3.12 -m venv .venv
.venv/bin/pip install memoryintelligence-mcp
```

It worked. The package installed. I could see `mi-mcp` in my path.

This detour took me maybe 10 minutes, and it involved googling and a bit of trial and error. A true novice — someone who's never touched Homebrew — would likely have stopped here. There's a drop-off point between "pip install fails" and "okay, now install Homebrew and Python 3.12" that the docs need to bridge.

---

### The `--help` Surprise (a Good One)

Once installed, I did what any cautious developer does: `mi-mcp --help`.

In v0.2.5 this was actually reassuring:

```
setup commands (run these first, not shown above):
  mi-mcp setup     store your API key + wire + opt-in + verify (one command)
  mi-mcp wire      wire into Claude Desktop / Code / Cursor
  mi-mcp doctor    verify install, key resolution, and wiring
  mi-mcp status    show wired surfaces + opt-in allowlist

Get a key at https://memoryintelligence.io/portal, then run `mi-mcp setup`.
```

This is excellent. The portal link is there. The subcommands are explained. I know exactly what to do next.

**Note for writers:** In older versions (v0.1.5–0.1.6), this block was completely absent. `--help` showed only transport server flags. A user running `--help` in those versions would have concluded setup doesn't exist and given up before ever finding the command. This is fixed now — but the documentation for older version users (or anyone referencing older guides) should note the upgrade path.

---

### The API Key: Where It Gets Tricky

I'm running Claude Code as my AI assistant. I want the agent to help me with the setup. This is where things got weird.

The docs say: run `mi-mcp setup`, it'll prompt for your API key. But if I let Claude Code run that command, the API key would appear in Claude's context. The docs themselves say "never put your key in a config file." The spirit of that guidance applies here: never paste your key somewhere it'll be logged or visible to an AI assistant.

So I'm stuck. I can either:
1. Let Claude run the setup and leak my key into its session → clearly wrong
2. Run it myself in a separate terminal window, typing the key interactively → fine, but now why am I using Claude for this at all?
3. Store the key in Keychain first, then let Claude run `mi-mcp wire` instead of `mi-mcp setup` → secure, but I had to figure this out myself

Option 3 is the right answer. But there's no documentation pointing me there. And the command to store a key in Keychain without it showing up in your shell history is not something most developers know off the top of their head.

**What the docs need here:**

A "Setting up via an AI agent" section, something like:

> **Using Claude Code or another AI coding assistant?**
> Don't run `mi-mcp setup` through your agent — the interactive key prompt would expose your API key in the agent's context. Instead:
> 1. In **your own terminal** (not the agent's), store your key securely:
>    ```bash
>    read -s K; security add-generic-password -a "$USER" -s "MI_API_KEY" -w "$K" -U; unset K
>    ```
> 2. Then ask your agent to run: `mi-mcp wire`
> 3. Restart your assistant.

That's it. A dozen lines of documentation would have saved me a genuine head-scratch moment and kept my key secure.

---

### Wire Output: Actually Wonderful

Once the key was in Keychain and I ran `mi-mcp wire`, the output was exactly what I needed:

```
wiring memoryintelligence MCP server
  wrapper → /Users/gabrielle/.memoryintelligence/mcp/run-mi-mcp.sh
           execs /path/to/.venv/bin/mi-mcp
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

This output did everything right. It told me what changed, where, what got backed up, and what to do next. It even explicitly called out that no key was written anywhere — exactly the reassurance I needed after the security concerns above.

This is how every CLI setup command should feel. Keep this.

---

### Doctor Output: Three Red Xs on a Healthy Install

After restarting and running `mi-mcp doctor`, I got this:

```
[✓] mi-mcp binary
[✗] binary on PATH
[✓] wrapper rendered
[✓] wrapper executable
[✓] MI_API_KEY resolvable   source=keychain
[✓] opt-in allowlist
[✓] vault path
[✓] desktop wired
[✓] desktop entry sandbox-launchable
[✓] code wired
[✗] cursor wired   (not wired)
[✗] vscode wired   (not wired)

  healthy ✓
```

My first reaction: three failures. My second reaction: but it says healthy. My third reaction: is "healthy" correct despite those three failures?

The answer is yes — all three `[✗]` items are either advisory or expected. I didn't ask to wire Cursor or VSCode. The binary-on-PATH item is a "nice to have" for running commands from your own terminal, but the wrapper handles launch just fine without it.

But a novice reading this doesn't know that. The symbol `[✗]` means failure. Three of them creates doubt, and the overall `healthy ✓` verdict feels like a contradiction.

The fix is simple: use different symbols for "you might want to address this someday" vs. "this is broken and must be fixed." Even a muted color difference would help. As-is, it's easy to leave this page unsure if you're in a good state.

---

### The Invisible .env Problem

After setup, I wanted to enable the extended tools (mi_explain, mi_batch, etc.). The README mentions `MI_MCP_FULL=1`. I wrote it to `~/.memoryintelligence/.env`. Restarted. Nothing changed.

It took source-code inspection to discover what happened: the wrapper script only reads `.env` as a fallback when the API key isn't in Keychain. Since I'm using Keychain (the right, secure choice), the wrapper skips `.env` entirely. `MI_MCP_FULL=1` never reaches the process.

I wasn't supposed to figure this out by reading the wrapper script. I was supposed to have documentation that told me:

> **Note for Keychain users:** Because your API key is resolved via Keychain rather than `.env`, additional config like `MI_MCP_FULL=1` must be set in your host's MCP config, not in `.env`.
>
> For Claude Code: `claude mcp add memoryintelligence ... -e MI_MCP_FULL=1`  
> For Claude Desktop: add `"MI_MCP_FULL": "1"` to the `env` block in `claude_desktop_config.json`

The `.env` file currently has an ambiguous documented role — it looks like a general config file, but it only functions as a key fallback. That ambiguity needs to be surfaced.

---

## Overall Assessment

The setup flow, once you're past the Python version wall, is genuinely good. `mi-mcp wire` is excellent. The v0.2.5 `--help` improvement is a real win. The Keychain-first security model is well-designed.

The three rough edges that could meaningfully reduce onboarding drop-off:
1. **Python version** — one prose line + venv snippet in Quick Start
2. **Agent-assisted setup** — one new section with the Keychain command and "then run wire"
3. **MI_MCP_FULL=1 for Keychain users** — one note clarifying the host-config approach

All three are purely documentation changes. No code needed. They would together cover the single most common onboarding failure pattern: "I did what the docs said, why isn't it working?"
