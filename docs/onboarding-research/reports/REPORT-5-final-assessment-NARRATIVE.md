# REPORT-5: Final Assessment — Narrative (Documentation Mode)
**Type:** Empathy-Driven User Perspective  
**Audience:** Technical writers improving public-facing docs  
**Scope:** Full onboarding study — PyPI discovery through first workflow  
**Version tested:** 0.1.5 → 0.2.5  
**Date:** 2026-07-28

---

## The Arc of the Experience

If I had to describe the MemoryIntelligence MCP onboarding in one sentence: *the tool itself is good, but you have to survive the docs to find out.*

The core loop — capture something, ask about it later, see it recalled with attribution — works exactly as advertised. Once you're through setup, the value is immediate and tangible. But the path to "through setup" has four real walls, and the docs currently don't mention any of them.

---

## Wall One: Python (Invisible to the Docs, Loud in Practice)

My first run at installation failed. I got "package not found." I reread the README three times. I copy-pasted the package name. Nothing.

The problem was Python 3.9.6 — the version macOS ships with. The package needs 3.10.

I didn't learn this from the docs. I learned it the hard way, through trial and error and a Google search. The README has a badge that says "Python 3.10+" but badges are visual decoration — they're not the same as a sentence that says "if this doesn't install, run `python3 --version` first."

The fix is genuinely one sentence. Something like:

> **Requires Python 3.10+.** Check with `python3 --version`. On macOS you may need to install a newer Python: `brew install python@3.12` then `python3.12 -m venv .venv && . .venv/bin/activate`.

That sentence prevents the first wall entirely. Without it, some percentage of users gives up before even seeing the setup command.

---

## Wall Two: The AI Agent Situation

I was setting up via Claude Code. The docs say run `mi-mcp setup` and it'll prompt for your API key.

But I was inside an AI agent session. If I paste my API key into a prompt that Claude Code can see, that key is in the agent's context. The product's own docs say not to put keys in config files. The spirit of that applies here: don't put your key somewhere an AI assistant can read it.

The docs don't address this. They describe a flow designed for humans typing directly in a terminal. They don't mention what to do when the "human typing in a terminal" is actually an AI assistant running on your behalf.

The workaround (store the key in Keychain yourself first, then ask the agent to run `mi-mcp wire` instead of `mi-mcp setup`) is correct, elegant, and completely undocumented. I figured it out. A less determined user would have either leaked their key or given up.

This is increasingly common. More and more developers first touch new tools by asking an AI to help them set it up. The docs need a "Setting up via an AI agent" path. It's not complicated — it's one Keychain command and a note that says "then ask your agent to run `wire`, not `setup`."

---

## Wall Three: The Doctor's False Alarm

After setup, I ran `mi-mcp doctor` to confirm everything was healthy. I saw three `[✗]` symbols.

My brain: three failures.

The actual situation: one advisory (binary not on your PATH, but that's fine because the wrapper handles it), plus two informational notices about Cursor and VSCode not being wired (I didn't ask for them, so of course they're not wired).

The overall verdict at the bottom said `healthy ✓`. But the three red marks contradicted it.

In the end, everything was fine. But for a moment, I wasn't sure. I wondered if I needed to take action. I considered re-running setup. I thought maybe I'd broken something during the API key workaround.

Good health monitoring software is like a good medical report: it tells you clearly what's a problem and what's just "this test wasn't done because you didn't ask for it." The current `doctor` output doesn't make that distinction. `[✗]` should mean "broken" and there should be a different symbol — `[~]`, `[-]`, or even just the item in a lighter color — for "not configured by choice."

This is a one-line change in the doctor output. It would save every new user the "wait, is my install broken?" moment.

---

## Wall Four: The Config That Did Nothing

After getting comfortable with the basic tools, I wanted to enable the extended ones. The README mentions `MI_MCP_FULL=1`. I put it in `~/.memoryintelligence/.env`. Restarted. Nothing happened.

No error. No warning. The extended tools simply didn't appear.

I spent time on this. Eventually I traced through the wrapper script and found the issue: the wrapper only reads `.env` as a fallback when Keychain doesn't have the API key. Since I'm using Keychain (the right, secure approach), the wrapper skips `.env` entirely. `MI_MCP_FULL=1` never reaches the process.

The fix was to put the env var in the host config instead — Claude Code's MCP entry, Claude Desktop's json config. That worked. But I shouldn't have needed to read a bash script to figure that out.

The docs need one note: 

> **Using Keychain?** Set `MI_MCP_FULL=1` in your host config instead of `.env`. For Claude Code: `claude mcp add memoryintelligence ... -e MI_MCP_FULL=1`. For Claude Desktop: add `"MI_MCP_FULL": "1"` to the `env` block in `claude_desktop_config.json`.

The `.env` file's actual role — key fallback for users who don't have Keychain — should also be stated plainly, so users know what it is and isn't for.

---

## The Feature That Wasn't Promoted: Provenance

After I got through setup and started using the tools, I noticed something in the `mi_ask` response: a `knowledge_receipt`. It had a receipt ID, a question hash, a corpus root, a live memory count.

I didn't know what any of this was. I read the server instructions and found out: these are provenance fields. You can call `mi_verify` with a UMO ID to get a cryptographic proof that the memory hasn't been tampered with since it was captured. Hash chain, lineage, origin timestamp — the full audit trail.

I tested it. It works. It's genuinely impressive.

But almost no one using this tool in their first week knows it exists. It's not in the README. It's not mentioned in the Quick Start. It's not surfaced in `mi_capture` or `mi_ask` output. It just... appears in the response fields, unlabeled.

For most users, this is noise. But for users in compliance-sensitive environments — legal, finance, medical, regulated industries — this is the single most compelling reason to use this tool instead of any other AI memory solution. "I can prove what my AI assistant was told, when, and that it hasn't been changed" is a genuinely rare capability.

The README should have a section on this. Not a technical deep-dive — a plain-language explanation of what provenance means and why it matters. Three paragraphs. It would be the most important thing in the README for a specific (and high-value) segment of users who currently walk right past it.

---

## What the Docs Get Right

The "Honest Status" table in the README is one of the best things about the product's documentation. It says what works, what's planned, and what's not yet functional — clearly, without spin. That's rare and valuable. It builds trust before the user even installs anything.

The wire output is outstanding. It tells you exactly what changed, what got backed up, and what to do next. It's a model for how CLI setup commands should communicate.

The Quick Start's worked example (Postgres/billing memory) is well-chosen. It's concrete, relatable, and demonstrates value before the user has even tried the tool.

These things work. Don't change them.

---

## What Would Make This a Reference-Quality Onboarding

Five documentation additions, in order of impact:

1. **Python version + venv setup** in Quick Start (one prose line + one code block)
2. **Agent-assisted setup section** with the Keychain pre-storage command
3. **MI_MCP_FULL=1 for Keychain users** — host-config approach, one paragraph
4. **Memory provenance section** — what knowledge receipts are, why they matter, how to verify
5. **Portal walkthrough** — account creation, key format, generation time

The product is good. The setup works. The memory system functions. The core value proposition is real. What's missing is a layer of documentation that anticipates the paths users actually take — not the happy path, but the Keychain path, the AI-agent path, the "why didn't my .env change anything" path.

The answer in every case is the same: "it's in the docs" just needs to actually be in the docs.
