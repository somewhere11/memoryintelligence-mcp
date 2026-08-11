# REPORT-4: First Workflow — Narrative (Documentation Mode)
**Type:** Empathy-Driven User Perspective  
**Audience:** Technical writers improving public-facing docs  
**Phase:** Phase 2 — First use of mi_capture, mi_ask, mi_list after setup  
**Version tested:** memoryintelligence-mcp 0.2.5  
**Date:** 2026-07-28

---

## As If I Was This Person

Setup is done. Doctor says healthy. I restarted Claude. And now I'm staring at a blank chat window thinking: *okay, so what do I actually do?*

I know the tools are there — mi_capture, mi_ask, mi_list. I read about them. But there's a gap between "I know these tools exist" and "I know what to type right now to see the value."

---

### The First Capture: Anticlimactic in the Best Way

I asked Claude to capture some notes from our setup session — what I'd learned, what friction I'd found. Claude called `mi_capture` with the content.

The response was immediate. Something like:

```
Captured. parent_id: abc123, children: 12
```

My reaction was: "Did that work? 12 children?" I didn't know what children were. I didn't know if 12 was good or bad. I didn't know if my content was now split into 12 separate pieces or if it was still one thing.

The value of the capture didn't land in that moment. It was abstract. "Saved" doesn't feel real until you can see what was saved, or retrieve it.

**What the docs need here:**

The "Quick Start" example in the README is perfect for orienting users before the first capture:

> "Remember we picked Postgres for billing — we needed transactions" (new session) "what did we decide about the billing database?"

That worked-example format is exactly what a new user needs before their first session. It answers the question "what is this FOR?" with something concrete. But there's no mention of UMO chunking or what "12 children created" means.

A short note would help: "For longer captures, the server splits your content into individual claims — each one separately searchable. The overall capture is still one item in your memory list."

---

### The First Query: Where the Value Shows Up

A few turns later, I asked Claude something related to what I'd captured. Claude called `mi_ask` with the question and got back a relevant excerpt — the right piece, correctly attributed.

That's the moment. That's when it clicked.

Even though I hadn't specifically said "look up what I captured about X," the assistant found it. It connected a question to a piece of content from earlier in the session (and earlier sessions). And it cited where it came from.

If I were writing the README, I would frontload this moment. Not the mechanism (mi_capture sends content to the vector store...) — the moment. Lead with the experience:

> *You mention a decision you made two weeks ago. Your assistant already knows — because you told it then, and it remembered.*

That's what the tool does. That's what makes someone understand why they'd set up an MCP server at all.

---

### Wanting to Check What Was Saved

After the capture returned "12 children," I instinctively wanted to look at what was stored. I called `mi_list`.

It showed two items. Not 13. Just two parent UMOs — the one I just created, and a prior one that existed already.

My question: where are the 12 children? Were they not created? Are they hidden? Is `mi_list` only showing top-level entries?

I spent a moment trying to figure out if something had gone wrong. The answer turned out to be "no, this is correct" — parent UMOs appear in the list, children are indexed for search but not shown by default. That's a reasonable design. But it's not documented anywhere.

A single sentence in the README would close this loop: "`mi_list` shows your top-level memory records. When content is chunked, the parent record appears here; individual claims are searchable via `mi_ask` but not listed separately."

---

### The Knowledge Receipt: A Feature I Didn't Know I Had

When `mi_ask` returned results, there was a `knowledge_receipt` in the response. It had a `receipt_id`, a `question_hash`, a `corpus_root`, and a `corpus_live_count`.

My first reaction: I don't know what any of this means.

My second reaction (after reading the server instructions): oh, this is an audit trail. I can call `mi_verify` with the memory's ID to prove it wasn't tampered with since I captured it.

This is actually a remarkable feature. Persistent, verified memory with a provenance chain is something most AI memory tools don't offer at all. But I found out about it by reading the system prompt instructions, not the README.

The README has one line about verification but doesn't explain the receipt, the verification command, or why it matters. For users in trust-sensitive workflows (legal, medical, compliance, finance), this is one of the most compelling features in the entire product. It's currently invisible to most onboarding users.

**A suggested addition to README:**

> **Memory you can verify.** Every `mi_ask` call returns a knowledge receipt — a signed record of what your assistant knew at query time. Call `mi_verify <memory-id>` to confirm a specific memory hasn't been changed since it was captured. This gives you an audit trail, not just storage.

Six sentences. It would be the clearest differentiator in the README for any user thinking about using this in a professional context.

---

### Extended Tools: I Tried, Nothing Happened

After getting comfortable with capture and ask, I wanted to try the extended tools — mi_explain to understand what's in my corpus, mi_match to find similar memories, and so on. I'd seen these in the docs. I wrote `MI_MCP_FULL=1` to `.env` and restarted.

Nothing changed.

The tools didn't appear. No error. I had no way of knowing if the env var wasn't being read, or if the tools were there but hidden, or if I'd made a typo somewhere. I just... didn't have the tools I expected.

Eventually I figured out the issue (Keychain users can't use `.env` for this), but only because I know how to read bash scripts. A typical developer would have tried the `.env` approach, seen nothing, tried restarting again, seen nothing, and concluded "the extended tools don't work on my setup."

This isn't a setup failure. It's a documentation gap that maps a common user action ("put the env var in the .env file") to a silent no-op. The fix is a note in the docs. The note doesn't need to explain the wrapper's conditional logic — it just needs to tell Keychain users to use the host config instead.

---

## What This Tells Us About the Docs

The first workflow is actually very good. When the tools work, they work well. The value is real — semantic recall, provenance, multi-session persistence. These are genuinely differentiating features.

The documentation problem isn't that it says wrong things. It's that it leaves several key moments undocumented:

1. **After capture:** What does "12 children" mean? Is that good?
2. **After list:** Why do I see fewer items than I captured?
3. **Knowledge receipt:** What is this, and why should I care?
4. **Extended tools for Keychain users:** Why didn't `MI_MCP_FULL=1` do anything?

Each of these is a moment where a user could exit the product ("it's not working") or lose confidence ("I don't understand what just happened"). Covering them with brief, plain-language answers would dramatically increase the rate of users who get from first capture to second session.

---

## A Note on Voice

The README currently leans technical. The "Honest Status" table is a great instinct — it signals transparency and sets expectations. Lean into that voice more. Users who are evaluating whether to adopt a new tool are also evaluating whether they trust the team building it. Honest, plain-English documentation of limitations and the "why behind the how" builds that trust faster than technical precision alone.
