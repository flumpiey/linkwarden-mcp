<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/flumpiey/linkwarden-mcp/main/assets/banner-dark.svg">
  <img src="https://raw.githubusercontent.com/flumpiey/linkwarden-mcp/main/assets/banner-light.svg" alt="LINKWARDEN-MCP: ask your AI about your Linkwarden bookmarks, collections and tags" width="1280">
</picture>

<!-- mcp-name: io.github.flumpiey/linkwarden-mcp -->

[![Licence: MIT](https://img.shields.io/github/license/flumpiey/linkwarden-mcp?style=for-the-badge&label=licence&color=06004f&labelColor=f2ff26)](LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/flumpiey/linkwarden-mcp/ci.yml?branch=main&style=for-the-badge&label=ci&color=06004f&labelColor=f2ff26)](https://github.com/flumpiey/linkwarden-mcp/actions/workflows/ci.yml) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-06004f?style=for-the-badge&labelColor=f2ff26)](https://www.python.org/) [![PyPI](https://img.shields.io/pypi/v/linkwarden-mcp?style=for-the-badge&label=pypi&color=06004f&labelColor=f2ff26)](https://pypi.org/project/linkwarden-mcp/) [![MCP Registry](https://img.shields.io/badge/mcp%20registry-listed-06004f?style=for-the-badge&labelColor=f2ff26)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.flumpiey/linkwarden-mcp)

## What it is and why

`linkwarden-mcp` is a stdio [Model Context Protocol](https://modelcontextprotocol.io/) server for [Linkwarden](https://linkwarden.app/), the self-hosted bookmark manager that preserves full-page archives. It lets Claude, Cursor, VS Code Copilot and other MCP hosts search, read and sort your live library in natural language. The problem it solves: an AI assistant needs useful access to your bookmarks without an access token that can also delete your library or touch user accounts. The server is read-only by default, and each class of change needs its own opt-in scope.

## Features

- **18 read tools, always on.** Search, metadata, preserved page text, collections, tags, a library overview and eleven triage and hygiene workflows.
- **Scope-gated writes.** Write and delete tools register only when `LINKWARDEN_MCP_WRITE_SCOPES` or `LINKWARDEN_MCP_DELETE_SCOPES` names their domain. With no scopes the host sees no mutating tool at all.
- **Delete is never implied by write.** Deletes and tag merges need `LINKWARDEN_MCP_DELETE_SCOPES`, separate from write scopes.
- **Hard denylist** in the HTTP client: tokens, session, auth, user admin (except `GET /api/v1/users/me`), migration export and import, and whole-instance preservation jobs stay blocked at every scope.
- **Dry run by default** for bulk workflows (`apply_triage_plan`, `bulk_sort_by_rules`, `auto_tag_by_domain`).
- **Bulk cap.** Every bulk operation refuses more than `LINKWARDEN_MAX_BULK` records (default 25).
- **Safe collection delete.** `delete_collection` asks the user, through MCP elicitation, whether to delete, move or keep the links inside first.
- **Name resolution.** Tools take collection and tag names, and fail loud on unknown or ambiguous names.
- **Fail-fast start.** The server checks `GET /api/v1/users/me` at start-up, and rejects unknown scopes, wildcards and legacy write flags.
- **Companion agent skill** in [`skills/linkwarden-bookmarks/SKILL.md`](skills/linkwarden-bookmarks/SKILL.md), plus a Cursor plugin and a Claude Desktop Extension bundle.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and a Linkwarden access token. In Linkwarden, open **Settings > Access Tokens** (`/settings/access-tokens`), create a token and copy it.

1. Check that the package runs. With no configuration it stops with `LINKWARDEN_API_URL is required`:

   ```bash
   uvx linkwarden-mcp
   ```

2. Add the server to your MCP host. For Claude Code:

   ```bash
   claude mcp add linkwarden --env LINKWARDEN_API_URL=https://links.example.com --env LINKWARDEN_API_KEY=<your-token> -- uvx linkwarden-mcp
   ```

3. Restart the host, then ask: *"Find my unread bookmarks about Python"* or *"What is in my Dev collection?"*

Set `LINKWARDEN_API_URL` to the instance base URL, for example `https://links.example.com` or `http://127.0.0.1:3000` for local Docker. Add `/api/v1` only if your deployment needs it. The server sends the token as `Authorization: Bearer <token>`.

<details>
<summary><strong>Cursor</strong></summary>

**Plugin (Configure UI for URL, key and scopes):** this repo is a Cursor plugin through [`.cursor-plugin/plugin.json`](.cursor-plugin/plugin.json) and the root [`mcp.json`](mcp.json).

1. Link or copy the clone to `~/.cursor/plugins/local/linkwarden-mcp`.
   - macOS and Linux: `ln -s /path/to/linkwarden-mcp ~/.cursor/plugins/local/linkwarden-mcp`
   - Windows: Cursor does not follow symlinks for local plugins. Use a junction or a copy:
     ```bat
     mklink /J "%USERPROFILE%\.cursor\plugins\local\linkwarden-mcp" "<path-to-clone>"
     ```
2. Reload the window.
3. Open **Plugins > Configure** on `linkwarden-mcp`. Set **Linkwarden API URL** and **Linkwarden API key**. Leave **Write scopes** and **Delete scopes** empty for read-only.
4. Confirm that the `linkwarden` MCP server is on under Customize > MCP.

**Manual config:** project `.cursor/mcp.json` or user-wide `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "linkwarden": {
      "type": "stdio",
      "command": "uvx",
      "args": ["linkwarden-mcp"],
      "env": {
        "LINKWARDEN_API_URL": "https://links.example.com",
        "LINKWARDEN_API_KEY": "<your-token>"
      }
    }
  }
}
```

The root `mcp.json` is plugin wiring with `${...}` placeholders only. Never commit real secrets there.

</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

**Desktop Extension:** download [`mcpb.mcpb`](https://github.com/flumpiey/linkwarden-mcp/releases/latest/download/mcpb.mcpb) from [GitHub Releases](https://github.com/flumpiey/linkwarden-mcp/releases). It needs v0.1.5 or later and `uv` on `PATH`; it launches `uv tool run --python 3.12 linkwarden-mcp`.

1. Open Claude Desktop **Settings > Extensions**.
2. Open **Advanced settings > Install Extension...** and select `mcpb.mcpb`.
3. Enter **Linkwarden API URL** and **Linkwarden API key**, then click **Install**.
4. Leave **Write scopes** and **Delete scopes** empty for read-only.

On Windows, a double-click often does nothing, and a drag into chat attaches the file instead of installing it. Use **Install Extension...**.

**Manual config:** edit `claude_desktop_config.json` (macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`), then restart:

```json
{
  "mcpServers": {
    "linkwarden": {
      "command": "uvx",
      "args": ["linkwarden-mcp"],
      "env": {
        "LINKWARDEN_API_URL": "https://links.example.com",
        "LINKWARDEN_API_KEY": "<your-token>"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>VS Code / GitHub Copilot</strong></summary>

Create `.vscode/mcp.json` in the project root:

```json
{
  "servers": {
    "linkwarden": {
      "type": "stdio",
      "command": "uvx",
      "args": ["linkwarden-mcp"],
      "env": {
        "LINKWARDEN_API_URL": "https://links.example.com",
        "LINKWARDEN_API_KEY": "<your-token>"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Windsurf, Zed, Cline, Continue and other stdio hosts</strong></summary>

Every stdio host needs the same three values:

| Field | Value |
|-------|-------|
| Command | `uvx` |
| Args | `linkwarden-mcp` |
| Env | `LINKWARDEN_API_URL`, `LINKWARDEN_API_KEY`, optional scopes |

- Windsurf: `~/.codeium/windsurf/mcp_config.json`, key `mcpServers`.
- Zed: `settings.json`, key `context_servers`.
- Cline: `cline_mcp_settings.json`, key `mcpServers`.
- Continue: `.continue/config.yaml`, list `mcpServers` with `name`, `command`, `args`, `env`.

From a clone, use `uv run --directory /path/to/linkwarden-mcp linkwarden-mcp`. This is a Python package: `npx` does not run it.

</details>

## Configuration

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `LINKWARDEN_API_URL` | yes | none | Linkwarden base URL. `LINKWARDEN_URL` is a fallback alias. |
| `LINKWARDEN_API_KEY` | yes | none | Access token, sent as a Bearer token. `LINKWARDEN_TOKEN` is a fallback alias. |
| `LINKWARDEN_MCP_WRITE_SCOPES` | no | empty (read-only) | Comma-separated scopes for create and update tools. |
| `LINKWARDEN_MCP_DELETE_SCOPES` | no | empty | Comma-separated scopes for delete and merge tools. Write scopes never imply these. |
| `LINKWARDEN_MAX_BULK` | no | `25` | Largest number of records in one bulk operation. Must be 1 or more. |

- Valid scopes: `links`, `collections`, `tags`, `raw`. `raw` expands to all three domain scopes.
- Wildcards (`*`, `all`) and unknown names stop the server at start-up.
- The legacy flags `LINKWARDEN_MCP_ALLOW_WRITES`, `ALLOW_WRITES` and `LINKWARDEN_MCP_WRITES` stop the server if set.
- Recommended for most bookmark work: `LINKWARDEN_MCP_WRITE_SCOPES=links,collections` and `LINKWARDEN_MCP_DELETE_SCOPES=links`.

Copy [`.env.example`](.env.example) to `.env` for local runs. Never commit `.env`.

## Tools

No scopes: 18 tools. All three domain scopes in both variables: 31 tools. Call `list_resources` to see the live scopes and boundary.

| Tool | Access | Needs | What it does |
|------|--------|-------|--------------|
| `list_resources` | read | none | Reports `read_only`, write and delete scopes, and the boundary text |
| `search_links` | read | none | Searches by query, collection, tag or pin status; `limit` defaults to 50 |
| `get_link` | read | none | Returns full metadata for one link |
| `read_link_content` | read | none | Returns preserved plain text, with archive fallback |
| `list_collections` | read | none | Lists collections with link counts, in your Linkwarden order (no sort) |
| `list_tags` | read | none | Lists all tags with link counts; sort includes `link_count_desc`/`link_count_asc` |
| `get_library_overview` | read | none | Totals, empty collections and unused tags |
| `suggest_collection_for_url` | read | none | Heuristic collection suggestions for a URL |
| `suggest_tags_for_link` | read | none | Suggests existing tags; never invents names |
| `find_unsorted_links` | read | none | Lists links in the unsorted collection (default Unorganized) |
| `triage_links` | read | none | Proposes a collection and tags for link ids |
| `find_duplicate_links` | read | none | Groups links with the same normalised URL |
| `recommend_collection_for_links` | read | none | Consensus collection for a batch of links |
| `suggest_links_for_collection` | read | none | Finds links elsewhere that likely belong in a collection |
| `analyze_collection_overlap` | read | none | Compares two collections by domains, tags and URLs |
| `suggest_collection_structure` | read | none | Flags empty, near-duplicate and overcrowded collections |
| `align_tags_with_similar_links` | read | none | Tags used on links from similar domains |
| `get_sorting_dashboard` | read | none | One-shot triage: unsorted, duplicates, empty, largest |
| `save_link` | write | WRITE `links` | Saves a URL into a named collection |
| `smart_save_link` | write | WRITE `links` | Saves a URL with heuristic collection and tags |
| `organise_links` | write | WRITE `links` | Moves or retags several links |
| `update_link` | write | WRITE `links` | Updates name, URL, description, collection or tags (read, modify, write) |
| `queue_archive` | write | WRITE `links` | Queues preservation; runs async |
| `apply_triage_plan` | write | WRITE `links` | Applies `[{link_id, collection?, tags?}]`, adding tags to existing ones; `dry_run=true` by default |
| `bulk_sort_by_rules` | write | WRITE `links` | Sorts links by `domain_pattern` rules (exact host or subdomain), adding tags; `dry_run=true` by default |
| `create_collection` | write | WRITE `collections` | Creates a collection, optional parent |
| `auto_tag_by_domain` | write | WRITE `links` + `tags` | Applies domain-to-tag rules; `dry_run=true` by default |
| `delete_links` | delete | DELETE `links` | Deletes several links |
| `delete_tags` | delete | DELETE `tags` | Deletes tags by id or name |
| `merge_tags` | delete | DELETE `tags` | Merges tags into a new name |
| `delete_collection` | delete | DELETE `collections` | Deletes a collection after the user picks delete, move or cancel for its links; refuses a collection with sub-collections |

### Permission and safety model

1. **Registration gate.** At start-up the server registers only the tools that the scopes allow. A host cannot call a tool that does not exist.
2. **Call gate.** Each mutating tool checks its scope again before it runs.
3. **Client gate.** The HTTP client checks every request against the scope map and the denylist, whatever tool sent it.
4. **Annotations.** Read tools carry `readOnlyHint`. Delete tools carry `destructiveHint`, so hosts can ask for confirmation.
5. **Limits.** Bulk calls stop above `LINKWARDEN_MAX_BULK`. Bulk workflows preview by default.

`delete_collection` with links inside also needs DELETE `links` to delete them, or WRITE `links` to move them.

## Limits

- One process serves one `LINKWARDEN_API_URL`.
- Multi-user use on a shared instance is not verified.
- Suggestions are heuristic and local to your library.
- Transport is stdio only. Hosts that need a remote HTTP endpoint, such as ChatGPT Apps, cannot use it.

## Development

```bash
uv sync --extra dev
npm install
uv run ruff check src tests
uv run pytest
```

- `npm install` installs lefthook and commitlint and registers the git hooks.
- The test suite is offline and uses `respx` mocks. It needs no Linkwarden instance.
- `pre-commit` runs `ruff check` and `pytest`. `commit-msg` enforces Conventional Commits.
- `npm run pre-publish` runs the release gate: ruff, pytest, sdist contents, `python -m build`, `twine check` and `npx @anthropic-ai/mcpb pack mcpb`.
- CI runs ruff and pytest on Python 3.10 and 3.12. A published GitHub Release uploads to PyPI and the MCP Registry.

## Licence

MIT. See [LICENSE](LICENSE).

---

Built by Dru Connold. [flumpiey.github.io](https://flumpiey.github.io) | [malvadev.com](https://malvadev.com)
