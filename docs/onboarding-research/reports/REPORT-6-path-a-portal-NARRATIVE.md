# REPORT-6: Path A Portal Experience — Narrative (Documentation Mode)
**Type:** Empathy-Driven User Perspective  
**Audience:** Technical writers improving public-facing docs  
**Phase:** Path A — No API key, navigating the portal for the first time  
**Source:** Browser inspection of memoryintelligence.io/portal (2026-07-28)  
**Date:** 2026-07-28

---

## As If I Was This Person

I found MemoryIntelligence on GitHub. The README says: "Get a free API key at https://memoryintelligence.io/portal." I click.

The first thing I see on the signup form:

> "Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now."

I stop. This is where my onboarding ends.

---

## The Wall

I have no invitation. I don't know anyone at the company. I followed a link from the README. I expected a signup form. I got a message that says I can't sign up.

There's no "join the waitlist" link. No "request an invite" button. No email address to contact. Just the invite notice, sitting there, with nowhere to go.

My options in this moment:
1. Hope I can find a way to request access somewhere (I can't, not from this page)
2. Go back to GitHub and search the README for another path (there isn't one)
3. Give up

Most users give up here.

This is the most complete onboarding failure you can have: the user followed every instruction correctly, hit the right URL, and then got blocked by something that wasn't mentioned in the instructions. Not a typo. Not a bad network. Not a missing dependency. The door just isn't open, and nobody told them.

**The fix is one sentence in the README.** Something like:

> "Currently in invite-only beta. If you haven't received an invitation, [request early access here] or check your inbox if you were referred."

That sentence acknowledges the reality, tells the user it's expected and not their fault, and gives them a path. Without it, invite-only reads as "broken" rather than "exclusive."

---

## What's There When You Get In

For context on what invited users experience — and to help writers document this path — here's what the portal actually looks like:

**Signup is clean.** Email, optional name, optional "what are you building?" question, password. That's it. No card required, no plan selection, no configuration. After verification (email link or 6-digit code), you get your key immediately on the Dashboard.

**The key format is `mi_sk_beta_...`** This is shown in the Quickstart tab's cURL examples. It's useful to document because users setting up environment variables need to know the format. The README shows `MI_API_KEY` in env var tables but never shows an example value.

**Key management is thoughtful.** Keys can have names ("Production", "Staging"), permissions (Read/Write), and expiration (30/90/365 days or never). You can revoke and rotate. There are per-key usage stats. This is more sophisticated than most developer tools at this stage.

**One confusing moment:** The key creation modal says "Copy your secret key now. You won't be able to see it again." But the Keys tab has a "Reveal" button right there on the key list. These two things contradict each other. A user who panics after not copying the key, then discovers Reveal, feels relieved — but also like they were misled. Just update the copy: "You can always reveal your key again from the Keys tab."

---

## The Part Nobody Talks About

Here's what surprised me most about the portal: there's a full memory interface built right into it.

The Dashboard has a search bar. You type a question — "things I decided last week", "people I met at the conference", "what was that project budget we discussed" — and it searches your captured memories semantically, with score breakdowns and citation. You can select memories and synthesize them with "Run MI Ask." There's a floating "Ask from memory" panel with conversation history.

This is a complete visual alternative to the MCP tools. You don't need Claude Code or Claude Desktop. You don't need Python. You just go to the portal and search your memories in a browser.

The README doesn't mention this. Not a single sentence.

I understand why — the README is written for developers who want to integrate. But there's a whole class of user who would be deeply served by the portal UI: someone who primarily uses it to review, not just to capture; someone evaluating whether to integrate it before committing to setup; a team member who needs read access without the full MCP install.

A sentence in the README under a "Explore your memories" section would change this: "You can also search and review your memories directly in the portal at memoryintelligence.io/portal." That's all. One sentence. It would open the product to an entirely different use pattern.

---

## The Pricing Nobody Sees

There are three tiers: Tier 01 ($29/month, 500 UMOs, manual only), Tier 02 ($49/month, 5,000 UMOs, with auto-capture), Tier 03 ($99/month, unlimited, with admin/compliance). All free during beta.

This is visible in the portal Billing tab. It's not visible anywhere on GitHub or in the README.

Users who want to evaluate the product before committing don't have a way to understand the cost structure. This matters more than it might seem for developer tools: a developer evaluating a new dependency wants to know if the free tier will cover their use case, if there's a path to scale, and what "paid" looks like. None of that is answerable from the README.

A one-line mention — "Pricing and tiers at memoryintelligence.io" — with a link would close this gap. It doesn't need to embed the full table. Just acknowledge that pricing exists and point somewhere.

---

## What This All Adds Up To

The portal experience, once you're inside, is genuinely good. Clean form, immediate key delivery, thoughtful key management, a visual memory interface, well-structured team roles. The team has clearly invested in the portal as a real product surface, not just a key-vending machine.

The documentation gap is about transitions — the moments of crossing from one surface to another. From README to portal, from "no account" to "invited user," from MCP tools to portal UI. At each of these transitions, there's an assumption that the user will figure it out. Some will. Most won't.

For a product in invite-only beta, the users you have are your best advocates or your lost leads. Every documentation gap at this stage is disproportionately expensive — not because there are millions of users, but because the ones who are here are exactly the users you're trying to impress. They're developers, they're evaluating your product seriously, and they're forming impressions that will drive whether they recommend it to others.

The good news: none of these fixes are hard. The portal is built. The features are there. The words just need to catch up.
