from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from link_garden.security import ExportScope, Visibility


@dataclass(frozen=True)
class AppConfig:
    default_visibility: Visibility = Visibility.private
    export_default_scope: ExportScope = ExportScope.public
    serve_default_scope: ExportScope = ExportScope.public
    server_bind_host: str = "127.0.0.1"
    require_allow_remote: bool = True


def default_config() -> AppConfig:
    return AppConfig()


def config_path(root: Path) -> Path:
    return root / "config.yaml"


def ensure_config_file(root: Path) -> tuple[Path, bool]:
    path = config_path(root)
    if path.exists():
        return path, False

    default_map = {
        "default_visibility": Visibility.private.value,
        "export_default_scope": ExportScope.public.value,
        "serve_default_scope": ExportScope.public.value,
        "server_bind_host": "127.0.0.1",
        "require_allow_remote": True,
    }
    path.write_text(yaml.safe_dump(default_map, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return path, True


def load_config(root: Path) -> tuple[AppConfig, list[str]]:
    path = config_path(root)
    defaults = default_config()
    warnings: list[str] = []

    if not path.exists():
        return defaults, warnings

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Failed to parse config.yaml: {exc}. Secure defaults were used.")
        return defaults, warnings

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        warnings.append("config.yaml must be a YAML mapping. Secure defaults were used.")
        return defaults, warnings

    parsed_visibility = _parse_visibility(raw, "default_visibility", defaults.default_visibility, warnings)
    parsed_export_scope = _parse_scope(raw, "export_default_scope", defaults.export_default_scope, warnings)
    parsed_serve_scope = _parse_scope(raw, "serve_default_scope", defaults.serve_default_scope, warnings)
    parsed_server_host = _parse_host(raw, "server_bind_host", defaults.server_bind_host, warnings)
    parsed_require_allow_remote = _parse_bool(raw, "require_allow_remote", defaults.require_allow_remote, warnings)

    return (
        AppConfig(
            default_visibility=parsed_visibility,
            export_default_scope=parsed_export_scope,
            serve_default_scope=parsed_serve_scope,
            server_bind_host=parsed_server_host,
            require_allow_remote=parsed_require_allow_remote,
        ),
        warnings,
    )


def _parse_visibility(
    mapping: dict[str, Any],
    key: str,
    fallback: Visibility,
    warnings: list[str],
) -> Visibility:
    raw = mapping.get(key)
    if raw is None:
        return fallback
    try:
        return Visibility(str(raw).strip().lower())
    except ValueError:
        warnings.append(f"Invalid {key}={raw!r}. Using {fallback.value}.")
        return fallback


def _parse_scope(
    mapping: dict[str, Any],
    key: str,
    fallback: ExportScope,
    warnings: list[str],
) -> ExportScope:
    raw = mapping.get(key)
    if raw is None:
        return fallback
    try:
        return ExportScope(str(raw).strip().lower())
    except ValueError:
        warnings.append(f"Invalid {key}={raw!r}. Using {fallback.value}.")
        return fallback


def _parse_bool(mapping: dict[str, Any], key: str, fallback: bool, warnings: list[str]) -> bool:
    raw = mapping.get(key)
    if raw is None:
        return fallback
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    warnings.append(f"Invalid {key}={raw!r}. Using {fallback}.")
    return fallback


def _parse_host(mapping: dict[str, Any], key: str, fallback: str, warnings: list[str]) -> str:
    raw = mapping.get(key)
    if raw is None:
        return fallback
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    warnings.append(f"Invalid {key}={raw!r}. Using {fallback}.")
    return fallback
