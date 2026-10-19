# Report 2: Repository Review & Setup Clarification
## Format: Novice User Narrative (Documentation Improvement)

**Date:** 2026-06-05  
**Perspective:** First-time user reading MemoryIntelligence MCP documentation  
**Goal:** Identify where documentation confused me or left gaps  

---

## The Good News First

After finding the GitHub repository, I was genuinely excited about this tool. Here's what won me over:

**I understood the core value immediately:**
> "Maintain persistent, searchable memory across sessions"

That's powerful. I understood the use case right away—remember things I've decided, keep track of preferences, search back through past decisions.

**The three core tools made sense:**
- `mi_capture` — Save things
- `mi_ask` — Search things
- `mi_list` — Browse things

Simple, logical, no jargon.

**The features sounded responsible:**
- PII redaction (I liked that it thinks about privacy)
- Local execution (no sketchy network calls)
- Confirmation gates (doesn't delete things without asking)

At this point, I thought: "Okay, I'm ready to install this."

---

## Where I Got Stuck

Then I tried to follow the setup, and I ran into a wall of questions I couldn't answer:

### Confusion #1: When Do I Get the API Key?

The docs say: "Free API key from memoryintelligence.io/portal"

But they don't say:
- Do I go get the key FIRST, before installing?
- Or do I install first, then go get the key?
- Does the setup wizard help me get the key?
- Will the system tell me if I forget this step?

**My internal monologue:**
> "Should I be setting up an account right now? Am I about to waste 10 minutes installing something that won't work because I don't have a key? I don't want to find out halfway through."

**What would have helped:**
A clear numbered sequence:
```
1. Create a free account at memoryintelligence.io/portal
2. Copy your API key
3. Run: pip install memoryintelligence-mcp
4. Run: mi-mcp setup (and paste your API key when prompted)
```

Simple. Clear. No guessing.

---

### Confusion #2: Which Host Am I Using?

The docs mention: "Integrates with Claude Desktop, Claude Code, and Cursor"

But I don't know:
- Do I pick one? Or does it work with all three?
- Does the setup wizard know which one I have?
- Do I have to tell it?
- Will it work differently on each one?

**My internal monologue:**
> "I think I have Claude Code open right now, but I'm not 100% sure. Is there a different setup for Claude Desktop? Do I need to do something special? If I pick wrong, will it just silently not work?"

**What would have helped:**
A setup wizard that:
1. Looks for installed hosts
2. Says: "I found Claude Code on your system. That's where the MCP server will connect."
3. Lets me verify: "Is that right?" (yes/no)

Or at minimum, docs that say:
> "To check which Claude product you're using: [steps]. The MCP setup will work on any of these products, but will connect to whichever one you specify."

---

### Confusion #3: How Do I Know It Worked?

The docs say: "The setup command completes configuration in one step"

That's... vague. "Completes" how?

**Questions in my head:**
- Does it print something to the screen?
- Does it open a window?
- Does it just finish silently?
- How do I test that it actually works?
- What if I made a typo in my API key—will I find out now or later?

**My internal monologue:**
> "If the command just runs silently, I'll have no idea if it worked. And I don't want to spend 20 minutes troubleshooting a broken setup. I want a clear 'success!' message."

**What would have helped:**
Docs showing actual setup output:
```
$ mi-mcp setup
Configuring MemoryIntelligence MCP...
✓ API key validated
✓ Claude Code detected and configured
✓ Memory database created
✓ Setup complete!

Next: Run this command to test:
  mi-mcp demo
```

Clear success signal. Clear next step.

---

### Confusion #4: Do I Need Those "Extended Tools"?

The docs mention extended tools (mi_explain, mi_verify, mi_forget, mi_batch, etc.) behind a MI_MCP_FULL=1 flag.

**My questions:**
- Do I need these right away?
- Or are they advanced stuff?
- Should I enable them now or later?
- Will things break if I don't?

**My internal monologue:**
> "This feels like asking someone: 'Do you need the advanced settings?' Without knowing what the advanced settings do, I don't know if I need them. I don't want to:
> - Omit something critical
> - Turn on a bunch of stuff I don't understand
> - Have unstable features break my workflow"

**What would have helped:**
Clear guidance:
> **Getting Started:** The three core tools (capture, ask, list) are all you need. Setup installs these by default.
>
> **Advanced Features:** Extended tools (mi_explain, mi_verify, mi_forget, etc.) are optional. Enable these when you're comfortable with the basics and want more power. [Link to advanced guide]

Simple. Tells me what's required vs. nice-to-have.

---

### Confusion #5: Does the Magic "Auto-Recall" Actually Work?

The docs mention: "Agent instructions so compatible hosts automatically recall relevant memories"

**My questions:**
- What does "automatically" mean exactly?
- Does it happen every time I start a task?
- Every time I ask a question?
- Immediately after setup, or do I need more steps?
- How would I notice it happening?

**My internal monologue:**
> "This sounds amazing—'automatically recall memories.' But how do I know if it's working? If I set this up and nothing happens, is it broken or is that normal? I'm setting expectations I might not be able to meet."

**What would have helped:**
A concrete example:
> **Automatic Memory Recall:**
>
> After setup, when you start a new conversation in Claude Code, the MCP server automatically checks your memory and surfaces relevant previous memories. For example:
>
> *Scenario:* You previously saved "Prefer concise explanations over detailed ones" to memory.
>
> *What happens:* Starting a new task, Claude automatically remembers this and adjusts its communication style.
>
> *Where you see it:* The memory system surfaces relevant memories in the context without you asking.

Show me a scenario. Show me what to look for.

---

## Overall Sentiment

| Stage | Feeling | Reason |
|-------|---------|--------|
| After understanding value | 😊 Excited | "This solves a real problem!" |
| While reading setup docs | 😕 Confused | "What are all these unknowns?" |
| After hitting Q1-Q5 | 😤 Frustrated | "Just tell me what to do!" |
| Current state | 🤔 Waiting | "I want to try this, but I have too many questions" |

---

## Key Insights for Technical Writers

### 1. Sequence Matters More Than Details
I don't need to understand the internals. I need to know: "Do this, then do that, then do this." A numbered list beats a paragraph.

### 2. Unknowns Breed Caution
Every question I had made me second-guess the next step. "Should I proceed, or will I mess something up?" Clear docs eliminate that friction.

### 3. "Yes" > "Maybe"
Docs that say "Yes, extended tools are optional for beginners" are WAY more reassuring than docs that list extended tools without saying whether they're required.

### 4. Show, Don't Tell
Showing me what successful setup looks like (exact console output, success message) is more valuable than describing it.

### 5. One Path at a Time
Don't show me all the options at once. Show me the fastest path to value, then link to advanced options.

---

## Honest Assessment

**The product is good.** The docs just need to hold my hand a bit more at the start. Specifically:

1. ✅ **Clear sequence:** When/how to get API key
2. ✅ **Host clarification:** Which one you're using and why it matters
3. ✅ **Success signal:** What "working" looks like
4. ✅ **Feature gating:** What's required vs. optional
5. ✅ **Auto-recall explanation:** Concrete example of how it works

Fix those five things, and I'd feel confident hitting the install button.

---

## Questions for Technical Writers

1. Can you add a "Setup Checklist" section showing the exact sequence?
2. Can you show actual console output from a successful setup?
3. Can you add a "Required vs. Optional Features" table?
4. Can you include a scenario showing automatic memory recall in action?
5. Can you clarify which product features apply to which Claude host?

---

## Related Findings

- Value proposition is strong and clear
- Installation method (pip + mi-mcp setup) is simple
- Feature set is solid
- Docs just need to fill 5 specific gaps
