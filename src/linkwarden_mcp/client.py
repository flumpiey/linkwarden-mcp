"""httpx client with source-tree denylist."""

from __future__ import annotations

import json as jsonlib
from typing import Any
from urllib.parse import urlparse

import httpx

from linkwarden_mcp.errors import ApiError, DeniedPathError
from linkwarden_mcp.scopes import WRITE_METHODS, WritePolicy

DENIED_PREFIXES = (
    "/api/v1/tokens",
    "/api/v1/session",
    "/api/v1/auth",
)

WHOLE_INSTANCE_PRESERVATION = frozenset({"preserveAll", "rePreserveAll"})


def _normalise_path(path: str) -> str:
    parsed = urlparse(path)
    return parsed.path.rstrip("/") or "/"


def deny_reason(method: str, path: str, *, json: Any = None) -> str | None:
    """Return denial reason or None if allowed."""
    method = method.upper()
    norm = _normalise_path(path)

    for prefix in DENIED_PREFIXES:
        if norm.startswith(prefix):
            return f"{method} {norm} is denied (sensitive route {prefix})."

    if norm.startswith("/api/v1/users") and not (method == "GET" and norm.endswith("/me")):
        return f"{method} {norm} is denied (user admin). Only GET /api/v1/users/me is allowed."

    if norm == "/api/v1/migration" and method in {"GET", "POST"}:
        return f"{method} {norm} is denied (full library export/import)."

    if norm == "/api/v1/worker/preservation" and method == "POST":
        action = (json or {}).get("action") if isinstance(json, dict) else None
        if action in WHOLE_INSTANCE_PRESERVATION:
            return f"POST {norm} with action={action!r} is denied (whole-instance preservation)."

    if norm == "/api/v1/links/archive" and method == "DELETE":
        link_ids = (json or {}).get("linkIds") if isinstance(json, dict) else None
        if not link_ids:
            return "DELETE /api/v1/links/archive without linkIds is denied."

    return None


def normalize_response(data: Any) -> Any:
    if isinstance(data, dict) and set(data.keys()) == {"response"}:
        return data["response"]
    return data


def parse_tags_payload(data: Any) -> tuple[list[dict[str, Any]], Any | None]:
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        inner = data["data"]
        tags = inner.get("tags") or []
        if isinstance(tags, list):
            return tags, inner.get("nextCursor")
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"], None
    if isinstance(data, list):
        return data, None
    return [], None


def parse_links_payload(data: Any) -> list[dict[str, Any]]:
    """Normalize search/list link payloads to a list of link dicts."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    inner = data.get("data")
    if isinstance(inner, dict):
        links = inner.get("links") or inner.get("data") or []
        return [x for x in links if isinstance(x, dict)] if isinstance(links, list) else []
    if isinstance(inner, list):
        return [x for x in inner if isinstance(x, dict)]
    links = data.get("links")
    if isinstance(links, list):
        return [x for x in links if isinstance(x, dict)]
    return []


def extract_api_message(response: httpx.Response) -> str:
    text = (response.text or "").strip()
    if not text:
        return f"Linkwarden HTTP {response.status_code}"
    try:
        payload = response.json()
    except jsonlib.JSONDecodeError:
        return text[:300]
    if isinstance(payload, dict):
        for key in ("message", "error", "detail"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return text[:300]


class LinkwardenClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        client: httpx.AsyncClient | None = None,
        policy: WritePolicy | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.policy = policy or WritePolicy(frozenset(), frozenset())
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token.strip()}"},
            timeout=60.0,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        method = method.upper()
        url_path = path if path.startswith("/") else f"/{path}"
        reason = deny_reason(method, url_path, json=json)
        if reason:
            raise DeniedPathError(reason)
        if method in WRITE_METHODS:
            self.policy.authorize(method, url_path)
        try:
            response = await self._client.request(
                method, url_path, params=params, json=json
            )
        except httpx.RequestError as exc:
            raise ApiError(
                f"Linkwarden unreachable at {self.base_url}. Check LINKWARDEN_API_URL. Detail: {exc}"
            ) from exc
        if response.status_code >= 400:
            raise ApiError(extract_api_message(response), status=response.status_code)
        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return normalize_response(response.json())
        return response.text

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, *, json: Any = None) -> Any:
        return await self.request("POST", path, json=json)

    async def put(self, path: str, *, json: Any = None) -> Any:
        return await self.request("PUT", path, json=json)

    async def delete(self, path: str, *, json: Any = None) -> Any:
        return await self.request("DELETE", path, json=json)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
