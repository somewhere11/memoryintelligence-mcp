# Changelog

All notable changes to `memoryintelligence-mcp` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/); this project uses [Semantic Versioning](https://semver.org/).

## [0.2.11] — 2026-08-11

### Fixed — `doctor` only ever asked PyPI, so a mirror install could not learn it was behind (#1347)

This package ships on **two** channels — PyPI and the public GitHub mirror — and doctor
consulted one. A user installed from the mirror could be **ahead of** PyPI and be told
they were current. Not hypothetical: 0.2.6 was tagged and installable from the mirror
while PyPI went 0.2.5 → 0.2.7, and for ~20 hours `mi-mcp doctor` answered
`0.2.6 (latest)` with a green tick.

The unreachable-PyPI branch already handled this class carefully — `latest unknown`,
never "up to date". The divergence branch never got the same care.

Doctor now reads **both** channels and reports the newest across them. When the channels
disagree it names them, **even when you are on the newest of the two**, because the
divergence itself is the defect and whoever runs `doctor` is the only person positioned
to see it. When you are current, any unreachable channel is disclosed rather than hidden:
one channel agreeing with you is weaker evidence than two. An unreachable channel is
treated as *unknown*, never as *different*, so being offline does not raise a false alarm.

`--no-version-check` / `MI_MCP_NO_VERSION_CHECK=1` still make **zero** network calls, now
to either channel.

## [0.2.10] — 2026-08-11

### Fixed — the local PII floor over-redacted digit runs and ate the following space (#1586)

```
in : "the watermark is 1737654321 seconds"
out: "the watermark is <PHONE>seconds"
```

`_PHONE_LONG_RE` was `(?:\+?\d[\s().-]?){10,15}` — **any** 10–15 digit run, each digit allowed
a trailing separator. Two defects compounded:

1. it matched **UNIX epoch seconds**, the most common 10-digit run in MI's own corpus, so a
   timestamp was redacted as a phone number;
2. the final iteration's `[\s().-]?` **swallowed the following separator**, gluing the next
   word to the marker.

**This was not a thin-install-only problem, as originally filed.** `scrub_text` applies the
`_HARD` floor on top of core's result **unconditionally** (`scrub.py:235`), so a floor looser
than core does not merely under-serve thin installs — it **overwrites a correct answer with a
wrong one on every MCP read**. Verified with core importable:

```
core alone : "the watermark is 1737654321 seconds"   (correct, untouched)
via floor  : "the watermark is <PHONE>seconds"       (degraded)
```

One loose pattern split into three precise ones, mirroring `core/security/pii_detector.py`
rather than inventing a second design:

- **`_PHONE_SEP_RE`** — separated forms. The separators *are* the signal, so no digit-value
  constraint is needed. Ends on a **digit**, which is defect 2's fix.
- **`_PHONE_E164_RE`** — the leading `+` is the signal (core measured 0 corpus matches for
  this shape).
- **`_PHONE_BARE10_RE`** — defect 1's fix, and the dangerous one. NANP shape excludes epoch
  seconds **structurally** (they start with `1` until 2033), and an alnum-aware boundary
  excludes hex-hash digits (`"svo_hash": "914eb6579098371c"` contains a 10-digit run). Core
  measured **360 → 48 → 1** as those are applied.

21 RED-first cases in `tests/test_scrub_precision.py`, 8 failing before the fix. Every
precision case has a recall partner (#1456), so closing the over-redaction cannot reopen the
leak, and the suite is green in **both** install shapes — with core importable and without —
because the defect and the fix both live in the floor that runs either way.

## [0.2.9] — 2026-08-09

### Fixed — the thin-install PII floor had drifted behind core (#1464)

`scrub.py` carries its own hard-PII regex floor. On a thin PyPI install it is the
**only** protection: this package depends on `mcp` / `httpx` / `pydantic` and NOT on
`memory-intelligence`, so the "strong path" through the core detector is absent for
every ordinary `pip install memoryintelligence-mcp` user.

That floor fell behind the core detector without anything noticing. **Measured: 7 of
14 hard-PII cases leaked** to the model context.

Brought to parity for everything a regex can do:

- **SSN** — separator-agnostic. Was hyphen-only, so `412 55 9832` and `412.55.9832`
  walked straight through.
- **Phone** — added the `+CC` short form and a **context-anchored** bare 7-digit.
  `555-0142` and `+1-555-0142` both leaked before, including an exemplar fixture.
  The bare form is anchored to a telephony keyword rather than matched outright,
  because a naked `NNN-NNNN` also matches file:line ranges and UUID fragments.
- **Address** — there was **no address detector at all**. Now covers English,
  international and compound/glued street forms.
- **Obfuscation** — NFKC normalisation, zero-width strip and homoglyph folding, so a
  zero-width-split or Cyrillic-lookalike value is caught.
- **Email** — tolerates the whitespace-split form.

Result: **15 of 16 cases redact**, with no over-redaction of file:line ranges,
numeric ranges, migration numbers or numbered headings.

### Known limitation — PERSON

`PERSON` / `ORG` / `LOCATION` need the corpus NER, which a thin install does not
have. Names are still covered *conditionally*, by the stored-entity belt, when
capture extracted them. This is asserted in the test suite as a known state rather
than left implicit.

## [0.2.8] — 2026-08-04

### Added — `mi-mcp doctor` tells you when you're behind
Doctor reported the binary, PATH, wrapper, key, allowlist, vault and wiring — and
not one word about **which version it was running**. So the most common way to be
broken was invisible: a user on 0.2.5 asking why the workspace tools "don't exist",
when they exist fine and the install is two releases old.

Doctor now checks PyPI and reports as its **first** line:

```
[✗] version  0.2.5 installed, 0.2.8 available — `uv tool upgrade memoryintelligence-mcp && mi-mcp wire`
```

Details that matter:

- **The upgrade command matches how you actually installed it** — `uv tool` /
  `pipx` / `pip`, detected from the interpreter's location. Suggesting `pip` to a
  uv-tool user is a dead end; on a Homebrew Python, `pip` may not exist at all
  and is PEP-668 externally-managed regardless.
- **`mi-mcp wire` is in the suggestion on purpose.** Upgrading across 0.2.6 without
  re-wiring leaves your config pointing at a server id that no longer announces
  itself, and the tools silently disappear.
- **Out of date never fails doctor's exit code** — behind is not broken, and scripts
  that gate on `mi-mcp doctor` must not start failing the day a release lands.
- **Unreachable PyPI reports "latest unknown", never "up to date".** Offline is not
  evidence of being current.
- **Opt out** with `--no-version-check` or `MI_MCP_NO_VERSION_CHECK=1`. Then **no
  request is made at all** — not a request whose answer is ignored. The check is an
  anonymous PyPI index fetch, the same one any install performs.

It reads the **simple index** (PEP 691), not `/pypi/<project>/json`. The aggregate
endpoint is CDN-cached and was observed serving a stale version for minutes after
0.2.7 published — a doctor reading it would confidently tell a user they were
current when they were two releases behind, which is precisely the bug this check
exists to prevent.

## [0.2.7] — 2026-08-03

### Added — `mi_ask` / `mi_list` take a `workspace_id` (#385 UC2)
Symmetric with `mi_capture` (one mental model: *omit = personal, pass an id = that
workspace*). Omit it and the read is personal, byte-for-byte as before — no wrapper,
no extra key, no extra round-trip. Pass a workspace you belong to and the read is
scoped to it; a workspace you do **not** belong to is refused rather than silently
downgraded to personal, so the scope a result reports is never a lie.

Two things specific to this surface:

- **A workspace read never comes from the on-device index.** `MI_MCP_LOCAL=1`
  serves reads locally, and the local index has no workspace concept — answering
  from it would return personal memories under a workspace label. A workspace
  target forces the cloud path, the same way advanced filters already do.
- **The result says whether other members' memories are actually included.**
  Server-side workspace read-isolation (`MI_WORKSPACE_READ_ISOLATION`) is **off by
  default**, and with it off a member-targeted read returns exactly what a personal
  read returns. The scope block therefore carries `member_wide_reads`
  (`true` / `false` / `"unknown"`), read from the server's own `/health`
  capabilities and cached per process. When it is not `true` on a multi-member
  workspace the block also carries a `note` telling the agent not to claim it
  searched the whole team. **Without this, `shared: true, member_count: 4` on an
  owner-scoped read is an overclaim waiting to be repeated to a user.**

Requires an API server new enough to advertise
`capabilities.workspace_read_isolation` in `/health`; older servers report
`"unknown"` rather than a guess. The remote MCP surface reports the same field
(read directly from the flag, since it runs inside the API process), so both
surfaces describe a workspace read the same way.

### Added — `mi_capture(workspace_id=…)` — workspace routing actually works (#385 UC1)
Routing a capture to a specific workspace was **documented as shipped and was not
implemented on this surface**. The backend has honored it since #736/#385 and the
REMOTE MCP sends it — but the local package had no way to *express* a target:
`mi_capture` had no `workspace_id` argument and `MIClient.capture()` sent no
routing header. `mi_workspaces` (added in 0.2.6) listed workspaces the tools then
could not capture into, and its description told agents to pass the workspace ULID
as `scope_id`, which routes nothing (`scope`/`scope_id` is the separate governance-scope
axis, sent in the request body). Now:

- **`mi_capture(content, workspace_id?, confirm?)`** routes the capture. Omit
  `workspace_id` and the capture goes to your home workspace exactly as before —
  personal is still the default, and an untargeted capture costs no extra API call.
- **A shared-workspace write is gated.** Targeting a workspace with more than one
  member without `confirm=true` returns `{"status": "confirm_required", …}` and
  **saves nothing** — a single silent call can never post a memory into a team
  space. Solo and personal captures need no confirm.
- **Every routed capture names where it landed** — the response carries
  `destination: {workspace_id, name, role, shared, member_count}`.
- **A workspace you are not a member of is refused, not silently downgraded** to
  personal, so a reported destination is never a lie. Authorization itself stays
  server-side; this mirrors it so the feedback is accurate.

This matches the remote surface's contract (`mi_capture` there already took
`workspace_id` + `confirm`), so both MCP surfaces now route captures identically.

Note on the wire: the target is sent as a **header**, and the API has two names for
it depending on the auth plane — `X-MI-Workspace` (API-key plane, which this package
uses) and `X-Workspace-Id` (JWT plane, what the remote sends). The client sends both,
so routing is correct on either plane.

## [0.2.6] — 2026-08-03

### Changed — the local server is now named `mi-local` (#1320)
The local stdio server announced itself as `Server("memoryintelligence")` and
`mi-mcp setup`/`wire` registered it under the config key `memoryintelligence` —
while the REMOTE MCP surface (`api.memoryintelligence.io/v1/mcp`) announces
`memoryintelligence-remote` but is typically added to claude.ai/Desktop under
the display name "memoryintelligence". On any client hosting both, the two
surfaces were indistinguishable and tool calls silently resolved to the wrong
one: during a 2026-08-02 debug, the local server's tools masqueraded as the
remote's, and `mi_workspaces` "didn't exist" because the remote was never
called. The local server now announces `mi-local` and wires under that key.

**Migration is automatic and guarded**: re-running `mi-mcp setup` or
`mi-mcp wire` renames an existing `memoryintelligence` (or pre-0.1.8
`memory-intelligence`) config entry to `mi-local` — but ONLY when that entry
points at the mi-mcp launcher (`run-mi-mcp.sh`, `python -m mi_mcp`, or the
`mi-mcp` binary). An identically-named entry pointing anywhere else is left
untouched. `mi-mcp doctor` detects a pending rename and tells you to run
`mi-mcp wire`. Idempotent — re-running is always safe.

Which server am I talking to? The local announces `mi-local` (7 tools by
default, 11 with `MI_MCP_FULL=1`); the remote announces
`memoryintelligence-remote` (4 tools).

### Added — `mi_workspaces` (tool-surface parity with the remote, #1320)
The remote surface added `mi_workspaces` for workspace routing; the local
package now has it too, in the default surface: lists the workspaces you can
capture into (id, name, your role, member count) via `GET /v1/workspaces` —
the same endpoint the remote calls, so "does mi_workspaces exist" answers the
same on both surfaces. Default surface is now 7 tools; the full surface is 11.

## [0.2.5] — 2026-07-24

### Fixed — capture now works on Claude Desktop / claude.ai connector / Cowork
Capture (`mi_capture`/`mi_upload`) was silently blocked on GUI and remote
surfaces. The write-consent gate keys on the server's working directory, but
those launchers spawn the server at the filesystem root (`/`) with no project
folder — so the per-folder allowlist could never match, and running `mi-mcp
setup` in a project folder didn't help (the server isn't running from there).
Claude Desktop was already accommodated via a wired `MI_MCP_OPT_IN_ALL=1`, but
the claude.ai connector is configured outside `mi-mcp wire` and so had no way to
satisfy the gate at all.

