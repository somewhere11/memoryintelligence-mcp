# Publishing `memoryintelligence-mcp` to PyPI

> **Status: REVIEW BEFORE FIRST USE.** Nothing here runs automatically until the
> one-time setup below is done by a maintainer. No API token is stored anywhere.

## The model — Trusted Publishing (OIDC), no stored token

We publish via **PyPI Trusted Publishing**: GitHub Actions authenticates to PyPI
with a short-lived OpenID Connect token issued per-run, so there is **no
long-lived `PYPI_TOKEN`** to leak, rotate, or commit. The publish job also emits
**PEP 740 attestations**, so installers can verify the artifact was built by this
repo's workflow.

Three controls gate every release:

1. **Tag-triggered only** — `.github/workflows/publish.yml` runs solely on a
   `v*` tag push, never on a branch push.
2. **Protected `pypi` environment** — the publish job targets a GitHub
   Environment that **requires a human approval click** before it runs. A tag
   alone does not ship.
3. **Version guard** — the workflow asserts the git tag (`vX.Y.Z`) matches
   `pyproject.toml`'s `version`, and only maintainers can push `v*` tags.

Net flow: `git push --tags` → CI builds + `twine check` → **a maintainer
approves the `pypi` environment** → PyPI publishes with provenance.

---

## One-time setup (maintainer, do once)

> Prerequisite: the public mirror repo `somewhere11/memoryintelligence-mcp`
> exists and contains `.github/workflows/publish.yml` (it ships in `mcp-server/`,
> so the mirror seed includes it).

### 1. PyPI — add the GitHub publisher to the existing project
The project already exists on PyPI (releases `0.1.0`, `0.1.1` were published with
a token). So this is **"add a publisher to an existing project"**, not a pending
publisher.

- pypi.org → **Your projects → `memoryintelligence-mcp` → Manage → Publishing**.
- Under **"Add a new publisher" → GitHub**, enter exactly:
  - **Owner:** `somewhere11`
  - **Repository name:** `memoryintelligence-mcp`
  - **Workflow name:** `publish.yml`
  - **Environment name:** `pypi`
- Save. (No token is generated — PyPI now trusts that specific workflow+environment.)

### 2. GitHub (mirror repo) — protect the `pypi` environment
- Mirror repo → **Settings → Environments → New environment → `pypi`**.
- Enable **Required reviewers** and add the maintainer(s). This is the human
  approval gate on every publish.
- (Optional) Limit deployment branches/tags to `v*` tags.

### 3. GitHub (mirror repo) — protect release tags
- **Settings → Tags → New rule → pattern `v*`** so only maintainers can push
  release tags (the trigger for publishing).

### 4. Revoke the legacy token (after the first TP publish succeeds)
Once a Trusted-Publishing release works end-to-end, delete the old PyPI API
token that published `0.1.0`/`0.1.1`. Trusted Publishing replaces it.

---

## Releasing a version (every time)

1. **Bump the version in all three places** (they must match):
   - `pyproject.toml` → `version`
   - `src/mi_mcp/__init__.py` → `__version__`
   - `CHANGELOG.md` → new dated section
2. **Land it on `main`** (mirror tracks shipped code).
3. **Verify locally** (optional but recommended):
   ```bash
   python -m build && twine check dist/*
   pytest -q && ruff check src/
   ```
4. **Tag and push:**
   ```bash
   git tag v0.1.5        # must equal pyproject version
   git push origin v0.1.5
   ```
5. **Approve the publish.** The `publish.yml` run builds, validates, then pauses
   at the `pypi` environment. A maintainer clicks **Approve** in the run's
   "Deployments" gate. PyPI then publishes with attestations.
6. **Verify:** https://pypi.org/project/memoryintelligence-mcp/ shows the new
   version; `pipx install memoryintelligence-mcp` / `uvx memoryintelligence-mcp`
   pulls it.

### Note on the next published version
PyPI has `0.1.4` live (the explain fix + Tier 0 + redaction signal). `0.1.2` and
`0.1.3` were tagged in the changelog but **never published** — PyPI versions are
immutable and gaps are fine, so no backfill is needed. The next publish is
**`0.1.5`** (`mi-mcp setup` one-command onboarding + MemoryIntelligence branding +
README rewrite).

---

## Pre-publish checklist
- [ ] Trusted Publishing configured on PyPI (step 1) + `pypi` env with required reviewers (step 2).
- [ ] `pyproject` `Repository` URL points to the public mirror (not the monorepo). ✅ set to `somewhere11/memoryintelligence-mcp`.
- [ ] Version matches across `pyproject.toml`, `__init__.py`, `CHANGELOG.md`.
- [ ] `twine check dist/*` passes; README renders.
- [ ] `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md` present (shipped in the sdist).
- [ ] Tag `vX.Y.Z` == `pyproject` version.

---

## Manual fallback (discouraged — emergencies only)
If Trusted Publishing is ever unavailable, a maintainer can publish from a clean
checkout with a scoped token (stored only in the maintainer's Keychain, never in
the repo):
```bash
python -m build
twine check dist/*
TWINE_USERNAME=__token__ TWINE_PASSWORD="$(security find-generic-password -a somewhere-kc -s pypi-token -w)" \
  twine upload dist/*
```
Prefer the OIDC flow above; this exists only as a break-glass path.
