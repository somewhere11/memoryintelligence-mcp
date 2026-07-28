# REPORT-7: Extended Tools (MI_MCP_FULL=1) — PRD (Build Mode)
**Type:** Product Requirements Document  
**Audience:** MCP Engineer  
**Phase:** Extended tool testing — mi_explain, mi_batch, mi_match, mi_account  
**Version:** v0.2.5 (MI_MCP_FULL=1 activated via host config env block)  
**Date:** 2026-07-28

---

## Executive Summary

All 4 extended tools were live-tested after correctly activating MI_MCP_FULL=1 via host config (not .env — see I8). Three of four work. mi_account returns 401 with the same API key that authenticates all other tools. Several undocumented behaviors surface: mi_batch has a payload size constraint, mi_explain's depth is gated by capture source, and mi_match's composite score formula is visible in the explain block.

---

## Tool 1: mi_explain

### Status: ✅ WORKING

### What It Does
Returns a structured explanation of a UMO — how it was processed, what was extracted, scores at each signal level, the full provenance chain, and (for rich UMOs) SVO triples.

### Three Levels Tested

| Level | Content |
|-------|---------|
| `human` | Plain-language summary, key reasons, retrieval quality rating, detected tone |
| `audit` | Individual score breakdown (semantic/temporal/entity/graph), hash_chain, reproducibility flag, actor_type, source_channel, device_id, lineage steps |
| `full` | All of audit + `svo` (Subject-Verb-Object triples) + `fabric_edges` |

### Critical Finding: Capture Source Determines Explain Depth

| Source | Entities | SVO Triples | Semantic Score | Entity Score | Graph Score |
|--------|----------|-------------|---------------|-------------|-------------|
| `file_import` | 42 (5 types) | 113 triples | 0.92 | 1.0 | 1.0 |
| `claude-connector` | 0 | null | 0.50 | 0.0 | 0.0 |

`svo` is null even at `full` level for claude-connector captures. `fabric_edges` is null for all tested UMOs.

**Implication for users:** mi_explain is substantially more useful for uploaded files than for MCP-captured text. Users who primarily capture via MCP (the default behavior) will find mi_explain returns sparse results. This is not documented.

### Issue E1: Explain Depth Not Documented by Capture Source
**Priority:** MEDIUM  
**Requirements:**
1. README or tool description should note that SVO extraction and entity enrichment are only applied to file_import/mi_upload sources
2. claude-connector captures return sparse explain — users should understand why their UMOs show 0 entities

### Issue E2: fabric_edges Always Null
**Priority:** LOW (may be tier-gated)  
**Requirements:**
1. Clarify whether `fabric_edges` is populated in any configuration
2. Document what tier or condition activates the knowledge graph layer

---

## Tool 2: mi_match

### Status: ✅ WORKING

### What It Does
Compares two UMOs for semantic relevance. Returns composite similarity score, above-threshold boolean, and optional explain block.

### Live Test Result
- **source:** `019f3e05` ("UMO is a verb" — file_import)  
- **candidate:** `019faa0a` (agent-assisted setup security — claude-connector)  
- **threshold:** 0.5  
- **score:** 0.5120 — "Moderate alignment" (above threshold → `match: true`)

### Score Decomposition (from explain: "human")
```
Semantic similarity: 73.14%
Entity overlap:       0.00%
Topic overlap:        0.00%
Composite:           51.20%
```

The composite formula applies the same multi-signal weighting as mi_ask: high semantic similarity is dragged down by zero entity and topic overlap. Two UMOs about the same product from different contexts (brand positioning vs. technical setup) score only 51% composite despite 73% semantic alignment.

### Issue M1: Composite Formula Not Documented for mi_match
**Priority:** LOW  
**Description:** The formula (`sem.60-kw.15-ent.15-rec.10`) is visible in mi_ask knowledge receipts but not mentioned in the mi_match tool description. Users don't know why a 73% semantic match becomes 51% composite.

**Requirements:**
1. Tool description should note that mi_match uses the same composite weighting as mi_ask
2. explain block should show the formula used alongside the score breakdown

### Note: hash_chain in match audit
The `audit.hash_chain` for a mi_match result concatenates both UMO hashes: `hash_A:hash_B`. This creates a tamper-evident link between both records in the comparison. Not documented but notable for audit use cases.

---

## Tool 3: mi_account

### Status: ❌ 401 ERROR

### Error
```
Error (401): Invalid or expired token
```

