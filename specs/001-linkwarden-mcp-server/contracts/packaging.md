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
include = [
  "src/",
  "tests/",
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

```yaml
name: publish

on:
  release:
    types: [published]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: twine check dist/*
      - uses: actions/upload-artifact@v4
        with:
          name: python-package-distributions
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/linkwarden-mcp
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: python-package-distributions
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

## Pre-first-publish checklist

- [ ] GitHub environment **`pypi`** exists (Settings → Environments)
- [ ] PyPI trusted publisher registered for this repo + `publish.yml` workflow
- [ ] `project.description` reviewed — no placeholder text
- [ ] `tests/test_sdist_contents.py` passes locally
- [ ] `twine check dist/*` passes in CI build job

## Dev dependencies

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "respx", "ruff", "hatchling", "hatch"]
```

All CI tests run mocked (`respx`); no integration marker or live Linkwarden env vars.

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
