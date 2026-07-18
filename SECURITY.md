# Security Policy

## Reporting a vulnerability

Please report security issues privately to **connect@somewheremedia.com** — do
not open a public issue for anything exploitable.

Include: what you found, how to reproduce it, and the impact. We aim to
acknowledge within 3 business days and will keep you updated through to a fix.
Please give us a reasonable window to remediate before any public disclosure.

## Supported versions

The latest published `0.x` release on PyPI receives fixes. This is pre-1.0
software under active development.

## Design notes relevant to security

- **No API key in configs.** `mi-mcp wire` writes `env: {}` and resolves
  `MI_API_KEY` from the macOS Keychain at launch — a leaked config file exposes
  nothing.
- **stdio only.** The server runs as a local subprocess with no network
  listener; the networked transports are disabled in this release.
- **Capture is opt-in** per directory; destructive ops (`mi_forget`) require
  explicit confirmation; hidden tools are rejected at the call boundary.
- **Untrusted-data framing** wraps retrieved content to blunt prompt injection.

Please **do not** include real API keys or personal memory content in reports or
issues.