Now the gate recognizes "no project working directory" (a root cwd) as a
**surface-level consent** case: capture is allowed and tagged with a
`claude-connector` provenance source, so it's identifiable. This mirrors the
existing Desktop behavior but is derived at runtime, so it covers every
GUI/remote surface automatically. Reads were never gated. Editor surfaces
(Code/Cursor launched inside a real folder) keep per-folder consent unchanged,
and `MI_MCP_STRICT_CWD=1` restores strict folder gating on every surface for
anyone who wants it. The blocked-capture message is now plain-language.

### Changed — pinned the dev linter (`ruff==0.15.22`)
`[dev]` pulled the latest ruff, whose newer rules flagged pre-existing code and
reddened the public mirror's CI on every push. Pinned in lockstep with the
monorepo (#1163); no runtime effect.

## [0.2.4] — 2026-07-24

Proof surface + recall trust + upload honesty. No setup change (no re-`wire` —
`pip install -U memoryintelligence-mcp` is enough); one additive output-shape
change on `mi_ask` (it now returns an envelope — see the receipt note below).

### Added — the proof surface reaches the agent (MI#1152 rung 2)
MI just shipped query receipts — a per-`mi_ask` sealed record of *what the query
saw* — but they never reached an agent through the MCP surface. Now they do:

- **`mi_ask` returns a `knowledge_receipt`.** The ask output is now an envelope
  `{"results": [...], "knowledge_receipt": {...}}` (was a bare list). The receipt
  carries `receipt_id`, `question_hash` (the question is NEVER sent in the
  clear — only its SHA-256), `corpus_root`, `corpus_live_count`, and the ranking
  `versions`. Absent when receipts are disabled server-side (shape stays
  `{"results": [...]}`). Its duplicate result-seals are dropped — the hits
  already carry them.
- **`mi_verify` is now visible by default.** The provenance-proof tool — the
  product's core "we cite, we don't hallucinate" claim — was hidden behind
  `MI_MCP_FULL`. It joins the default surface so an agent can prove a single
  memory is untampered without a flag.
- **Server `instructions` teach both.** The agent is told a receipt rides every
  `mi_ask` (cite `receipt_id` for provenance/audit) and that `mi_verify`
  recomputes a memory's seal on demand.

Output-shape note: an `mi_ask` consumer that assumed a bare list must now read
`.results`. The receipt is additive.

### Added — injection-resistant recall framing (#1153)
Text recalled from the memory store can contain content captured from untrusted
sources. `mi_ask` / `mi_list` / `mi_explain` output now passes through a
three-layer egress defense (adapted from PAM, arXiv:2605.11032v1 §2.1) so a
payload smuggled into a memory renders as inert quoted data, never as an
instruction:

- **Structural framing** — the untrusted-data fence carries a per-response nonce,
  and the closing marker bears that nonce, so recalled text can no longer forge
  the end of the block to break out into instruction context.
- **Content escaping** — line-leading (and post-sentence) role markers
  (`System:` / `Assistant:` / …), chat-template sentinels (`<|im_start|>`,
  `[/INST]`, `<<SYS>>`) and high-signal override phrases ("ignore previous
  instructions", "reveal your system prompt") are visibly neutralized and broken
  so they can neither impersonate a turn nor be matched as a special token.
- **Quarantine** — a recalled result whose text carries an injection signature is
  moved into a cordoned QUARANTINED section, structurally separated from trusted
  recall. Clean recall is never cordoned, so retrieval fidelity is unchanged.

A 200-attack before/after battery ships under `docs/validation/pam_comparison/`
(0 executable vectors survive framing; 0 fence forgeries).

### Fixed — `mi_upload` no longer reports a blank failure on a success (#1166)
A slow file (the upload runs the full extraction pipeline synchronously
server-side) could exceed the client's 30s read timeout **after** the server had
already committed the UMOs — surfacing as `Unexpected error:` with nothing after
it, on an upload that actually succeeded. Now:

- upload gets an explicit, generous timeout instead of the shared 30s read budget;
- a read timeout returns an honest, actionable message — the upload may have
  completed, so check `mi_list` before retrying (writes are never auto-retried,
  to avoid a duplicate) — instead of a raw, message-less error;
- the unexpected-error fallback always includes the exception type, so no tool
  can ever again return a blank `Unexpected error:`;
- a leaked file handle on every upload is closed.

### Fixed — `mi_list` no longer looks empty for memories that have entities (#1079)
The compact list view dropped the per-row entity array and surfaced only
`topics` (populated from row tags, often empty for captured content), so a rich
capture read back as if nothing had been extracted. `mi_list` rows now carry a
compact entity-tag list alongside `topics`.

### Hardened — local read path redaction proven end-to-end (#433)
Added coverage proving the on-device (`MI_MCP_LOCAL=1`) `mi_ask` / `mi_list`
paths run every agent-bound field (summary and topics) through the egress
scrubber, so a future field can't be added without redaction and leak raw PII to
the model.

## [0.2.3] — 2026-07-22

### Fixed — Claude Desktop actually launches: the sandbox P0 finally ships (#1135)
The Desktop direct-interpreter wire (merged 2026-07-07) never reached PyPI — the
published 0.2.2 was built from an earlier commit under the same version number,
so `mi-mcp wire`/`setup` on the released package kept writing a Desktop entry
pointing at `run-mi-mcp.sh`, which Claude Desktop's macOS sandbox refuses to
exec. Result: the server never completes the MCP handshake, Desktop kills it at
its 60s timeout ("Server disconnected"), and no tools register — while `doctor`
reported green. This release cuts current `main`, which carries:

- **`wire` emits `{command: <python>, args: ["-m", "mi_mcp"]}` for Desktop** —
  a real Mach-O binary the sandbox allows; the key still never touches the
  config (resolved in-process from the Keychain, time-boxed at 5s).
- **`doctor` now FAILS when the Desktop entry points at a shell script**, with
  the exact remediation printed — the escalated user's hours of debugging
  become one red line.
- **The launcher's Keychain read is time-boxed** (perl alarm, 5s) for the
  surfaces that keep the wrapper (Code/Cursor): a Keychain ACL authorization
  prompt (e.g. after a venv/binary change) can no longer hang the launch
  until the host's timeout.
- Config backup before overwrite (P1) + startup marker line (P2) from the
  onboarding-report arc, also previously unreleased.
- **License clarified: Apache-2.0.** Every published release (0.2.0–0.2.2) has
  shipped under Apache-2.0; an in-repo MIT text was drift, never a decision.
  This release restores the LICENSE file and metadata to Apache-2.0 so the
  paperwork matches what has always been published — including its explicit
  patent grant (LICENSE §3), which applies to this package as the licensed
  Work. See the LICENSE for its exact scope and terms.

**To pick this up:** `pip install -U memoryintelligence-mcp` (or `uv tool
upgrade`), then **re-run `mi-mcp wire`**, then fully quit + reopen Claude
Desktop. `mi-mcp doctor` must show `[✓] desktop entry sandbox-launchable`.

## [0.2.2] — 2026-07-07

### Fixed — `explain` now surfaces the score breakdown through `mi_ask` (MI#482)
`mi_ask`'s `explain` argument was silently dropped: the MCP output shaper projected
every hit down to `{umo_id, summary, source, score}` and discarded the per-signal
`scores` breakdown unconditionally, so passing `explain: "human"` (or any level) had
no observable effect and ranking couldn't be diagnosed (e.g. the entity-channel
contribution). The shaper now **keeps the `scores` block** (semantic/keyword/entity/
recency) on each hit whenever `explain` is anything other than `none`; the default
lean shape is unchanged, so token cost is unaffected unless you ask for the breakdown.

## [0.2.1] — 2026-07-05

### Fixed — one shared vault with the MemorySpace Desktop (MI#653)
`0.2.0` noted that `mi-mcp` defaulted its local `.umo` vault to `~/MemoryIntelligence`
while the MemorySpace Desktop app reads `~/Somewhere` — two separate folders, so a
memory captured or backfilled through `mi-mcp` never showed up in the Desktop app, and
told you to point `MI_VAULT` there by hand. This release makes that automatic.

- **`mi-mcp wire` / `setup` now point the vault at `~/Somewhere`** — they write
  `export MI_VAULT="$HOME/Somewhere"` into the launcher (`run-mi-mcp.sh`), so `mi-mcp`
  and the Desktop resolve **one** vault out of the box. It's a default only: it's
  guarded so an explicit `MI_VAULT` you set yourself (env or MCP config) still wins.
- **`paths.py`'s default is unchanged** (`~/MemoryIntelligence`) — existing installs are
  never silently moved; the unification happens the next time you run `wire`.
- **`mi-mcp doctor` reports the effective vault** and whether it matches the Desktop's,
  reading the value the launcher will actually use — so the check goes green once wired.

**To pick this up:** upgrade, then **re-run `mi-mcp wire`** (upgrading alone doesn't
rewrite the launcher), and restart Claude Desktop. `mi-mcp doctor` should show the vault
as `~/Somewhere`. Files already backfilled into `~/MemoryIntelligence` by `0.2.0` stay
where they are — move them into `~/Somewhere` (or re-run `backfill`) if you want them in
the app; `doctor` flags the mismatch.

## [0.2.0] — 2026-07-04

### Added — the local vault (Path A), previously built on `main` but never released
The published `0.1.12` shipped as a thin cloud client; the entire local-vault stack
landed on `main` afterward **under the same version number** and was never cut into a
release. This release publishes it (release-hygiene fix — no new code, just a version
bump over what `main` already carried).

- **`backfill --execute` now writes the local vault** (`cli.py`): the cloud → local
  migration re-embeds each memory locally, encrypts to the owner's key, and writes a
  signed `.umo`. The prior published build's `--execute` was a dry-run stub.
- **Offline reads** — `local_index.py` + `localreads.py` + `indexer.py`: a flat-numpy
  cosine index over the decrypted vault, mirroring the hosted ranking, so `mi_ask` works
  network-free (needs the `[local]` extra: `cryptography` + `numpy`).
- **`mi-mcp index {build,stat,path}`** — build/inspect the local vector index.
- **On-device redaction** (`scrub.py`) applied on the local read path.
- **`embedder.py`** — local bge-small embeddings for backfill + query.
- Note (MI#653): `mi-mcp` still defaults its vault to `~/MemoryIntelligence`; the
  MemorySpace Desktop vault is `~/Somewhere`. Until `wire`/`setup` sets
  `MI_VAULT=~/Somewhere`, point it there manually so the two surfaces share one vault.

## [0.1.12] — 2026-06-16

### Fixed
- **The MCP client now retries on transient failures instead of failing the
  first time the API is slow to wake.** The Railway `sdk-api` is a single small
  instance that intermittently cold-starts or saturates (CPU-bound embedding +
  pgvector rerank), and the client had a hard 30s budget with **no retry** — the
  source of the "MCP keeps timing out" reports. Now:
  - **Idempotent reads** (`mi_ask`, `mi_list`, `mi_explain`, `mi_verify`,
    `mi_match`, account lookup) retry up to 2× on a read timeout or a transient
    5xx (502/503/504), with exponential backoff (0.5s, 1.0s).
  - **Writes** (`mi_capture`, `mi_upload`, `mi_forget`, batch) are **not**
    read-retried — a timeout after the request body landed could double-apply.
  - **Connection-level retries** (transport `retries=2`) cover the cold-start
    `ConnectError` case for *every* verb, since no body is re-sent when the
    connection never established.

  This is a client-side reliability mitigation. The durable fix is local-vault
  reads (no network round-trip on recall) — tracked separately.

## [0.1.11] — 2026-06-16

### Added
- **`mi_upload` is now part of the default tool surface** — file-capture parity
  with the API. The MCP previously exposed only text capture; `mi_upload` now
  ships in the visible tool set and its description covers the full capture
  matrix: structured files (csv/tsv/xlsx/json → typed claims), documents
  (pdf/docx), images (→ OCR), and audio/video (→ transcription).

## [0.1.10] — 2026-06-15

### Changed
- **`mi_forget` now enforces its `confirm=true` gate.** The tool advertised a
  confirmation step but the handler ignored it and deleted immediately. It now
  returns `confirmation_required` (and deletes nothing) unless `confirm=true` is
  passed — so an injected or accidental call can't silently destroy a memory.
  (Pairs with the API-side delete fix: deletes now actually persist.)

### Fixed
- **Release CI is green on the public mirror again.** `test_contract_endpoints.py`
  asserted the monorepo's `api/contract/openapi.json` exists; the mirror is a
  subtree of `mcp-server/` only, so that file is absent and the test errored on
  every release. It now **skips** when the contract isn't present (monorepo-only
  test), instead of failing the mirror's build.

## [0.1.9] — 2026-06-13

### Added
- **`--capture-anywhere` for `wire`/`setup`** — opt capture in for **Claude Desktop**,
  which has no project folder for the per-folder consent gate to match. Sets
  `MI_MCP_OPT_IN_ALL=1` on the **desktop entry only**; Claude Code and Cursor keep
  per-folder consent. Default **off** (explicit opt-in is the ownership stance).
  `--no-capture-anywhere` turns it back off; a plain re-wire preserves the choice.
  Desktop captures are tagged `source=claude-desktop` (new `MI_DEFAULT_SOURCE`) so
  they're identifiable apart from project captures, and `wire` prints a consent
  warning while it's on. **No API key is ever written to a config.**

### Changed
- **Proactive-capture guidance tightened** — the server instructs the host to
  capture *sparingly* (the user's own durable facts — not third parties' details,
  venting, or half-formed ideas), reducing over-capture.

### Fixed
- **Launch wrapper self-heals a stale binary path** — `run-mi-mcp.sh` tries the
  wire-time path first, then re-resolves via `PATH` and the common install dirs,
  and exits with one actionable error if none resolve — instead of failing
  silently when a reinstall/upgrade moves the `mi-mcp` binary.

## [0.1.8] — 2026-06-10

### Changed
- **The MCP server id is now `memoryintelligence`** (was `memory-intelligence`).
  This is the id under `mcpServers` in your config and the name in
  `claude mcp add …`. It now matches the brand/package token everywhere else
  (`MemoryIntelligence`, `memoryintelligence-mcp`) instead of splitting the word
  with a dash.
- **Auto-migration:** `mi-mcp wire`/`setup` removes the old `memory-intelligence`
  entry from every surface (file configs **and** `claude mcp remove`) before
  adding the new id, so an upgrade leaves no duplicate/orphan. `mi-mcp doctor`
  flags a leftover legacy entry and tells you to re-wire. **Action on upgrade:
  run `mi-mcp wire` once.** (Hand-edited configs: rename the key yourself.)

## [0.1.7] — 2026-06-09

### Changed
- **Hidden files now live under `~/.memoryintelligence/`** (was `~/.mi/`), matching
  the visible `~/MemoryIntelligence/` vault — one on-brand namespace:
  - launcher → `~/.memoryintelligence/mcp/run-mi-mcp.sh`
  - capture opt-in allowlist → `~/.memoryintelligence/mcp/opt-in-paths`
  - keyfile (the Keychain fallback) → `~/.memoryintelligence/.env`

  `mi-mcp setup`/`wire` write the new layout and migrate an existing
  `~/.mi/opt-in-paths` forward non-destructively. The legacy `~/.mi/` launcher
  and `~/.mi-env` keyfile are still **read** for one release, so existing
  installs keep working until you re-run `wire`. `paths.py` is now the single
  source of truth for the layout (it previously declared the new layout while the
  CLI still wrote `~/.mi/` — that split is fixed here).

### Added
- **README "Names & locations" map** — explains the package / command / server-id
  names (`memoryintelligence-mcp` / `mi-mcp` / `memory-intelligence`) and where
  every file lives, so the naming no longer looks arbitrary.

## [0.1.6] — 2026-06-09

### Security
- **`doctor` no longer prints any bytes of your API key.** `mi-mcp doctor`
  previously logged an 11-character prefix of the resolved key (CodeQL
  `py/clear-text-logging-sensitive-data`, high). It now reports only *where*
  the key resolved from (Keychain / keyfile / env), never the key itself.

### Added
- **MCP ↔ API contract tests** (`tests/test_api_contract.py`, run in CI — not
  shipped in the published package) — pin that every client method sends only
  parameter values the API accepts (`explain`, `pii_handling`,
  `retention_policy`, `scope`), so an API enum/type change can never silently
  422 a real call. This is the general form of the `explain` bool→enum bug
  fixed in 0.1.3.

### Changed
- Internal code-quality cleanups (narrowed a few broad `except` clauses, removed
  an unused import). No behavior change.

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
