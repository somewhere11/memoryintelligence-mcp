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
from typing import Iterable, Optional

logger = logging.getLogger("mi_mcp.scrub")

# Order matters: SSN/card before the looser phone matcher so digits aren't mis-tagged.
_HARD = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<EMAIL>"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "<SSN>"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "<CARD>"),
    (re.compile(r"(?<![\d.])(?:\+?\d[\s().-]?){10,15}(?![\d.])"), "<PHONE>"),
]

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
        for pattern, repl in _HARD:
            out = pattern.sub(repl, out)
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
