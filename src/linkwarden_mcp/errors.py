"""Shared exceptions."""

from __future__ import annotations


class ConfigError(ValueError):
    """Missing or invalid configuration."""


class DeniedPathError(PermissionError):
    """HTTP path blocked by client denylist."""


class ApiError(RuntimeError):
    """Linkwarden returned an HTTP error."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class BulkCapExceeded(ValueError):
    """Bulk operation exceeds LINKWARDEN_MAX_BULK."""

    def __init__(self, requested: int, cap: int) -> None:
        super().__init__(
            f"Requested {requested} records but bulk cap is {cap}. "
            "Reduce the batch size or raise LINKWARDEN_MAX_BULK."
        )
        self.requested = requested
        self.cap = cap


class AmbiguousNameError(ValueError):
    """Multiple entities match a name."""

    def __init__(self, kind: str, name: str, count: int) -> None:
        super().__init__(
            f"Ambiguous {kind} name {name!r}: {count} matches. "
            f"Use {kind} id instead."
        )
        self.kind = kind
        self.name = name
        self.count = count


class UnknownNameError(ValueError):
    """No entity matches a name."""

    def __init__(self, kind: str, name: str) -> None:
        super().__init__(f"Unknown {kind} {name!r}. List {kind}s first.")
        self.kind = kind
        self.name = name


def check_bulk_cap(count: int, cap: int) -> None:
    if count > cap:
        raise BulkCapExceeded(count, cap)
