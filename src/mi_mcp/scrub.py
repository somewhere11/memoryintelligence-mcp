"""Egress redaction for the LOCAL agent surface (#433 — the R11 gate on local reads).

Everything a local read hands the model — ``mi_ask``/``mi_list`` summaries AND
``topics`` — passes through :func:`scrub_text` before it leaves the process. The
cloud enforces this for ``X-MI-Source`` agent surfaces via
``core.security.export_scrub`` (the R11 read-time gate); the local path must match
or it is a privacy DOWNGRADE (review finding CR1, issue #433).

Three layers, strongest available first:

1. **Core detector (strong path).** When the ``memory-intelligence`` core is
   importable (monorepo checkouts, school-tier installs that add the core), the
   text runs through ``core.security.export_scrub.scrub_for_export`` — the SAME
   machinery the cloud read endpoints use: the full hard-PII pattern set
   (email / SSN / card+Luhn / phone / IP / IBAN / DOB / license / passport) plus
   fresh corpus-NER detection of PERSON / ORG / LOCATION. Because detection runs
   at READ time, it catches names the capture-time NER missed — the class of leak
   the substring-only scrubber could not see. Non-PII labels (e.g. TECHNOLOGY)
   are not in the detector's PII map and render through.
2. **Hard-PII regex floor.** The in-package email/SSN/card/phone patterns always
   run — on a thin PyPI install (no core) they are the hard-PII guarantee, and on
   the strong path they backstop ``scrub_for_export``'s fail-open detector.
3. **Stored-entity belt.** Entity names the engine extracted at capture (carried
   in the index) are redacted deterministically — including per-token variants
   and possessives ("Maria", "Gonzalez's" for a stored "Maria Gonzalez") — so a
   name the read-time NER misses still cannot leak if capture caught it.

The agent surface is NON-OVERRIDABLE: there is no raw switch on this path
(#433 acceptance criteria). Owner-raw reads live on the human surfaces (desktop
app, ``mi-mcp memory open``), never here — per the #500 decision the owner reads
their own vault unredacted, but an LLM context never receives raw PII.

This is still the fail-safe floor, not the end state. The fuller, reversible form
— a pseudonym ledger that maps names↔tokens and re-identifies for the human
surface — is Phase 2 (#433 follow-on). Until then, fail CLOSED: any error
redacts the whole field.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Iterable, Optional

logger = logging.getLogger("mi_mcp.scrub")

# =============================================================================
# HARD-PII FLOOR  (#1464)
# =============================================================================
#
# ⚠️ THIS IS THE ONLY PII PROTECTION ON A THIN PyPI INSTALL. `pyproject.toml`
# depends on mcp / httpx / pydantic — NOT on `memory-intelligence` — so
# `_scrub_with_core` returns None for every ordinary
# `pip install memoryintelligence-mcp` user and layer 1 never runs.
#
# It had drifted badly behind `core/security/pii_detector.py`: measured, 7 of 14
# hard-PII cases leaked straight to the model context. Core gained an ADDRESS
# detector (#1371), separator-agnostic SSN (#1446), a 7-digit phone form and
# unicode-obfuscation handling (#846/#847) — and none of it reached here, because
# nothing tied the two floors together.
#
# `tests/test_mcp_scrub_contract.py` is now that tie: one shared fixture set
# asserted against BOTH surfaces, living in `tests/` so it runs under `test-core`
# and therefore GATES merges. (`mcp-tests.yml` is standalone and advisory — a
# contract test living there would not have stopped this.)
#
# Patterns are literal copies, not imports: the entire point is that `core` is
# absent here. Keep them in step with the named constants in
# `core/security/pii_detector.py`; the contract test tells you when you haven't.

#: Zero-width / invisible splitters (#846) and cross-script confusables (#847).
#: Both are length-preserving so a match on the healed shadow maps back cleanly.
_INVISIBLE = {ord(c): None for c in "​‌‍﻿­⁠"}
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ѕ": "s", "ԁ": "d", "ј": "j", "һ": "h",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
    "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "ο": "o", "α": "a", "ρ": "p", "ε": "e", "ι": "i", "ν": "v", "τ": "t",
})

#: SSN — SEPARATOR-AGNOSTIC (#1446). The old pattern required a literal hyphen,
#: so "412 55 9832" and "412.55.9832" walked straight through.
_SSN_RE = re.compile(r"\b(?!000|666|9\d\d)\d{3}[\s.\-]+(?!00)\d{2}[\s.\-]+(?!0000)\d{4}\b")

#: Phone. `_PHONE_LONG` is the pre-existing 10–15 digit run. The short forms are
#: the #1446/A2 gap: every alternative needed THREE digit groups, so "555-0142"
#: and "+1-555-0142" leaked — including `pii-phone-001`, an EXEMPLAR fixture.
_PHONE_LONG_RE = re.compile(r"(?<![\d.])(?:\+?\d[\s().-]?){10,15}(?![\d.])")
_PHONE_INTL_SHORT_RE = re.compile(r"(?<![\d])\+\d{1,3}[\s.\-]?\d{3}[\s.\-]\d{4}(?![\d])")
#: A bare 7-digit run is NOT distinctive — core measured it hitting file:line
#: ranges, ULID fragments and coordinates — so it is CONTEXT-ANCHORED, as there.
_PHONE_BARE7_RE = re.compile(r"(?<![\d.\-:])[2-9]\d{2}[\s.\-]\d{4}(?![\d\-])")
_PHONE_CTX_RE = re.compile(
    r"\b(?:call|called|calling|phone|telephone|tel|mobile|cell|fax|pager"
    r"|hotline|extension|ext|dial|voicemail|landline|backup\s+line|number\s+is)\b",
    re.IGNORECASE,
)
_PHONE_WINDOW = 40

#: Street addresses (#1371 + A3 + #1467 tiering). ADDRESS is a HARD type in core
#: — stripped on every surface — and this floor had NO address detector at all.
#: Ambiguous common-noun suffixes (Loop/Path/Way/...) are deliberately EXCLUDED
#: rather than corroborated: without core's context machinery the safe subset is
#: the unambiguous one, and over-redacting here would be a silent content loss.
_ST_UNAMBIG = (r"Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr"
               r"|Court|Ct|Terrace|Ter|Parkway|Pkwy|Highway|Hwy|Crescent|Cres|Alley|Pike")
_ST_INTL = (r"Rue|Boulevard|Chemin|Via|Viale|Piazza|Corso|Calle|Avenida"
            r"|Paseo|Carrera|Rua|Ulica|Aleja|Laan|Plein")
_ST_GLUED = (r"stra(?:ss|ß)e|gasse|platz|weg|allee|straat|gracht"
             r"|gata|gatan|gade|vei(?:en)?|katu|tie")
_ADDRESS_RE = re.compile(
    r"\b\d{1,6}[A-Za-z]?\s+(?:[A-Z][A-Za-z0-9.'\-]*\s+){1,4}(?:" + _ST_UNAMBIG + r")\b\.?"
    r"|\b\d{1,5}[a-zA-Z]?,?\s+(?:" + _ST_INTL + r")\b"
    r"(?:\s+(?:[A-ZÀ-Þ][\wÀ-ÿ'’\-]*|de|del|della|di|la|le|les|des|du|van|von)){1,4}"
    r"|\b[A-ZÀ-Þ][\wÀ-ÿ'’\-]*(?:" + _ST_GLUED + r")\.?\s+\d{1,5}[a-zA-Z]?\b"
)

# Order matters: SSN / card / address before the looser phone matcher so digit
# runs are not mis-tagged.
_HARD = [
    # `\s*@\s*` tolerates the whitespace-split form (#846).
    (re.compile(r"[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<EMAIL>"),
    (_SSN_RE, "<SSN>"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "<CARD>"),
    (_ADDRESS_RE, "<ADDRESS>"),
    (_PHONE_INTL_SHORT_RE, "<PHONE>"),
    (_PHONE_LONG_RE, "<PHONE>"),
]


def _healed(text: str) -> str:
    """NFKC + zero-width strip + homoglyph fold — the #846/#847 shadow.

    Length-preserving per character, so running the same patterns over the healed
    copy and substituting on it cannot corrupt offsets.
    """
    out = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    return out.translate(_HOMOGLYPHS)


def _redact_anchored_phone(text: str) -> str:
    """7-digit local numbers, only near a telephony keyword (#1446/A2)."""
    anchors = [(m.start(), m.end()) for m in _PHONE_CTX_RE.finditer(text)]
    if not anchors:
        return text
    out, shift = text, 0
    for m in _PHONE_BARE7_RE.finditer(text):
        s, e = m.start(), m.end()
        if not any(a_s <= e + _PHONE_WINDOW and s <= a_e + _PHONE_WINDOW
                   for a_s, a_e in anchors):
            continue
        out = out[: s + shift] + "<PHONE>" + out[e + shift:]
        shift += len("<PHONE>") - (e - s)
    return out

# Sticky flag: once the core import fails we don't retry it on every call.
_CORE_UNAVAILABLE = False


def _scrub_with_core(text: str) -> Optional[str]:
    """Run the cloud's R11 egress detector when the core package is installed.

    Returns ``None`` when the core isn't importable (thin PyPI install) so the
    caller falls back to the in-package floor. ``skip_types=None`` redacts soft
    PII (PERSON / ORG / LOCATION) too — stricter than the cloud agent gate's
    ``skip_types=SOFT_PII_TYPES``, which is deliberate: the local surface has no
    Phase-2 pseudonym ledger yet, so blanket-redacting detected names is the
    conservative side of #433.
    """
    global _CORE_UNAVAILABLE
    if _CORE_UNAVAILABLE:
        return None
    try:
        from core.security.export_scrub import scrub_for_export
    except Exception:
        _CORE_UNAVAILABLE = True
        logger.info(
            "core export_scrub unavailable — local egress uses the in-package floor"
        )
        return None
    return scrub_for_export(text, mode="redact", skip_types=None).scrubbed


def _redact_entity_names(text: str, entities: Iterable) -> str:
    """Redact every stored entity name — full form, per-token, and possessive.

    "Maria Gonzalez" in the index redacts "Maria Gonzalez", "Maria", "Gonzalez",
    and "Gonzalez's" (the variant leak from the #506 hold assessment). Tokens
    shorter than 3 chars are skipped ("Al", initials) — they over-match common
    words more than they protect.
    """
    for name in entities or ():
        n = str(name).strip()
        if len(n) < 3:
            continue
        variants = {n}
        variants.update(p for p in re.split(r"\s+", n) if len(p) >= 3)
        for v in sorted(variants, key=len, reverse=True):
            text = re.sub(
                r"(?<!\w)" + re.escape(v) + r"(?:[’']s)?(?!\w)",
                "<ENTITY>",
                text,
                flags=re.IGNORECASE,
            )
    return text


def scrub_text(text: Optional[str], entities: Iterable = ()) -> Optional[str]:
    """Redact PII from text destined for an agent surface (all three layers).

    Returns the input unchanged when empty/None; fails CLOSED (``<REDACTED>``) on
    any error so a scrubber bug can never leak.
    """
    if not text:
        return text
    try:
        out = str(text)
        strong = _scrub_with_core(out)
        if strong is not None:
            out = strong

        # #846/#847: run the floor over an obfuscation-HEALED copy first, so a
        # zero-width-split or homoglyph-substituted value is caught. The healed
        # copy is what we keep when it differs — the raw form only reaches here
        # if it was never obfuscated, and returning healed text is strictly safer
        # than returning text whose PII we could not see.
        healed = _healed(out)
        if healed != out:
            for pattern, repl in _HARD:
                healed = pattern.sub(repl, healed)
            out = healed

        for pattern, repl in _HARD:
            out = pattern.sub(repl, out)
        out = _redact_anchored_phone(out)
        return _redact_entity_names(out, entities)
    except Exception:
        return "<REDACTED>"


def scrub_topics(topics, entities: Iterable = ()) -> list:
    """Scrub a topics list for the agent surface (each label through scrub_text).

    ``topics`` was the ungated field in the #506 hold assessment — a name that
    became a topic label at capture leaked raw through ``mi_list``.
    """
    if not topics:
        return []
    return [scrub_text(str(t), entities) for t in topics]
