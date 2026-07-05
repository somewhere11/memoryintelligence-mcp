"""Admin CLI for the MI MCP server: ``mi-mcp {setup|wire|doctor|status}``.

Security model (build-spec §13.3): the API key NEVER goes into any MCP client
config. ``wire`` writes ``{command: <wrapper>, args: [], env: {}}`` and renders
a wrapper (``~/.memoryintelligence/mcp/run-mi-mcp.sh``) that resolves
``MI_API_KEY`` at launch from the macOS Keychain, then the on-disk keyfile,
else fails. So a leaked config file exposes nothing.

  setup    — one command: store the key, wire hosts, opt in this dir, verify.
             (alias: ``init``). The frictionless front door for new users.
  wire     — register the server in Claude config(s); no key in any file.
  doctor   — verify wiring + key resolvability (prints prefix only, never the key).
  status   — show which surfaces are wired + the capture opt-in allowlist.
  memory   — inspect the local .umo vault (ls|open|verify|rm|path).
  backfill — migrate cloud memories into the local .umo vault (re-embed locally).
  index    — build/inspect the local vector index (build|path|stat).

The key is stored OUTSIDE every config — in the macOS Keychain (``security``)
or, on Linux/Windows (or by choice), a ``chmod 600 ~/.memoryintelligence/.env``
keyfile (the legacy ``~/.mi-env`` is still read for back-compat). Both are
resolved by the launch wrapper at runtime, so no config file ever holds a secret.

The on-disk layout (launcher, opt-in allowlist, keyfile) lives under
``~/.memoryintelligence/`` — see ``paths.py``, the single source of truth.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__, paths
from .config import load_opt_in_paths

SERVER_KEY = "memoryintelligence"
# Pre-0.1.8 server ids we replace on wire so an upgrade leaves no orphaned entry.
# (0.1.7 and earlier registered the server as "memory-intelligence" — the one
# dash-seam that didn't match the brand/package "memoryintelligence".)
LEGACY_SERVER_KEYS = ("memory-intelligence",)

# Wrapper rendered by `wire`. __MI_MCP_BIN__ is replaced with the absolute path
# to the mi-mcp binary (resolved at wire time) so the host can spawn it even
# with a minimal PATH. If that path later goes stale (a reinstall/upgrade moved
# the binary), the wrapper self-heals by re-resolving via PATH + the common
# install dirs — so a moved binary degrades to one clear, actionable error
# instead of the silent spawn failure that strands a stale absolute path.
WRAPPER_TEMPLATE = r"""#!/usr/bin/env bash
# Rendered by `mi-mcp wire` — do not edit; re-run wire to regenerate.
# Resolves MI_API_KEY at launch so the key never lives in any MCP client config.
set -euo pipefail

# 1. inherited env  →  2. macOS Keychain  →  3. keyfile (new then legacy)  →  fail
if [[ -z "${MI_API_KEY:-}" ]]; then
  MI_API_KEY="$(security find-generic-password -a "${MI_KEYCHAIN_ACCOUNT:-$USER}" -s "MI_API_KEY" -w 2>/dev/null || true)"
fi
for __mi_envf in "$HOME/.memoryintelligence/.env" "$HOME/.mi-env"; do
  if [[ -z "${MI_API_KEY:-}" && -f "$__mi_envf" ]]; then
    set -a; . "$__mi_envf"; set +a
  fi
done
if [[ -z "${MI_API_KEY:-}" ]]; then
  echo "run-mi-mcp: MI_API_KEY not found (env, Keychain service 'MI_API_KEY', or ~/.memoryintelligence/.env)" >&2
  exit 1
fi
export MI_API_KEY

# Point the local .umo vault at the MemorySpace Desktop vault (~/Somewhere) so
# both surfaces resolve ONE vault (#653). Without this, mi-mcp defaults to
# ~/MemoryIntelligence and backfilled memories never appear in the Desktop (and
# on a dev machine ~/MemoryIntelligence is the monorepo checkout itself). An
# explicit MI_VAULT (inherited env or a config `env` entry) still wins — we only
# fill the default.
if [[ -z "${MI_VAULT:-}" ]]; then
  export MI_VAULT="$HOME/Somewhere"
fi

# Resolve the mi-mcp binary. The path captured at `wire` time is tried first —
# it's the most reliable under a host's minimal GUI PATH (e.g. Claude Desktop).
# If a reinstall/upgrade moved it, fall back to PATH then the common install
# dirs so the launcher self-heals instead of failing silently.
MI_MCP_BIN="__MI_MCP_BIN__"
if [[ ! -x "$MI_MCP_BIN" ]]; then
  MI_MCP_BIN="$(command -v mi-mcp 2>/dev/null || true)"
fi
if [[ -z "${MI_MCP_BIN:-}" || ! -x "$MI_MCP_BIN" ]]; then
  for __cand in \
    "$HOME/.local/bin/mi-mcp" \
    "$HOME/.local/bin/memoryintelligence-mcp" \
    "/opt/homebrew/bin/mi-mcp" \
    "/usr/local/bin/mi-mcp"; do
    if [[ -x "$__cand" ]]; then MI_MCP_BIN="$__cand"; break; fi
  done
