"""Tests for the local-surface egress scrubber (review CR1 fix + the #433 R11 gate).

The scrubber is layered: core detector (when the monorepo core is importable) →
in-package hard-PII regex floor → stored-entity belt. The floor/belt tests pin
``_scrub_with_core`` off so they are deterministic in BOTH environments (the repo
venv has core; the mcp-server CI job installs the package alone). The core
integration tests importorskip and exercise the strong path for real.
"""

import pytest

from mi_mcp import scrub


@pytest.fixture
def floor_only(monkeypatch):
    """Pin to the in-package floor — deterministic regardless of core presence."""
    monkeypatch.setattr(scrub, "_scrub_with_core", lambda t: None)


# --- hard-PII regex floor ----------------------------------------------------

def test_hard_pii_is_redacted(floor_only):
    assert scrub.scrub_text("reach me at a.b@x.io") == "reach me at <EMAIL>"
    assert scrub.scrub_text("ssn 123-45-6789 noted").startswith("ssn <SSN>")


def test_known_entity_names_redacted(floor_only):
    assert scrub.scrub_text("Maria Gonzalez approved it", ["Maria Gonzalez"]) == "<ENTITY> approved it"
    # short tokens (<3 chars) are NOT redacted (would over-match)
    assert scrub.scrub_text("Al ran the test", ["Al"]) == "Al ran the test"


def test_entity_name_variants_redacted(floor_only):
    # The #506 hold-assessment variant leak: the index stores the FULL name but the
    # summary uses a part or a possessive — those must scrub too.
    out = scrub.scrub_text("Maria said yes and Gonzalez’s memo agrees", ["Maria Gonzalez"])
    assert "Maria" not in out and "Gonzalez" not in out
    assert out.count("<ENTITY>") == 2
    # ASCII apostrophe possessive as well
    out2 = scrub.scrub_text("per Gonzalez's note", ["Maria Gonzalez"])
    assert "Gonzalez" not in out2


def test_topics_are_scrubbed(floor_only):
    # topics was the ungated field in the #506 hold assessment
    out = scrub.scrub_topics(["budget", "Maria Gonzalez", "a.b@x.io"], ["Maria Gonzalez"])
    assert out == ["budget", "<ENTITY>", "<EMAIL>"]
    assert scrub.scrub_topics(None) == []
    assert scrub.scrub_topics([]) == []


def test_empty_passthrough():
    assert scrub.scrub_text("") == ""
    assert scrub.scrub_text(None) is None


def test_fails_closed_on_internal_error(monkeypatch):
    monkeypatch.setattr(scrub, "_HARD", [(object(), "x")])  # .sub will AttributeError
    assert scrub.scrub_text("anything sensitive") == "<REDACTED>"


# --- layering ---------------------------------------------------------------

def test_floor_holds_when_core_missing(monkeypatch):
    # Simulate the thin PyPI install: core import already failed (sticky flag).
    monkeypatch.setattr(scrub, "_CORE_UNAVAILABLE", True)
    out = scrub.scrub_text("reach a.b@x.io, Maria called", ["Maria Gonzalez"])
    assert "a.b@x.io" not in out and "Maria" not in out


def test_strong_path_runs_before_the_floor(monkeypatch):
    calls = []

    def fake_core(t):
        calls.append(t)
        return t.replace("SECRET", "<X>")

    monkeypatch.setattr(scrub, "_scrub_with_core", fake_core)
    assert scrub.scrub_text("SECRET plus a.b@x.io") == "<X> plus <EMAIL>"
    assert calls == ["SECRET plus a.b@x.io"]


# --- core-detector integration (monorepo venv; skipped on thin installs) -----

def _require_core(monkeypatch):
    pytest.importorskip("core.security.export_scrub", reason="monorepo core not installed")
    monkeypatch.setattr(scrub, "_CORE_UNAVAILABLE", False)


def test_core_path_catches_what_the_floor_cannot(monkeypatch):
    _require_core(monkeypatch)
    # IP addresses are in the core detector's pattern set, not the floor's.
    out = scrub.scrub_text("server at 10.20.30.40 for staging")
    assert "10.20.30.40" not in out


def test_core_path_catches_names_capture_ner_missed(monkeypatch):
    # The #506 hold-assessment missed-entity leak: no stored entities at all, yet
    # the read-time detector still redacts the person.
    _require_core(monkeypatch)
    out = scrub.scrub_text("Meeting with Dr. Sarah Chen about the audit", entities=[])
    assert "Sarah Chen" not in out


def test_parity_with_cloud_agent_policy(monkeypatch):
    # Hold-assessment gap 6: everything the cloud agent gate (ask.py, mode=redact,
    # skip_types=SOFT_PII_TYPES) redacts, the local surface redacts too.
    _require_core(monkeypatch)
    from core.security.export_scrub import SOFT_PII_TYPES, scrub_for_export

    sample = "Card 4111 1111 1111 1111, call 555-867-5309 or a.b@x.io"
    cloud = scrub_for_export(sample, mode="redact", skip_types=SOFT_PII_TYPES).scrubbed
    local = scrub.scrub_text(sample)
    for raw in ("4111", "555-867-5309", "a.b@x.io"):
        assert raw not in cloud
        assert raw not in local
