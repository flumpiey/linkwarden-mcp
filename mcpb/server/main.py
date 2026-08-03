"""Schema entry point; Claude Desktop runs uvx via mcp_config instead."""

raise SystemExit(
    "linkwarden-mcp Desktop Extension launches via uvx (see manifest.json mcp_config). "
    "Install uv: https://docs.astral.sh/uv/"
)
