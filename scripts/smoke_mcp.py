"""Live smoke test for test-linkwarden MCP config."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_mcp_env(server_name: str = "test-linkwarden") -> dict[str, str]:
    raw = (ROOT / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    block = re.search(
        rf'"{re.escape(server_name)}"\s*:\s*\{{.*?"env"\s*:\s*\{{(?P<body>.*?)\}}',
        raw,
        re.DOTALL,
    )
    if not block:
        raise RuntimeError(f"Could not find env block for {server_name!r} in .cursor/mcp.json")
    env: dict[str, str] = {}
    for key, value in re.findall(r'"([A-Z_]+)"\s*:\s*"([^"]*)"', block.group("body")):
        env[key] = value
    has_api = "LINKWARDEN_API_URL" in env and "LINKWARDEN_API_KEY" in env
    has_legacy = "LINKWARDEN_URL" in env and "LINKWARDEN_TOKEN" in env
    if not has_api and not has_legacy:
        raise RuntimeError(
            "LINKWARDEN_API_URL and LINKWARDEN_API_KEY required in test-linkwarden env "
            "(legacy LINKWARDEN_URL / LINKWARDEN_TOKEN also accepted)"
        )
    return env


async def main() -> int:
    env = {**os.environ, **load_mcp_env()}
    env["FASTMCP_SHOW_SERVER_BANNER"] = "false"

    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    transport = StdioTransport(
        command="uv",
        args=["run", "--directory", str(ROOT), "linkwarden-mcp"],
        env=env,
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        names = sorted(t.name for t in tools)
        print(f"tools ({len(names)}): {', '.join(names)}")

        result = await client.call_tool("get_library_overview", {})
        text = result.content[0].text if result.content else str(result)
        print(f"get_library_overview: {text[:400]}")

        result = await client.call_tool("list_collections", {})
        text = result.content[0].text if result.content else str(result)
        print(f"list_collections: {text[:200]}...")

        result = await client.call_tool("get_sorting_dashboard", {})
        text = result.content[0].text if result.content else str(result)
        print(f"get_sorting_dashboard: {text[:400]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
