# MCP Tool Contracts

**Feature**: `001-linkwarden-mcp-server`  
**Transport**: stdio via FastMCP

All tools use verb prefixes for client approval hints. Annotations: read tools `readOnlyHint=true`; delete tools `destructiveHint=true`.

## Read tools

### search_links

- **Input**: `query` (str, optional), `collection` (str, optional), `tag` (str, optional), `pinned_only` (bool, optional), `sort` (enum: newest|oldest|name|name_desc, optional), `limit` (int, optional)
- **Output**: List of `{ id, name, url, collection, tags[], pinned, readable }`
- **Errors**: Unknown collection/tag name with suggestion to list first; ambiguous collection name (multiple matches) with match count and instruction to use collection id

### get_link

- **Input**: `link_id` (int, required)
- **Output**: Full link record fields agents need for follow-up edits

### read_link_content

- **Input**: `link_id` (int, required)
- **Output**: `{ text, source: "textContent"|"archive", truncated: bool, title?, excerpt? }` or `{ unavailable: str }`
- **Behavior**: textContent first; archive format 3 fallback; never empty string on missing content

### list_collections

- **Input**: `sort` (optional word)
- **Output**: Tree-friendly list with `{ id, name, parent, link_count, members? }`

### list_tags

- **Input**: `sort` (optional, includes tag_count_desc/asc)
- **Output**: `{ id, name, link_count }[]`

### get_library_overview

- **Input**: none
- **Output**: See `data-model.md` overview shape; `tags_partial` when pagination incomplete

## Write tools (LINKWARDEN_MCP_WRITE_SCOPES)

### save_link

- **Input**: `url` (required), `collection` (str, required), `tags` (str[], optional), `name`, `description`, `note` (optional)
- **Output**: `{ link_id, collection_id, collection_created: bool, message }`
- **Errors**: Duplicate url → plain "already saved"; ambiguous collection name → match count and instruction to use collection id

### organise_links

- **Input**: `link_ids` (int[], required, max bulk), `collection` (str, optional), `tags` (str[], optional)
- **Output**: `{ updated_count, message }`

### create_collection

- **Input**: `name` (required), `parent` (str, optional)
- **Output**: `{ id, name, parent_id, created: true }`

### update_link

- **Input**: `link_id` (required), optional `name`, `url`, `description`, `note`, `collection`, `tags`
- **Output**: Updated link summary

### queue_archive

- **Input**: `link_ids` (int[], max bulk)
- **Output**: `{ queued_count, message }` — always "queued", never "completed"

## Delete tools

### delete_links (LINKWARDEN_DELETE)

- **Input**: `link_ids` (int[], max bulk)
- **Output**: `{ deleted_count }`

### delete_tags (LINKWARDEN_DELETE)

- **Input**: `tag_ids` or `tag_names` (max bulk by count)
- **Output**: `{ deleted_count }`

### merge_tags (LINKWARDEN_DELETE)

- **Input**: `new_tag_name` (str), `tag_ids` (int[], min 1)
- **Pre-check**: Count affected links; refuse if > bulk cap
- **Pre-check**: Warn if `new_tag_name` already exists
- **Output**: `{ new_tag_id, links_moved, warning? }`
- **API**: `PUT /api/v1/tags/merge`

### delete_collection (LINKWARDEN_DELETE_COLLECTIONS)

- **Input**: `collection` (str or id)
- **Output**: `{ collection_id, links_removed_count }` — cascades all links

## Workflow tools (read — always registered)

Heuristic compose tools. Scans capped at 500 links per collection query. Never invent tag names outside library vocabulary.

### suggest_collection_for_url

- **Input**: `url` (required), `title`, `excerpt` (optional)
- **Output**: `{ url, suggestions: [{ name, score, reason }] }` (top 3)

### suggest_tags_for_link

- **Input**: `link_id` or `url`
- **Output**: `{ suggestions: [{ name, score, reason }], existing_tags }`

### find_unsorted_links

- **Input**: `limit` (default 50), `collection` (default `Unorganized`)
- **Output**: `{ count, links[], scan_capped_at }`

### triage_links

- **Input**: `link_ids` (max bulk)
- **Output**: `{ plans: [{ id, suggested_collection, suggested_tags, reasons }] }`

### find_duplicate_links

- **Input**: `collection` (optional), `limit` (default 500)
- **Output**: `{ duplicate_groups: [{ normalized_url, count, links }], group_count }`

### recommend_collection_for_links

- **Input**: `link_ids` (max bulk)
- **Output**: `{ recommended_collection, agreement_count, votes, per_link }`

### suggest_links_for_collection

- **Input**: `collection`, `limit` (default 25)
- **Output**: `{ candidates: [{ id, url, score, reason }], profile_domains }`

### analyze_collection_overlap

- **Input**: `collection_a`, `collection_b`
- **Output**: shared domains/tags/URLs + `merge_recommended`

### suggest_collection_structure

- **Input**: none
- **Output**: empty collections, near-duplicate names, overcrowded, unused tags

### align_tags_with_similar_links

- **Input**: `link_id`, `min_count` (default 2)
- **Output**: `{ suggestions: [{ name, count, reason }] }`

### get_sorting_dashboard

- **Input**: none
- **Output**: unsorted/duplicate counts, empty collections, largest collections

## Workflow tools (write — LINKWARDEN_MCP_WRITE_SCOPES)

Mutating workflow tools default to `dry_run=true`. Set `dry_run=false` to apply.

### smart_save_link

- **Input**: `url`, optional `collection`/`tags`/`name`/…, `auto_apply_suggestions` (default false)
- **Output**: save result + suggestions used

### apply_triage_plan

- **Input**: `plan: [{ link_id, collection?, tags? }]`, `dry_run` (default true)
- **Output**: `{ would_update | updated_count, failures? }` — bulk-capped

### auto_tag_by_domain

- **Input**: `link_ids`, `dry_run` (default true)
- **Output**: domain-rule tag proposals; applies only vocabulary matches

### bulk_sort_by_rules

- **Input**: `rules: [{ domain_pattern, collection?, tags? }]`, `dry_run` (default true), `collection` source (default Unorganized)
- **Output**: matches + optional apply; bulk-capped when applying

## Bulk cap

All multi-record tools enforce `LINKWARDEN_MAX_BULK` (default 25). Refusal message includes requested count and cap. No partial application.
