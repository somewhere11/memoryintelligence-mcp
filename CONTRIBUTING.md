# Contributing

Thanks for your interest in `memoryintelligence-mcp`.

## Development setup

```bash
git clone <repo> && cd memoryintelligence-mcp   # (or the mcp-server/ dir of the monorepo)
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Before you open a PR

```bash
pytest                 # unit tests must pass
ruff check src/        # lint
python -m build && twine check dist/*   # package builds + metadata valid
```

## Conventions

- **Security first.** Never log or echo the API key. Never write a credential into a config file — the launcher resolves it at runtime. New tools get JSON-schema-validated inputs and appropriate annotations (`readOnlyHint` / `destructiveHint`).
- **stdio only.** This version ships no network listener. Don't re-introduce a networked transport without inbound auth + TLS.
- **Conventional Commits** for messages (`feat:`, `fix:`, `docs:`, `chore:`).

## Reporting security issues

Please report suspected vulnerabilities privately to **connect@somewheremedia.com** rather than opening a public issue.
