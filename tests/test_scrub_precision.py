"""The local floor must not be LOOSER than core (#1586).

`scrub_text` runs core's scrubber first (when importable) and then applies the
in-package `_HARD` floor **unconditionally on top**. So a floor pattern that is
looser than core does not merely under-serve thin installs — it actively
*degrades* core's correct output on every MCP read.

Two defects, found while checking parity for #1582:

    "the watermark is 1737654321 seconds"  ->  "the watermark is <PHONE>seconds"
                                                                  ^^^^^^^ ^
                                          a unix timestamp read as a phone,
                                          and the following space eaten

⚠️ BOTH EDGES (#1456). Fixing the over-redaction must not reopen the leak
direction, so every precision test here has a recall partner.
"""

from __future__ import annotations

import pytest

from mi_mcp.scrub import scrub_text


# ---------------------------------------------------------------------------
# EDGE 1 — precision. Ordinary digit runs must survive untouched.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,run", [
    # unix epoch seconds — 10 digits, the most common 10-digit run in the corpus.
    # Core excludes these structurally: they start with 1, NANP requires [2-9].
    ("the watermark is 1737654321 seconds", "1737654321"),
    ("created_at 1700000000 in the fixture", "1700000000"),
    ("the sync ran at 1735344000 and finished", "1735344000"),
    # placeholder run
    ("the sample id is 1234567890", "1234567890"),
    # a 10-digit run inside a hex hash
    ('svo_hash "914eb6579098371c" stays intact', "914eb6579098371c"),
])
def test_ordinary_digit_runs_are_not_phones(text, run):
    """Assert the DIGIT RUN survives — not that the whole string is untouched.

    The looser assertion was wrong and the tests caught it: core legitimately
    redacts other things in some of these sentences (`account 0123456789` →
    `<NUMERIC_ID>`, which is #845 working as intended, and an over-eager `id` →
    `<PERSON>`, which is #1421). Demanding a byte-identical string would have made
    this test fail for reasons that have nothing to do with #1586.
    """
    out = scrub_text(text)
    assert run in out, f"#1586 OVER-REDACTED the run {run!r}: {out!r}"
    assert "<PHONE>" not in out, f"#1586 typed {run!r} as a phone: {out!r}"


def test_an_anchored_account_number_is_still_caught_as_a_numeric_id():
    """The partner to the test above: not-a-phone must not become not-detected.

    `account 0123456789` IS sensitive, and core's anchored numeric-ID detector
    (#845) is the right owner of it. Pinned so a future precision fix cannot quietly
    turn this into a leak while making the epoch cases pass.

    ⚠️ CORE-ONLY, and the CI run is what proved it. This suite runs **thin** in
    `mcp-tests.yml` (core is not on the path), and the assertion failed there while
    passing locally where I had core importable — the lane trap again. It is
    skipped rather than deleted because the property is real when core is present.

    What the failure exposed is worth its own line: **the thin-install floor has no
    numeric-ID detector at all**, so `account 0123456789` genuinely passes through
    on a thin install. That is not #1586 (which is about over-redaction) — it is a
    recall gap on the floor, and it belongs to #1475's parity work.
    """
    pytest.importorskip(
        "core.security.export_scrub",
        reason="numeric-ID detection is core's; the thin floor has none (#1475)",
    )
    out = scrub_text("account 0123456789 in the doc")
    assert "0123456789" not in out, f"account number leaked: {out!r}"
    assert "<PHONE>" not in out, f"typed as a PHONE rather than an id: {out!r}"


def test_the_following_space_is_never_eaten():
    """The separator after the last digit must not be consumed by the match.

    `(?:\\+?\\d[\\s().-]?){10,15}` let the final iteration swallow a trailing
    space, gluing the next word to the marker.
    """
    out = scrub_text("call the desk at 4155550142 before six")
    assert "<PHONE>" in out
    assert "<PHONE>before" not in out, f"space eaten: {out!r}"
    assert "<PHONE> before six" in out, out


def test_no_marker_is_ever_glued_to_a_word():
    """Generalises the above across every separator that can follow a number."""
    for tail in [" seconds", ", then", ". Next", "; after", ")", " and 415-555-0199"]:
        out = scrub_text(f"reach the desk at 4155550142{tail}")
        assert "<PHONE>" in out
        glued = out.split("<PHONE>", 1)[1][:1]
        assert glued == "" or not glued.isalnum(), f"glued {glued!r} in {out!r}"


# ---------------------------------------------------------------------------
# EDGE 2 — recall. The leak direction must not regress.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "4155550142",                        # bare-10 NANP (#1582)
    "+14155550142",                      # E.164 (#1582)
    "415-555-0142",                      # separated
    "+1-415-555-0142",
    "(415) 555-0142",
    "+44 20 7946 0958",                  # intl grouped
    "call me at 555-0142",               # anchored bare-7 (#1446)
])
def test_real_phone_numbers_still_redact(text):
    assert "<PHONE>" in scrub_text(text), f"#1586 fix REOPENED a leak: {text!r}"


@pytest.mark.parametrize("text,markers", [
    ("412 55 9832", ("<SSN>",)),
    ("412.55.9832", ("<SSN>",)),
    ("dev@solobuild.example", ("<EMAIL>",)),
    ("22 Rue de la Paix", ("<ADDRESS>",)),
    # Marker differs by install shape: core (when importable) emits
    # `<CREDIT_CARD>` and wins, because it runs before the floor; a thin install
    # falls through to the floor's `<CARD>`. Accept either — this test has to be
    # true in both configurations, and pinning one would pass only by accident.
    ("4111 1111 1111 1111", ("<CREDIT_CARD>", "<CARD>")),
])
def test_other_hard_types_do_not_regress(text, markers):
    out = scrub_text(text)
    assert any(m in out for m in markers), f"{markers} regressed on {text!r} -> {out!r}"


# ---------------------------------------------------------------------------
# The floor must not be LOOSER than core — the property this issue is about.
# ---------------------------------------------------------------------------

def test_floor_never_degrades_core_output():
    """For text core leaves alone, the floor must leave it alone too.

    This is the actual defect: `_HARD` runs on top of core's result, so a looser
    floor pattern overwrites a correct answer with a wrong one.
    """
    core = pytest.importorskip(
        "core.security.export_scrub", reason="core not importable (thin install)"
    )
    for text in [
        "the watermark is 1737654321 seconds",
        "created_at 1700000000 in the fixture",
    ]:
        core_out = core.scrub_for_export(text).scrubbed
        floor_out = scrub_text(text)
        assert core_out == text, "fixture no longer represents 'core leaves it alone'"
        assert floor_out == core_out, (
            f"the floor degraded core's output: core={core_out!r} floor={floor_out!r}"
        )
