"""Schema entry point; Claude Desktop runs `uv tool run` via mcp_config instead."""

raise SystemExit(
    "linkwarden-mcp Desktop Extension launches via uv tool run "
    "(see manifest.json mcp_config). Install uv: https://docs.astral.sh/uv/"
)
