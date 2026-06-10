"""Admin CLI for the MI MCP server: ``mi-mcp {setup|wire|doctor|status}``.

Security model (build-spec §13.3): the API key NEVER goes into any MCP client
config. ``wire`` writes ``{command: <wrapper>, args: [], env: {}}`` and renders
a wrapper (``~/.memoryintelligence/mcp/run-mi-mcp.sh``) that resolves
``MI_API_KEY`` at launch from the macOS Keychain, then the on-disk keyfile,
else fails. So a leaked config file exposes nothing.

  setup  — one command: store the key, wire hosts, opt in this dir, verify.
           (alias: ``init``). The frictionless front door for new users.
  wire   — register the server in Claude config(s); no key in any file.
  doctor — verify wiring + key resolvability (prints prefix only, never the key).
  status — show which surfaces are wired + the capture opt-in allowlist.

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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import paths
from .config import load_opt_in_paths

SERVER_KEY = "memory-intelligence"

# Wrapper rendered by `wire`. __MI_MCP_BIN__ is replaced with the absolute path
# to the mi-mcp binary (resolved at wire time) so the host can spawn it even
# with a minimal PATH.
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
exec "__MI_MCP_BIN__" "$@"
"""


# ---------------------------------------------------------------------------
# Paths + helpers
# ---------------------------------------------------------------------------

def _surface_paths(home: Path) -> dict[str, Path]:
    """Config file per Claude surface. NOTE: verify the `code`/`cursor` paths
    against your installed versions before relying on a live wire."""
    return {
        "desktop": home / "Library/Application Support/Claude/claude_desktop_config.json",
        "code": home / ".claude.json",
        "cursor": home / ".cursor/mcp.json",
    }


def _wrapper_path(home: Path) -> Path:
    return paths.wrapper_path(home=home)


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
    # idempotent: drop any existing entry (any scope) first, then add
    subprocess.run([claude, "mcp", "remove", SERVER_KEY], capture_output=True, text=True)
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

def do_wire(home: Path, surfaces: list[str], dry_run: bool) -> None:
    """Render the launch wrapper and register the server in each surface's config.

    Shared by ``cmd_wire`` and ``cmd_setup``. Writes ``env: {}`` only — the key is
    never placed in a config; the wrapper resolves it at launch.
    """
    cfg_paths = _surface_paths(home)
    wrapper = _wrapper_path(home)
    bin_path = _mi_mcp_bin()
    entry = {"command": str(wrapper), "args": [], "env": {}}

    print(f"{'DRY-RUN: ' if dry_run else ''}wiring memory-intelligence MCP server")
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
        cfg = _load_json(cfg_path)
        servers = cfg.setdefault("mcpServers", {})
        action = "update" if SERVER_KEY in servers else "add"
        nochange = servers.get(SERVER_KEY) == entry
        servers[SERVER_KEY] = entry
        print(f"  {s:8} {cfg_path}  [{action}{' / no-change' if nochange else ''}]")
        if not dry_run:
            _atomic_write(cfg_path, json.dumps(cfg, indent=2) + "\n")

    print("\n  ✓ no API key written to any config — the wrapper resolves it at launch")


def cmd_wire(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="mi-mcp wire")
    ap.add_argument("--surfaces", default="desktop,code",
                    help="comma list of: desktop, code, cursor (default: desktop,code)")
    ap.add_argument("--dry-run", action="store_true", help="print changes, write nothing")
    ap.add_argument("--home", default=os.environ.get("HOME"),
                    help="override HOME (for testing)")
    args = ap.parse_args(argv)

    home = Path(args.home)
    surfaces = [s.strip() for s in args.surfaces.split(",") if s.strip()]
    do_wire(home, surfaces, args.dry_run)
    if not args.dry_run:
        print("\nNext steps:")
        print(f"  1. opt in a project:  echo \"$(pwd)\" >> {paths.mcp_config_dir(home=home) / 'opt-in-paths'}")
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

    for s, p in _surface_paths(home).items():
        wired = SERVER_KEY in _load_json(p).get("mcpServers", {})
        check(f"{s} wired", wired, str(p) if wired else "(not wired)", critical=False)

    print(f"\n  {'healthy ✓' if ok else 'issues found ✗'}")
    return 0 if ok else 1


def cmd_status(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="mi-mcp status")
    ap.add_argument("--home", default=os.environ.get("HOME"))
    args = ap.parse_args(argv)
    home = Path(args.home)

    print("MCP wiring:")
    for s, p in _surface_paths(home).items():
        wired = SERVER_KEY in _load_json(p).get("mcpServers", {})
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
                    help="comma list of: desktop, code, cursor (default: desktop,code)")
    ap.add_argument("--opt-in", default=None, metavar="DIR",
                    help="directory to allow captures from (default: current directory)")
    ap.add_argument("--no-opt-in", action="store_true",
                    help="don't opt any directory in (captures stay disabled)")
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
    do_wire(home, surfaces, dry_run=False)
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


_COMMANDS = {
    "setup": cmd_setup,
    "init": cmd_setup,   # alias
    "wire": cmd_wire,
    "doctor": cmd_doctor,
    "status": cmd_status,
    "memory": cmd_memory,
}


def run_admin(command: str, argv: list[str]) -> int:
    return _COMMANDS[command](argv)
