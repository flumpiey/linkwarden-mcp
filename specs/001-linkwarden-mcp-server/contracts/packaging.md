# Packaging Contract

**Feature**: `001-linkwarden-mcp-server`  
**Reference implementation**: [manager-mcp](https://github.com/flumpiey/manager-mcp)

## Build system

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
requires-python = ">=3.10"
dependencies = ["fastmcp>=2.0", "httpx"]

[project.scripts]
linkwarden-mcp = "linkwarden_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/linkwarden_mcp"]

[tool.hatch.build.targets.sdist]
only-include = [
  "src",
  "tests",
  "README.md",
  "LICENSE",
  "pyproject.toml",
]
```

`src/linkwarden_mcp/spec/` ships inside the wheel via the package tree — do not duplicate force-include.

## pyproject.toml traps

| Trap | Fix |
|------|-----|
| Missing sdist include | Empty sdist on PyPI; add explicit list in first commit |
| Placeholder description | PyPI blocks re-upload of same version; set final text before `0.1.0` |
| `uv_build` backend | Use hatchling to match manager-mcp and `hatch build` CI |
| Python 3.13-only | `requires-python = ">=3.10"`, ruff `target-version = "py310"` |

## Publish workflow

File **must** be named `.github/workflows/publish.yml` — must match PyPI trusted publisher workflow name exactly.

See `.github/workflows/publish.yml` (must keep that filename for the trusted publisher). Trigger: GitHub Release `published` or `workflow_dispatch`. Flow: `python -m build` → `twine check` → `pypa/gh-action-pypi-publish` (OIDC, environment `pypi`) → `mcp-publisher login github-oidc && mcp-publisher publish`.

Pre-release version bump must update: `pyproject.toml`, `server.json`, `mcpb/manifest.json`, `.cursor-plugin/plugin.json`. Then `git tag vX.Y.Z && git push origin vX.Y.Z` and create a GitHub Release from the tag.

## Pre-first-publish checklist

- [ ] GitHub environment **`pypi`** exists (Settings → Environments)
- [ ] PyPI trusted publisher registered for this repo + `publish.yml` workflow (no `PYPI_TOKEN`)
- [ ] `project.description` reviewed — no placeholder text
- [ ] `tests/test_sdist_contents.py` passes locally
- [ ] `twine check dist/*` passes in CI build job
- [ ] Version fields aligned across `pyproject.toml` / `server.json` / `mcpb/manifest.json` / `.cursor-plugin/plugin.json`

## Dev dependencies

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "respx", "ruff", "hatchling", "hatch"]
```

CI default: mocked (`respx`) via `addopts = "-m 'not integration'"`. Optional live suite uses `TEST_LINKWARDEN_API_URL` / `TEST_LINKWARDEN_API_KEY` (`pytest -m integration`).

## uvx consumption

After publish:

```json
{
  "command": "uvx",
  "args": ["linkwarden-mcp"],
  "env": {
    "LINKWARDEN_URL": "...",
    "LINKWARDEN_TOKEN": "..."
  }
}
```