fi
if [[ -z "${MI_MCP_BIN:-}" || ! -x "$MI_MCP_BIN" ]]; then
  echo "run-mi-mcp: mi-mcp binary not found — reinstall and re-wire:" >&2
  echo "  pip install -U memoryintelligence-mcp && mi-mcp wire" >&2
  exit 1
fi
exec "$MI_MCP_BIN" "$@"
"""


# ---------------------------------------------------------------------------
# Paths + helpers
# ---------------------------------------------------------------------------

def _surface_paths(home: Path) -> dict[str, Path]:
    """Config file per surface. NOTE: verify the `code`/`cursor`/`vscode` paths
    against your installed versions before relying on a live wire."""
    return {
        "desktop": home / "Library/Application Support/Claude/claude_desktop_config.json",
        "code": home / ".claude.json",
        "cursor": home / ".cursor/mcp.json",
        # VS Code / GitHub Copilot (agent mode) read a dedicated user mcp.json.
        "vscode": home / "Library/Application Support/Code/User/mcp.json",
    }


def _surface_key(surface: str) -> str:
    """Top-level JSON object that holds the server map for a surface.

    Claude surfaces (desktop/code/cursor) use ``"mcpServers"``; VS Code / Copilot
    use ``"servers"`` in their mcp.json. Per-surface so one wire pass writes the
    right schema for each host.
    """
    return "servers" if surface == "vscode" else "mcpServers"


def _wrapper_path(home: Path) -> Path:
    return paths.wrapper_path(home=home)


def _wrapper_vault(home: Path) -> Path | None:
    """The ``MI_VAULT`` default baked into the rendered wrapper by ``wire``, if any.

    The wrapper ``export MI_VAULT="$HOME/Somewhere"``s (behind a guard) so the
    server resolves the same vault as the Desktop (#653). ``doctor`` reads it to
    report the vault the *server* will actually use at launch — which isn't
    necessarily set in the shell running ``doctor``. Returns ``None`` if the
    wrapper is absent or sets no vault default."""
    wrapper = _wrapper_path(home)
    if not wrapper.exists():
        return None
    m = re.search(r'MI_VAULT="([^"]*)"', wrapper.read_text())
    if not m:
        return None
    return Path(m.group(1).replace("$HOME", str(home))).expanduser()


def _mi_mcp_bin() -> str:
    return shutil.which("mi-mcp") or str(Path(sys.executable).parent / "mi-mcp")


def _wire_code_via_cli(home: Path, wrapper: Path, dry_run: bool) -> bool:
    """Wire the Claude Code surface via the official ``claude mcp add`` rather
    than hand-editing ``~/.claude.json`` — the running Claude Code writes that
    file concurrently, so a third-party read/modify/write would race with it.

    Returns True if handled. Only used when wiring the *real* HOME; a custom
    ``--home`` (tests) returns False so the live config is never touched and the
    plain file-write path runs instead.
    """
    real_home = os.environ.get("HOME")
    if not real_home or str(home) != real_home:
        return False
    claude = shutil.which("claude")
    if not claude:
        return False
    add_cmd = [claude, "mcp", "add", SERVER_KEY, "-s", "user", "--", str(wrapper)]
    print("  code     via `claude mcp add -s user` (official; avoids racing ~/.claude.json)")
    if dry_run:
        print(f"           would run: {' '.join(add_cmd)}")
        return True
    # idempotent + migrate: drop any existing entry — current id AND the legacy
    # pre-0.1.8 ids — before re-adding, so an upgrade leaves no orphan.
    for key in (SERVER_KEY, *LEGACY_SERVER_KEYS):
        subprocess.run([claude, "mcp", "remove", key], capture_output=True, text=True)
    r = subprocess.run(add_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"           ! claude mcp add failed ({r.stderr.strip()[:160]}); falling back to file")
        return False
    print("           ✓ added via claude CLI")
    return True


def _atomic_write(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        # Set the final mode BEFORE writing any content. mkstemp already creates
        # the temp file at ≤0o600, but chmod-first closes any window where a
        # secret (the ~/.mi-env keyfile) could be observed at a looser mode.
        if mode is not None:
            os.chmod(tmp, mode)
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass  # tmp already gone / unremovable — the original error is re-raised below
        raise


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text().strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise SystemExit(f"error: {path} is not valid JSON — fix or move it before wiring")


def _resolve_key(home: Path) -> tuple[str, str]:
    """Resolve MI_API_KEY the same way the wrapper does. Returns (key, source).
    The key is returned only so the caller can show a prefix — never print it whole."""
    if os.environ.get("MI_API_KEY"):
        return os.environ["MI_API_KEY"], "env"
    account = os.environ.get("MI_KEYCHAIN_ACCOUNT") or os.environ.get("USER") or ""
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", "MI_API_KEY", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip(), "keychain"
    except (OSError, subprocess.SubprocessError):
        pass  # `security` unavailable/failed — fall through to the keyfile
    envf = paths.resolve_keyfile(home)  # new ~/.memoryintelligence/.env, else legacy ~/.mi-env
    if envf is not None:
        src = "~/.mi-env" if envf.name == ".mi-env" else "~/.memoryintelligence/.env"
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line.startswith("MI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'"), src
    return "", "none"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def do_wire(home: Path, surfaces: list[str], dry_run: bool,
            capture_anywhere: bool | None = None) -> None:
    """Render the launch wrapper and register the server in each surface's config.

    Shared by ``cmd_wire`` and ``cmd_setup``. No API key is ever placed in a
    config — the wrapper resolves it at launch.

    ``capture_anywhere`` controls the ONE non-secret env value we ever write:
    ``MI_MCP_OPT_IN_ALL=1``, and ONLY on the **desktop** entry. Claude Desktop is
    a GUI app that spawns the server with no project cwd, so the per-folder
    capture-consent gate can't apply there — capture from Desktop is therefore an
    explicit surface-level opt-in. Code/Cursor open a real folder, so they keep
    per-folder consent and never receive this flag.

    It is tri-state, so the toggle is fully reversible and upgrade-safe:
      • ``True``  → enable it (``--capture-anywhere``)
      • ``False`` → disable it (``--no-capture-anywhere``)
      • ``None``  → preserve whatever is already set (a plain re-wire never
                    silently flips a capture choice the user made).
    """
    cfg_paths = _surface_paths(home)
    wrapper = _wrapper_path(home)
    bin_path = _mi_mcp_bin()

    print(f"{'DRY-RUN: ' if dry_run else ''}wiring {SERVER_KEY} MCP server")
    print(f"  wrapper → {wrapper}")
    print(f"           execs {bin_path}; resolves MI_API_KEY at launch (no key in configs)")
    if not dry_run:
        _atomic_write(wrapper, WRAPPER_TEMPLATE.replace("__MI_MCP_BIN__", bin_path), mode=0o755)
        # Bring a legacy ~/.mi/opt-in-paths forward to the new location (no-op if
        # there's nothing to migrate). Non-destructive — the old file is left.
        if paths.migrate_opt_in_forward(home=home):
            print(f"  migrated opt-in allowlist → {paths.opt_in_paths_file(home=home)}")

    for s in surfaces:
        if s == "code" and _wire_code_via_cli(home, wrapper, dry_run):
            continue
        if s not in cfg_paths:
            print(f"  ! unknown surface '{s}' (skipped)")
            continue
        cfg_path = cfg_paths[s]
        cfg_key = _surface_key(s)
        cfg = _load_json(cfg_path)
        servers = cfg.setdefault(cfg_key, {})
        # Migrate: drop any pre-0.1.8 id (e.g. "memory-intelligence") so the
        # rename to "memoryintelligence" doesn't leave a duplicate/orphan entry.
        migrated = [k for k in LEGACY_SERVER_KEYS if servers.pop(k, None) is not None]
        if migrated:
            print(f"  {s:8} migrated id {', '.join(migrated)} → {SERVER_KEY}")
        # Build this surface's entry. env carries at most the one non-secret
        # opt-in flag, desktop-only. capture_anywhere is tri-state: True enables,
        # False disables, None preserves the current setting (so a plain re-wire
        # never silently flips a capture choice the user made).
        env: dict[str, str] = {}
        if s == "desktop":
            prior = servers.get(SERVER_KEY)
            prior_env = prior.get("env") if isinstance(prior, dict) else None
            already_on = isinstance(prior_env, dict) and prior_env.get("MI_MCP_OPT_IN_ALL") == "1"
            enabled = already_on if capture_anywhere is None else capture_anywhere
            if enabled:
                # Tag Desktop captures with a distinct provenance source so they're
                # identifiable/reviewable apart from project (folder-scoped) captures.
                env = {"MI_MCP_OPT_IN_ALL": "1", "MI_DEFAULT_SOURCE": "claude-desktop"}
        entry = {"command": str(wrapper), "args": [], "env": env}
        # VS Code / Copilot require an explicit transport type on each entry;
        # Claude surfaces don't use one.
        surface_entry = {"type": "stdio", **entry} if s == "vscode" else entry

        action = "update" if SERVER_KEY in servers else "add"
        nochange = servers.get(SERVER_KEY) == surface_entry
        servers[SERVER_KEY] = surface_entry
        note = ("  ·  capture-anywhere ON" if env else "  ·  capture-anywhere off") if s == "desktop" else ""
        print(f"  {s:8} {cfg_path}  [{action}{' / no-change' if nochange else ''}]{note}")
        if env and s == "desktop":
            print("           ⚠ ANY Claude Desktop chat under this macOS login can now write to your")
            print("             MI account (captures are PII-redacted + tagged source=claude-desktop).")
            print("             Don't enable on a shared login. Turn off: --no-capture-anywhere")
        if not dry_run:
            _atomic_write(cfg_path, json.dumps(cfg, indent=2) + "\n")

    print("\n  ✓ no API key written to any config — the wrapper resolves it at launch")


def cmd_wire(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="mi-mcp wire")
    ap.add_argument("--surfaces", default="desktop,code",
                    help="comma list of: desktop, code, cursor, vscode (default: desktop,code)")
    ap.add_argument("--dry-run", action="store_true", help="print changes, write nothing")
    ap.add_argument("--capture-anywhere", action=argparse.BooleanOptionalAction, default=None,
                    help="allow mi_capture from Claude Desktop regardless of folder "
                         "(sets MI_MCP_OPT_IN_ALL=1 on the desktop entry only; Code/Cursor "
                         "keep per-folder consent). Use --no-capture-anywhere to turn it back "
                         "off; omit both to preserve the current setting.")
    ap.add_argument("--home", default=os.environ.get("HOME"),
                    help="override HOME (for testing)")
    args = ap.parse_args(argv)

    home = Path(args.home)
    surfaces = [s.strip() for s in args.surfaces.split(",") if s.strip()]
    do_wire(home, surfaces, args.dry_run, capture_anywhere=args.capture_anywhere)
    if not args.dry_run:
        print("\nNext steps:")
        # "opt in a directory" reads as "put a file in a folder" to a new user — it's
        # neither. It records a project path in an allowlist; nothing is placed in the
        # folder. Show it as a concrete cd-then-command so the mental model is right.
        print("  1. allow captures from a project (no file is placed — it records the path):")
        print("       cd ~/Projects/my-app")
        print(f"       mi-mcp setup --opt-in \"$(pwd)\"     # or: echo \"$(pwd)\" >> {paths.mcp_config_dir(home=home) / 'opt-in-paths'}")
        print("  2. restart Claude (MCP servers load at startup)")
        print("  3. mi-mcp doctor   # verify")
    return 0


def cmd_doctor(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="mi-mcp doctor")
    ap.add_argument("--home", default=os.environ.get("HOME"))
    args = ap.parse_args(argv)
    home = Path(args.home)

    ok = True

    def check(label: str, good: bool, detail: str = "", critical: bool = True) -> None:
        nonlocal ok
        if critical and not good:
            ok = False
        print(f"  [{'✓' if good else '✗'}] {label}" + (f"  {detail}" if detail else ""))

    bin_path = _mi_mcp_bin()
    check("mi-mcp binary", Path(bin_path).exists(), bin_path)

    # PATH self-check — the #1 post-`uv tool install` stall: the shim exists but its
    # dir isn't on PATH, so `mi-mcp` "isn't found" until the user notices uv's warning.
    bin_dir = str(Path(bin_path).parent)
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    on_path = bin_dir in path_dirs
    check("binary on PATH", on_path,
          "" if on_path else f'{bin_dir} not on PATH — run `export PATH="{bin_dir}:$PATH"` (or `uv tool update-shell`) and open a new terminal',
          critical=False)

    wrapper = _wrapper_path(home)
    check("wrapper rendered", wrapper.exists(), str(wrapper))
    check("wrapper executable", wrapper.exists() and os.access(wrapper, os.X_OK),
          critical=wrapper.exists())

    key, src = _resolve_key(home)
    check("MI_API_KEY resolvable", bool(key),
          f"source={src}")

    optin = paths.opt_in_paths_file(home=home)
    n = len(load_opt_in_paths(optin)) if optin.exists() else 0
    check("opt-in allowlist", True,
          f"{n} entries" if optin.exists() else "absent — all captures will skip",
          critical=False)

    # Vault path — where the local .umo vault resolves, and whether it matches the
    # MemorySpace Desktop vault (~/Somewhere). By default they differ (#653): mi-mcp
    # defaults to ~/MemoryIntelligence, the Desktop reads ~/Somewhere. `mi-mcp wire`
    # bakes `MI_VAULT="$HOME/Somewhere"` into the wrapper to unify them, so the
    # EFFECTIVE vault is the one the wrapper exports when it spawns the server — not
    # necessarily what's set in this doctor shell. Resolve in that order: a live
    # MI_VAULT (an explicit override always wins) → the wrapper's baked-in default →
    # the paths default.
    desktop_vault = home / "Somewhere"
    live_vault = os.environ.get("MI_VAULT")
    if live_vault:
        vpath, vsrc = Path(live_vault).expanduser(), "MI_VAULT env"
    elif (wired := _wrapper_vault(home)) is not None:
        vpath, vsrc = wired, "wrapper (wired)"
    else:
        vpath, vsrc = paths.vault_dir(home=home), "default"
    matches = vpath.resolve() == desktop_vault.resolve()
    # Green when it resolves to the Desktop vault, or when the user set an explicit
    # MI_VAULT of their own (their choice wins — we don't second-guess it). Only the
    # unresolved default (mismatch, no explicit override) gets the #653 nag.
    green = matches or bool(live_vault)
    if green:
        detail = f"{vpath}  [{vsrc}]"
    else:
        detail = (f"{vpath} [{vsrc}] — Desktop reads {desktop_vault}; run `mi-mcp wire` "
                  f"(bakes MI_VAULT={desktop_vault}) so both share one vault (#653)")
    check("vault path", green, detail, critical=False)

    for s, p in _surface_paths(home).items():
        servers = _load_json(p).get(_surface_key(s), {})
        wired = SERVER_KEY in servers
        legacy = [k for k in LEGACY_SERVER_KEYS if k in servers]
        detail = str(p) if wired else "(not wired)"
        if legacy and not wired:
            detail = f"legacy id {', '.join(legacy)} present — run `mi-mcp wire` to migrate"
        check(f"{s} wired", wired, detail, critical=False)

    print(f"\n  {'healthy ✓' if ok else 'issues found ✗'}")
    return 0 if ok else 1


def cmd_status(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="mi-mcp status")
    ap.add_argument("--home", default=os.environ.get("HOME"))
    args = ap.parse_args(argv)
    home = Path(args.home)

    print("MCP wiring:")
    for s, p in _surface_paths(home).items():
        wired = SERVER_KEY in _load_json(p).get(_surface_key(s), {})
        print(f"  {s:8} {'wired ✓  ' if wired else 'not wired'}   {p}")

    optin = paths.opt_in_paths_file(home=home)
    opted = load_opt_in_paths(optin) if optin.exists() else []
    print(f"\nOpt-in paths ({len(opted)}):")
    for p in opted:
        print(f"  {p}")
    if not opted:
        print("  (none — captures will be skipped until you add one)")
    return 0


def cmd_memory(argv: list[str]) -> int:
    """Inspect the local vault: ``mi-mcp memory {ls|open|verify|rm|path}``."""
    from . import umo_format, vault

    ap = argparse.ArgumentParser(prog="mi-mcp memory")
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("ls", help="list memories in the vault (no key needed)")
    sub.add_parser("path", help="print the vault directory")
    for name, helptext in (
        ("open", "decrypt + print a memory by umo_id (needs your master key)"),
        ("verify", "verify a memory's signature offline"),
        ("rm", "delete a memory by umo_id"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("umo_id")
    args = ap.parse_args(argv)

    if args.action == "path":
        print(vault.vault_path())
        return 0

    if args.action == "ls":
        rows = vault.summarize()
        if not rows:
            print(f"(no memories yet in {vault.vault_path()})")
            return 0
        print(f"{'UMO ID':<28} {'CREATED':<22} {'FILE':<20} SIZE")
        for r in rows:
            print(f"{r['umo_id']:<28} {r['created_at']:<22} {r['file']:<20} {r['size']}")
        return 0

    if args.action == "rm":
        ok = vault.delete_umo(args.umo_id)
        print("deleted" if ok else f"not found: {args.umo_id}")
        return 0 if ok else 1

    path = vault.find_by_umo_id(args.umo_id)
    if path is None:
        print(f"not found: {args.umo_id}")
        return 1
    parsed = umo_format.parse(path.read_bytes())

    if args.action == "verify":
        pub_b64 = os.environ.get("MI_SIGNING_PUBKEY")
        if not pub_b64:
            print("⚠ no pinned MI signing key — set MI_SIGNING_PUBKEY="
                  "<base64 ed25519 public key> to verify")
            return 2
        import base64

        from cryptography.hazmat.primitives.asymmetric import ed25519
        mi_pub = ed25519.Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
        ok = umo_format.verify(parsed, mi_pub)
        print("signature OK ✓" if ok else "signature INVALID ✗")
        return 0 if ok else 1

    # open
    from . import keys
    try:
        priv = keys.load_master_private_key(create=False)
        out = umo_format.decrypt_as_owner(parsed, priv)
    except Exception as e:
        detail = str(e) or type(e).__name__
        print(f"cannot open: {detail} (wrong master key, or file corrupted)")
        return 1
    print(json.dumps(out, indent=2))
    return 0


# ---------------------------------------------------------------------------
# backfill — one-time cloud → local-vault migration (dry-run by default)
# ---------------------------------------------------------------------------

# A <PERSON>/<…> marker in the OWNER export means the content was redacted at
# INGEST (stored redacted). The owner export keeps person names, so a marker here
# flags a memory whose raw text was never stored and cannot be recovered locally.
_REDACTION_MARKERS = (
    "<PERSON>", "<EMAIL>", "<PHONE>", "<SSN>", "<LOCATION>", "<ORG>",
    "<CREDIT_CARD>", "[REDACTED]",
)


@dataclass
class BackfillStats:
    total: int = 0
    approx_bytes: int = 0
    with_raw: int = 0
    redacted_at_source: int = 0
    stream_error: str | None = None


def _analyze_export(lines) -> BackfillStats:
    """Tally an NDJSON export stream without writing anything.

    Pure + side-effect-free so it's unit-testable with synthetic lines. Counts
    UMOs, bytes, how many carry raw_text, and how many were already redacted at
    ingest (a marker in the owner export = unrecoverable raw text).
    """
    st = BackfillStats()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        st.approx_bytes += len(raw) + 1
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(obj, dict) and obj.get("_error"):
            st.stream_error = str(obj.get("_error"))
            continue
        st.total += 1
        if obj.get("raw_text"):
            st.with_raw += 1
        if any(m in line for m in _REDACTION_MARKERS):
            st.redacted_at_source += 1
    return st


# --- pure transforms (export row → .umo inputs); unit-testable without I/O -----

def _parse_export_objects(lines) -> list[dict]:
    """Parse export NDJSON lines into UMO dicts (skip blanks/errors/malformed)."""
    out: list[dict] = []
    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(obj, dict) and not obj.get("_error"):
            out.append(obj)
    return out


def _text_for_embedding(row: dict) -> str:
    """Pick the text to (re-)embed — the normalized text, else raw, else summary.

    The cloud has no exported embedding (`export.py` omits the 384-d vector), so
    backfill must re-embed locally; this chooses the same text capture embeds.
    """
    for k in ("normalized_text", "raw_text", "summary"):
        v = row.get(k)
        if v and str(v).strip():
            return str(v)
    return ""


def _payload_for_umo(row: dict, embedding: list[float]) -> dict:
    """Build the encrypted ``.umo`` payload for a backfilled cloud UMO."""
    return {
        "embedding": embedding,
        "summary": row.get("summary") or "",
        "entities": row.get("entities") or [],
        "topics": row.get("tags") or [],
        "created_at": row.get("created_at"),
        "normalized_text": row.get("normalized_text") or "",
        "raw_text": row.get("raw_text"),
        "semantic_hash": row.get("semantic_hash"),
        "quality_score": row.get("quality_score"),
        "source_type": row.get("source_type"),
        # Provenance: owner-self-signed, NOT MI-attested (we re-produced it locally).
        "origin": "backfill",
    }


def _public_metadata_for_umo(row: dict, owner_did: str) -> dict:
    """Plaintext public metadata for a backfilled ``.umo`` (no PII; vault-readable).

    Emits the same field set the desktop app writes (content_type / format_version /
    mi_key_id / schema_version / source_count) so the two surfaces share one
    readable home, plus an ``origin`` provenance label (the desktop ignores extras).
    """
    from . import umo_format
    return {
        "umo_id": row.get("id"),
        "created_at": row.get("created_at"),
        "owner_did": owner_did,
        "content_type": "text/plain",
        "format_version": umo_format.FORMAT_VERSION_STR,
        "mi_key_id": "local",
        "schema_version": row.get("schema_version") or "1.0",
        "source_count": 1,
        # MCP provenance: owner-self-signed backfill, NOT MI-attested (extra field).
        "origin": "backfill",
    }


def cmd_backfill(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="mi-mcp backfill",
        description="One-time migration of your cloud memories into the local .umo vault. "
                    "Dry-run by default (writes nothing).",
    )
    ap.add_argument("--execute", action="store_true",
                    help="actually write to the local vault (default: dry-run, writes nothing)")
    ap.add_argument("--since", default=None, metavar="ISO8601",
                    help="only backfill memories created on/after this timestamp")
    ap.add_argument("--home", default=os.environ.get("HOME"))
    args = ap.parse_args(argv)
    home = Path(args.home)

    key, src = _resolve_key(home)
    if not key:
        print("error: no MI_API_KEY resolvable — run `mi-mcp setup` first.", file=sys.stderr)
        return 2
    base_url = os.environ.get("MI_BASE_URL", "https://api.memoryintelligence.io").rstrip("/")

    from . import vault
    vault_dir = vault.vault_path()

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"{mode}: backfill cloud → local vault")
    print(f"  source: {base_url}/v1/memories/export?include_raw=true   (raw owner export · key {src})")
    print(f"  vault : {vault_dir}")
    print("  streaming export …")

    import httpx
    params = {"include_raw": "true"}
    if args.since:
        params["since"] = args.since
    headers = {"Authorization": f"Bearer {key}", "User-Agent": f"mi-mcp/{__version__}"}
    try:
        with httpx.stream(
            "GET", f"{base_url}/v1/memories/export",
            params=params, headers=headers,
            timeout=httpx.Timeout(120.0, connect=10.0),
        ) as resp:
            if resp.status_code >= 400:
                resp.read()
                print(f"error: export HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
                return 1
            # Collect the stream once; we need it for both the stats and (on
            # --execute) the write pass. The migration is a one-shot, so holding
            # the (embedding-free) export in memory is acceptable.
            lines = list(resp.iter_lines())
    except httpx.HTTPError as exc:
        print(f"error: export request failed: {exc}", file=sys.stderr)
        return 1

    stats = _analyze_export(lines)
    print()
    print(f"  memories            : {stats.total}")
    print(f"  approx size         : {stats.approx_bytes / 1024:.1f} KB")
    print(f"  carry raw_text      : {stats.with_raw}")
    print(f"  redacted at ingest  : {stats.redacted_at_source}  (raw never stored — unrecoverable)")
    if stats.stream_error:
        print(f"  ⚠ stream interrupted: {stats.stream_error} — counts are partial")

    if not args.execute:
        print("\n  DRY-RUN — nothing written.")
        print("  --execute would: re-embed each locally (fastembed bge-small) → encrypt to")
        print(f"  .umo with your owner key → write to {vault_dir} → build the local index.")
        return 0

    # ---- EXECUTE: re-embed locally → encrypt to .umo → vault → build index ----
    objects = _parse_export_objects(lines)
    embeddable = [(o, t) for o in objects if (t := _text_for_embedding(o)) and o.get("id")]
    skipped_no_text = sum(1 for o in objects if o.get("id") and not _text_for_embedding(o))
    if not embeddable:
        print("\n  nothing to write (no embeddable memories in the export).")
        return 0

    try:
        from . import embedder, indexer, keys, umo_format
        # create=False: NEVER mint a new owner key as a side effect of a migration —
        # that would encrypt the backfill to a key the owner doesn't hold, and reads
        # would silently skip every file (review H3). Fail loudly if it's not resolvable.
        owner_priv = keys.load_master_private_key(create=False)
        owner_pub = owner_priv.public_key()
        signing = keys.load_local_signing_key(create=False)
        # Match the desktop's fixed owner_did so MCP- and desktop-written .umo share
        # one consistent home (owner_did is a label, not used in decryption).
        owner_did = umo_format.LOCAL_OWNER_DID
    except Exception as e:  # missing crypto extra / no Keychain key / etc.
        print(f"\nerror: cannot resolve owner keys: {e}", file=sys.stderr)
        print("  (run `mi-mcp setup`/the desktop app first so the owner key exists)", file=sys.stderr)
        return 2

    # Print the key fingerprint so you can confirm the backfill is encrypted to YOUR key.
    print(f"\n  owner key: {keys.owner_did(owner_priv)}  (confirm this is yours)")
    print(f"  embedding {len(embeddable)} memories locally (bge-small)…")
    try:
        vectors = embedder.embed([t for _, t in embeddable])
    except embedder.LocalEmbedderError as e:
        print(f"\nerror: {e}", file=sys.stderr)
        return 2

    written = 0
    for (row, _text), vec in zip(embeddable, vectors):
        pm = _public_metadata_for_umo(row, owner_did)
        blob = umo_format.produce_umo_for_owner(
            _payload_for_umo(row, vec), pm, owner_pub, signing
        )
        vault.write_umo(pm["umo_id"], owner_did, blob)
        written += 1

    print(f"  wrote {written} .umo files → {vault_dir}")
    if skipped_no_text:
        print(f"  skipped {skipped_no_text} memories with no embeddable text")

    print("  building local index …")
    count = indexer.rebuild_and_save(owner_priv=owner_priv)
    print(f"  ✅ index built: {count} memories rankable locally → {paths.local_index_path()}")
    print("\n  Local reads are wired: set MI_MCP_LOCAL=1 to serve mi_ask/mi_list from this")
    print("  vault. `mi-mcp index build` rebuilds the index after vault changes.")
    return 0


# ---------------------------------------------------------------------------
# setup — the one-command front door (store key → wire → opt-in → verify)
# ---------------------------------------------------------------------------

def _store_key_keychain(key: str, account: str) -> None:
    """Store the key in the macOS Keychain under service ``MI_API_KEY``.

    ``-U`` updates an existing item so ``setup`` is re-runnable. macOS only;
    callers fall back to the keyfile when ``security`` is unavailable.

    Note: ``security`` has no non-interactive way to pass the secret off the
    command line (``-w -`` stores a literal ``-``), so the key is briefly in this
    subprocess's argv. On macOS a non-root user cannot read another user's argv,
    so the exposure is same-user only — the same trade-off as the documented
    manual ``security add-generic-password`` path.
    """
    subprocess.run(
        ["security", "add-generic-password", "-a", account, "-s", "MI_API_KEY",
         "-w", key, "-U"],
        check=True, capture_output=True, text=True,
    )


def _store_key_file(home: Path, key: str) -> Path:
    """Write the key to a ``chmod 600`` ``~/.memoryintelligence/.env`` keyfile.

    The cross-platform fallback when there is no Keychain (Linux/Windows) or when
    the user explicitly chooses ``--store file``. Still NOT a config file: the
    launch wrapper sources it at runtime; no MCP config ever holds the key. (The
    launcher still reads the legacy ``~/.mi-env`` too, for existing installs.)
    """
    envf = paths.keyfile_path(home)
    content = (
        "# MemoryIntelligence MCP — API key, resolved at launch by run-mi-mcp.sh.\n"
        "# Private (chmod 600). Never commit this file.\n"
        f'MI_API_KEY="{key}"\n'
    )
    _atomic_write(envf, content, mode=0o600)
    return envf


def _opt_in_dir(home: Path, directory: str) -> tuple[Path, bool]:
    """Add ``directory`` (realpath) to ``~/.memoryintelligence/mcp/opt-in-paths``.

    Returns ``(file, added)``. Idempotent — re-running setup in the same dir does
    not duplicate the entry. Realpath normalization matches the consent gate.
    """
    optin = paths.mcp_config_dir(create=True, home=home) / "opt-in-paths"
    target = os.path.realpath(os.path.expanduser(directory))
    existing = load_opt_in_paths(optin) if optin.exists() else []
    if any(os.path.realpath(os.path.expanduser(p)) == target for p in existing):
        return optin, False
    text = optin.read_text() if optin.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    text += target + "\n"
    _atomic_write(optin, text)
    return optin, True


def cmd_setup(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="mi-mcp setup",
        description="One command: store your key, wire hosts, opt in this dir, verify.",
    )
    ap.add_argument("--api-key", default=None,
                    help="provide the key non-interactively (else you're prompted, hidden)")
    ap.add_argument("--store", choices=["auto", "keychain", "file"], default="auto",
                    help="where to keep the key (auto: Keychain on macOS, ~/.memoryintelligence/.env elsewhere)")
    ap.add_argument("--surfaces", default="desktop,code",
                    help="comma list of: desktop, code, cursor, vscode (default: desktop,code)")
    ap.add_argument("--opt-in", default=None, metavar="DIR",
                    help="directory to allow captures from (default: current directory)")
    ap.add_argument("--no-opt-in", action="store_true",
                    help="don't opt any directory in (captures stay disabled)")
    ap.add_argument("--capture-anywhere", action=argparse.BooleanOptionalAction, default=None,
                    help="also allow mi_capture from Claude Desktop regardless of folder "
                         "(desktop entry only; Code/Cursor keep per-folder consent). "
                         "--no-capture-anywhere turns it off.")
    ap.add_argument("--home", default=os.environ.get("HOME"),
                    help="override HOME (for testing)")
    args = ap.parse_args(argv)

    home = Path(args.home)
    surfaces = [s.strip() for s in args.surfaces.split(",") if s.strip()]

    print("MemoryIntelligence MCP — setup\n")

    # 1) resolve the key. Preference order, safest first:
    #    interactive hidden prompt → MI_API_KEY env (non-interactive, not in argv)
    #    → --api-key flag (convenient, but visible in the process list — warn).
    #    The key is never echoed.
    key = (args.api_key or "").strip()
    if key:
        print("  ⚠ --api-key is visible in the process list (ps); on shared machines\n"
              "    prefer the interactive prompt or the MI_API_KEY env var.", file=sys.stderr)
    if not key:
        if sys.stdin.isatty():
            print("Get a free key at https://memoryintelligence.io/portal")
            try:
                key = getpass.getpass("Paste your MemoryIntelligence API key (hidden): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\naborted — nothing stored.", file=sys.stderr)
                return 130
        elif os.environ.get("MI_API_KEY"):
            key = os.environ["MI_API_KEY"].strip()
            print("  using MI_API_KEY from the environment")
        else:
            print("error: no API key. Run in a terminal to be prompted, set MI_API_KEY,\n"
                  "       or pass --api-key. Get a free key at https://memoryintelligence.io/portal",
                  file=sys.stderr)
            return 2
    if not key:
        print("error: empty API key — nothing stored.", file=sys.stderr)
        return 2
    if not key.startswith("mi_"):
        print("  ⚠ that doesn't look like an MI key (expected an 'mi_…' prefix) — continuing")

    # 2) store it OUTSIDE every config (Keychain, or chmod-600 keyfile)
    method = args.store
    if method == "auto":
        method = "keychain" if (sys.platform == "darwin" and shutil.which("security")) else "file"
    if method == "keychain":
        account = os.environ.get("MI_KEYCHAIN_ACCOUNT") or os.environ.get("USER") or ""
        try:
            _store_key_keychain(key, account)
            print(f"  [1/4] key → macOS Keychain (service MI_API_KEY, account {account})")
        except (OSError, subprocess.CalledProcessError) as e:
            envf = _store_key_file(home, key)
            print(f"  [1/4] Keychain unavailable ({e}); key → {envf} (chmod 600) instead")
    else:
        envf = _store_key_file(home, key)
        print(f"  [1/4] key → {envf} (chmod 600)")
    print("        never written to any MCP config — the launcher resolves it at runtime\n")

    # 3) wire the hosts
    print("  [2/4] wiring hosts")
    do_wire(home, surfaces, dry_run=False, capture_anywhere=args.capture_anywhere)
    print()

    # 4) opt this directory in for capture (reads work everywhere regardless)
    if args.no_opt_in:
        print("  [3/4] opt-in skipped (--no-opt-in) — captures stay disabled until you add a dir")
    else:
        directory = args.opt_in or os.getcwd()
        _optin, added = _opt_in_dir(home, directory)
        verb = "opted in for capture" if added else "already opted in"
        print(f"  [3/4] {verb}: {os.path.realpath(os.path.expanduser(directory))}")
    print()

    # 5) verify
    print("  [4/4] verifying")
    rc = cmd_doctor(["--home", str(home)])

    if rc == 0:
        print("\n  ✅ done — restart Claude, then just talk to it:")
        print('       "remember we picked Postgres for billing — we needed transactions"')
        print('       (new session)  "what did we decide about the billing database?"')
    else:
        print("\n  ⚠ setup ran, but doctor flagged issues above — fix them, then re-run `mi-mcp doctor`.")
    return rc


def cmd_index(argv: list[str]) -> int:
    """Build/inspect the local vector index: ``mi-mcp index {build|path|stat}``.

    ``build`` decrypts the vault with your master key (Keychain prompt) and writes
    the rank sidecar; the server loads that prebuilt sidecar on the read path.
    """
    ap = argparse.ArgumentParser(prog="mi-mcp index")
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("build", help="(re)build the index from the vault (needs your master key)")
    sub.add_parser("path", help="print the index sidecar path")
    sub.add_parser("stat", help="show how many memories are indexed")
    args = ap.parse_args(argv)

    from . import indexer

    if args.action == "path":
        print(paths.local_index_path())
        return 0

    if args.action == "stat":
        idx = indexer.load_index()
        if idx is None:
            print(f"(no index yet — run `mi-mcp index build`)  [{paths.local_index_path()}]")
            return 0
        print(f"{len(idx)} memories indexed  [{paths.local_index_path()}]")
        return 0

    # build
    try:
        count = indexer.rebuild_and_save()
    except Exception as e:
        detail = str(e) or type(e).__name__
        print(f"cannot build index: {detail}", file=sys.stderr)
        return 1
    print(f"✅ indexed {count} memories → {paths.local_index_path()}")
    return 0


_COMMANDS = {
    "setup": cmd_setup,
    "init": cmd_setup,   # alias
    "wire": cmd_wire,
    "doctor": cmd_doctor,
    "status": cmd_status,
    "memory": cmd_memory,
    "backfill": cmd_backfill,
    "index": cmd_index,
}


def run_admin(command: str, argv: list[str]) -> int:
    return _COMMANDS[command](argv)
