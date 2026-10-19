# REPORT-7: Extended Tools — Narrative (Documentation Mode)
**Type:** Empathy-Driven User Perspective  
**Audience:** Technical writers improving public-facing docs  
**Phase:** Extended tool testing after MI_MCP_FULL=1 activation  
**Version:** v0.2.5  
**Date:** 2026-07-28

---

## As If I Was This Person

I've gotten the basic flow working. mi_capture, mi_ask, mi_list, mi_verify — I understand what those do and I've used them. I've been reading about the extended tools: mi_explain, mi_batch, mi_match, mi_account. They sound like the power-user layer, and I want to try them.

Getting them to work was its own adventure (see REPORT-3 on MI_MCP_FULL=1 and .env), but I've sorted that now. Time to see what they actually do.

---

## mi_explain: Seeing Inside the Black Box

The first thing I try is mi_explain on one of my captured memories. I use `level: "full"` because I want everything.

For a memory I captured via MCP (the agent-assisted setup security issue), mi_explain returns something useful but not spectacular:

- Summary: readable
- Scores: semantic 0.50, temporal 0.50, entity 0.00, graph 0.00
- SVO triples: null

For the file I uploaded earlier ("UMO is a verb" brief), mi_explain at full level is a completely different experience:

- 42 extracted entities
- 113 SVO triples: subject-verb-object relationships the pipeline extracted from the text
- Scores: semantic 0.92, entity 1.0, graph 1.0
- Detected tone: very_negative (it caught the "built-in wince" framing of the document)

This is where I understand something important: **explain depth is a function of how I captured the memory, not the memory itself.**

When I capture via MCP — through the Claude connector, through conversation — the pipeline produces a lean UMO: summary, hash chain, basic scoring. When I upload a file, the pipeline runs the full treatment: entity extraction, relationship mapping, topic classification, SVO triples. The same information captured two different ways yields dramatically different transparency.

This is not documented anywhere. The README describes mi_explain as "get a detailed explanation of a specific UMO." It doesn't say "you'll get dramatically different results depending on how you captured it, and most of your captures may return svo: null."

For a developer building a pipeline, this is load-bearing information. If you're uploading files for high-stakes retrieval, you want file_import — not streaming capture — because the entity graph is what separates a good match from a mediocre one.

---

## mi_match: The Relationship Lens

mi_match asks a specific question: how related are these two memories?

I test it between the "UMO is a verb" file (rich entity graph) and the agent setup security finding (sparse capture). The result: 51.2% composite match, despite 73.1% semantic similarity.

This number tells a story. These two memories are about the same product — MemoryIntelligence, UMO, the workflow — but from completely different contexts: brand positioning versus technical onboarding. The semantic models see the similarity. But because they share no extracted entities (the file has 42 canonical entities; the MCP capture has 0) and no topic overlap, the composite drops to 51%.

The composite formula — `sem.60-kw.15-ent.15-rec.10` — is visible in mi_ask knowledge receipts. It's not mentioned in mi_match documentation. So when I see 51% and expect 73%, I have no idea where the gap came from until I look at the explain block.

The audit block also returns something I didn't expect: the `hash_chain` is both UMO hashes concatenated. This is the match result as a tamper-evident record — not just "these two are similar," but "these two were compared at this time, and here is the sealed record." For audit and compliance use cases, this is actually powerful. It's also not documented.

---

## mi_account: The Wall You Don't Expect

mi_account returns 401: "Invalid or expired token."

The same key I've been using for everything else — mi_capture, mi_ask, mi_list, mi_verify, mi_explain, mi_match, mi_batch — all authenticate without complaint. Only mi_account fails.

This is a particularly disorienting failure because mi_account is the one I'd expect to work without any special permissions. It's just querying information about my own account. Quota, tier, rate limits — that's basic account metadata. If anything should work with my API key, this should.

I have no way to know if this is:
- A bug
- A tier restriction
- A scope issue
- A feature that isn't live yet in the beta

There's no error message that explains it. The 401 is generic. I open the portal and check my key — it looks fine, it has read/write permissions, it's not expired. I'm not misled by the portal; I just have no path to resolving this.

When mi_account works, I imagine it would be the most-used tool in a production integration: you'd call it before making decisions about batch size, before checking if you're near quota, before deciding whether to throttle captures. Without it, those decisions are guesses.

---

## mi_batch: The Efficient Path (When You Know the Limits)

mi_batch is the one that surprises me most positively — once it works.

On my first attempt with 4 larger items, I get a ConnectTimeout. No error message, no size feedback, just silence and then timeout. I scale back to 2 items and it works immediately.

What I get back is more than I expected. Where mi_capture returns a confirmation, mi_batch returns the full UMO for each item: entities, topics, SVO triples, quality score, sentiment, validation status, and the complete 7-stage provenance chain:

`capture → normalize → extract → enrich → parse → embed → validate`

This is the pipeline made visible. And here's the thing I notice: my batch-captured items *do* get SVO triples — small captures via mi_batch return relationship graphs that mi_capture (via the connector) doesn't produce. Or at least, mi_capture doesn't return them in its response. They may be computed; I just can't see them without calling mi_explain.

For a developer building ingestion pipelines, mi_batch is clearly the right path: more efficient, richer metadata, full pipeline transparency. But "use mi_batch for bulk and pipeline work" is not in the docs. The README introduces mi_capture as the primary tool and mentions mi_batch briefly in the extended tools section. The practical guidance — "if you're ingesting more than 3–5 items, use mi_batch; if you want full UMO metadata returned, use mi_batch" — is nowhere.

---

## What the Extended Tools Actually Are

After testing all four, I have a mental model I wish I'd had at the start:

The base 6 tools are the **user-facing interface**: capture, recall, manage, verify. They're what you need to get value from MemoryIntelligence in daily use.

The extended 4 tools are the **pipeline interface**: they expose what's happening inside the system, enable programmatic comparison and analysis, and are designed for developers building on top of MI rather than using it through an AI assistant.

mi_explain shows you what the pipeline extracted. mi_match lets you query relationships directly. mi_batch is the right ingestion path for any automated workflow. mi_account (when fixed) gives you operational visibility.

This distinction — "daily use" vs. "build on top of" — is not articulated anywhere. The README presents all tools in a flat list. A section that said "Base tools for daily use; Extended tools for developers and integrations" would instantly clarify who needs MI_MCP_FULL=1 and why.

The people who need extended tools are not the same people who need basic onboarding. They're developers building pipelines, analysts running corpus comparisons, compliance teams wanting audit trails. Those users deserve documentation written for them, not a footnote saying "set MI_MCP_FULL=1 for additional tools."

---

## The Tone Anomaly

One small thing I can't stop thinking about: mi_explain on the "UMO is a verb" document returned `detected tone: very_negative`.

The document is a brand strategy brief — confident, persuasive, ambitious. But the pipeline caught the negative polarity embedded in the rhetoric: "every verb carries a built-in wince," "you did not lock the door," "save dies." The document argues for ownership and confidence through loss-frame language. The pipeline saw the loss frames.

This is sophisticated — and it's completely invisible to the user unless they call mi_explain at full level and happen to look at the tone field. It has implications for recall: does tone affect how memories are returned? Does a "very_negative" UMO rank differently than a neutral one for the same query?

That's a question I can't answer from the docs. It's also exactly the kind of thing that a developer building on top of MI needs to know.
