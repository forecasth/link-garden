from __future__ import annotations

from enum import Enum


class Visibility(str, Enum):
    private = "private"
    unlisted = "unlisted"
    public = "public"


class ExportScope(str, Enum):
    public = "public"
    unlisted = "unlisted"
    all = "all"


def visibility_allowed(visibility: Visibility, scope: ExportScope) -> bool:
    if scope == ExportScope.all:
        return True
    if scope == ExportScope.unlisted:
        return visibility in {Visibility.public, Visibility.unlisted}
    return visibility == Visibility.public


def scope_includes_private(scope: ExportScope) -> bool:
    return scope == ExportScope.all


def scope_is_broader_than_public(scope: ExportScope) -> bool:
    return scope in {ExportScope.unlisted, ExportScope.all}


def is_local_host(host: str) -> bool:
    cleaned = host.strip().lower()
    return cleaned in {"127.0.0.1", "localhost", "::1"}
