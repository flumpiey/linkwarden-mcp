"""sdist must not ship dev-only paths."""

from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = (
    ".claude/",
    "specs/",
    "docs/",
    "skills/",
    "skills-lock.json",
    "uv.lock",
    ".env.example",
    ".github/",
    "mcpb/",
)


def _archive_relative(name: str) -> str:
    """Strip sdist root dir (e.g. linkwarden_mcp-0.1.0/) for prefix checks."""
    parts = name.split("/", 1)
    return parts[1] if len(parts) > 1 else name


@pytest.mark.parametrize("target", ["sdist"])
def test_sdist_excludes_dev_paths(target: str) -> None:
    subprocess.run(
        ["uv", "run", "hatch", "build", f"--target={target}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    dist = ROOT / "dist"
    archives = sorted(dist.glob("linkwarden_mcp-*.tar.gz"))
    assert archives, "no sdist produced"
    archive = archives[-1]
    with tarfile.open(archive, "r:gz") as tf:
        names = tf.getnames()
    for forbidden in FORBIDDEN_PREFIXES:
        hits: list[str] = []
        for name in names:
            rel = _archive_relative(name)
            if rel == forbidden.rstrip("/") or rel.startswith(forbidden):
                hits.append(name)
        assert not hits, f"sdist contains forbidden path {forbidden!r}: {hits[:5]}"

    assert any("src/linkwarden_mcp" in n for n in names)
    assert any(_archive_relative(n).startswith("tests/") for n in names)
