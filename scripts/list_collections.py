"""List collections via test-linkwarden MCP."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_mcp_env(server_name: str = "test-linkwarden") -> dict[str, str]:
    raw = (ROOT / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    block = re.search(
        rf'"{re.escape(server_name)}"\s*:\s*\{{.*?"env"\s*:\s*\{{(?P<body>.*?)\}}',
        raw,
        re.DOTALL,
    )
    env: dict[str, str] = {}
    for key, value in re.findall(r'"([A-Z_]+)"\s*:\s*"([^"]*)"', block.group("body")):
        env[key] = value
    return env


async def main() -> None:
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
        result = await client.call_tool("list_collections", {})
        text = result.content[0].text if result.content else "[]"
        cols = json.loads(text)
        cols = sorted(cols, key=lambda c: (-c.get("link_count", 0), c.get("name", "").lower()))
        for c in cols:
            parent = f" (under {c['parent']})" if c.get("parent") else ""
            print(f"{c['name']}{parent} — {c.get('link_count', 0)} links")
        print(f"\nTotal: {len(cols)} collections")


if __name__ == "__main__":
    asyncio.run(main())