### Context
- Same API key authenticates mi_capture, mi_ask, mi_list, mi_verify, mi_explain, mi_match, mi_batch (all 9 other tools)
- mi_account is the only tool that returns 401
- Key is from macOS Keychain, format `mi_sk_beta_...`
- No retry was tested (single attempt)

### Issue I9: mi_account 401 with Valid Key
**Priority:** HIGH  
**Description:** mi_account fails authentication while all other tools succeed with the same key. Possible causes:
1. mi_account calls a different API endpoint with stricter scope requirements
2. mi_account is gated to a specific tier not available on the current beta account
3. The beta account doesn't have account-query permissions enabled
4. Bug in the mi_account tool's auth header construction

**Requirements:**
1. Root-cause the 401 — is this a scope/tier gate, or a bug?
2. If tier-gated: document which tier unlocks mi_account, and what it returns
3. If a bug: fix auth header; add integration test for mi_account with a valid key
4. If beta limitation: show a clear error message ("mi_account requires Tier 02 or above") rather than a generic 401

**Acceptance Criteria:**
- [ ] mi_account either works with a valid key or returns a descriptive error explaining why it doesn't
- [ ] README/tool description documents which tier or conditions activate mi_account

---

## Tool 4: mi_batch

### Status: ✅ WORKING (with payload size constraints)

### What It Does
Captures multiple items in a single request. More efficient than sequential mi_capture calls. Returns full UMO for each item on success.

### Live Test Results
- **2-item batch (short content):** ✅ Succeeded, ~160ms
- **4-item batch (long content ~500 chars/item):** ❌ ConnectTimeout

### What mi_batch Returns (vs mi_capture)
mi_batch returns MORE than mi_capture — the full UMO object per item, including:
- `entities` with canonical_id, confidence, type/subtype, char offsets
- `svo_triples` (for MCP-sourced batch items — unlike mi_capture, batch does extract SVOs)
- `topics` (stemmed keyword topics)
- `quality_score` (0.78–0.83 in tests)
- `sentiment_label` + `sentiment_score`
- `validation_status`
- `provenance.lineage` showing 7-stage-v1 pipeline: capture → normalize → extract → enrich → parse → embed → validate

### Notable Behaviors
- `trigger` in lineage is `"batch"` (vs `"explicit"` for mi_capture)
- `scope` parameter is accepted but response always shows `"user"` — project/team scopes may not be active in current beta
- All items in a batch are processed atomically — `results[].success` per item; batch doesn't fail atomically

### Issue B1: Payload Size Limit Undocumented
**Priority:** MEDIUM  
**Description:** Large batches cause ConnectTimeout with no documentation on what the limit is. Users building bulk ingestion pipelines have no guidance.

**Requirements:**
1. Document the per-item or total-payload size limit for mi_batch
2. Return a descriptive error (413 or custom message) when payload exceeds limit, rather than a timeout
3. Consider: expose a `max_batch_size` or `max_item_chars` in mi_account (once fixed)

### Issue B2: scope Parameter Silently Ignored
**Priority:** LOW  
**Description:** Sending `scope: "project"` results in `scope: "user"` in the response with no error. Users don't know their scope wasn't applied.

**Requirements:**
1. If project/team scopes aren't supported yet: return an error or warning when unsupported scope is passed
2. If they are supported: document which scopes are available and their effects

---

## Summary Table

| Tool | Status | Issues |
|------|--------|--------|
| mi_explain | ✅ Working | E1 (capture-source depth), E2 (fabric_edges null) |
| mi_match | ✅ Working | M1 (composite formula undocumented) |
| mi_account | ❌ 401 | I9 (CRITICAL — fails with valid key) |
| mi_batch | ✅ Working | B1 (size limit undocumented), B2 (scope silently ignored) |

---

## What Extended Tools Add (When Working)

Extended tools expose MI's internal pipeline in ways the base 6 tools don't:

- **mi_explain** turns a UMO from a black box into a transparent object — you can see exactly what signals it carries, how it was processed, and why it ranks as it does
- **mi_match** gives direct UMO-to-UMO comparison without going through mi_ask — useful for deduplication, clustering, and relationship mapping
- **mi_batch** reveals the full 7-stage pipeline and returns richer metadata than mi_capture — a better primary ingestion path for automated pipelines
- **mi_account** (when fixed) would give usage transparency — quota status, rate limits, tier info — which is essential for any production integration
