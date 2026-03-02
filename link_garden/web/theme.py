from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

TOKEN_PREFIX = {
    "colors": "color",
    "typography": "type",
    "spacing": "space",
    "radius": "radius",
    "shadows": "shadow",
}
TOKEN_REF_RE = re.compile(r"^\{([a-zA-Z0-9_.-]+)\}$")
TOKEN_INLINE_RE = re.compile(r"\{([a-zA-Z0-9_.-]+)\}")


def resolve_theme_file(repo_dir: Path) -> Path:
    candidate = (repo_dir / "ui" / "theme.yaml").resolve()
    if candidate.exists():
        return candidate
    fallback = (Path(__file__).resolve().parents[2] / "ui" / "theme.yaml").resolve()
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Theme file not found at {candidate}")


def load_theme(theme_file: Path) -> dict[str, Any]:
    payload = yaml.safe_load(theme_file.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("theme.yaml must contain a top-level mapping")
    return payload


def _sanitize_name(value: str) -> str:
    return value.replace("_", "-").strip().lower()


def token_var_name(path: str) -> str:
    parts = [_sanitize_name(part) for part in path.split(".") if part.strip()]
    if not parts:
        raise ValueError("Invalid token path")
    head = TOKEN_PREFIX.get(parts[0], parts[0].rstrip("s"))
    return "--" + "-".join([head, *parts[1:]])


def _flatten_tokens(value: dict[str, Any], parent: str) -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, child in value.items():
        path = f"{parent}.{key}"
        if isinstance(child, dict):
            flat.update(_flatten_tokens(child, path))
        else:
            flat[path] = str(child)
    return flat


def _resolve_value(value: str) -> str:
    match = TOKEN_REF_RE.match(value.strip())
    if not match:
        return TOKEN_INLINE_RE.sub(lambda part: f"var({token_var_name(part.group(1))})", value)
    return f"var({token_var_name(match.group(1))})"


def render_theme_css(theme: dict[str, Any]) -> str:
    tokens: dict[str, str] = {}
    for section in ("colors", "typography", "spacing", "radius", "shadows"):
        raw_section = theme.get(section, {})
        if isinstance(raw_section, dict):
            tokens.update(_flatten_tokens(raw_section, section))

    lines: list[str] = [":root {"]
    for token_path, token_value in sorted(tokens.items()):
        lines.append(f"  {token_var_name(token_path)}: {token_value};")
    lines.append("}")
    lines.append("")
    lines.extend(
        [
            "* { box-sizing: border-box; }",
            "body { margin: 0; padding: 0; font-family: var(--type-family, 'IBM Plex Sans', 'Segoe UI', sans-serif); font-size: var(--type-base-size, 16px); line-height: 1.55; background: var(--color-bg); color: var(--color-text); }",
            "a { color: var(--color-accent); text-decoration: none; }",
            "a:hover { text-decoration: underline; }",
            "code, pre { font-family: 'Consolas', 'SFMono-Regular', monospace; background: var(--color-surface); }",
            "h1, h2, h3 { line-height: 1.2; margin-top: 0; }",
            ".layout { max-width: 980px; margin: 0 auto; padding: var(--space-lg); }",
            ".toolbar { display: grid; grid-template-columns: 1fr 180px 200px auto; gap: var(--space-sm); margin-bottom: var(--space-md); align-items: center; }",
            ".card { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-subtle); padding: var(--space-md); margin-bottom: var(--space-sm); }",
            ".btn { display: inline-block; border: 1px solid var(--color-border); background: var(--color-surface); color: var(--color-text); padding: var(--space-xs) var(--space-sm); border-radius: var(--radius-sm); cursor: pointer; }",
            ".btn:hover { border-color: var(--color-accent); color: var(--color-accent); text-decoration: none; }",
            ".input { width: 100%; border: 1px solid var(--color-border); background: #fff; color: var(--color-text); padding: var(--space-xs) var(--space-sm); border-radius: var(--radius-sm); }",
            ".tag { display: inline-block; border: 1px solid var(--color-border); border-radius: 999px; padding: 0.15rem 0.55rem; font-size: 0.85rem; margin-right: 0.35rem; margin-top: 0.2rem; }",
            ".badge { display: inline-block; border-radius: var(--radius-sm); background: var(--color-surface); border: 1px solid var(--color-border); padding: 0.1rem 0.45rem; font-size: 0.8rem; color: var(--color-muted); }",
            ".muted { color: var(--color-muted); }",
            ".meta { font-size: 0.9rem; color: var(--color-muted); margin-top: 0.35rem; }",
            ".row { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }",
            ".pagination { display: flex; gap: var(--space-sm); align-items: center; margin-top: var(--space-md); }",
            "@media (max-width: 800px) { .layout { padding: var(--space-md); } .toolbar { grid-template-columns: 1fr; } }",
        ]
    )

    components = theme.get("components", {})
    if isinstance(components, dict):
        for class_name, style_map in components.items():
            if not isinstance(style_map, dict):
                continue
            lines.append("")
            lines.append(f".{_sanitize_name(class_name)} {{")
            for property_name, value in style_map.items():
                css_property = _sanitize_name(str(property_name))
                css_value = _resolve_value(str(value))
                lines.append(f"  {css_property}: {css_value};")
            lines.append("}")
    return "\n".join(lines).rstrip() + "\n"


def compile_theme(theme_file: Path, output_css: Path) -> Path:
    theme = load_theme(theme_file)
    css = render_theme_css(theme)
    output_css.parent.mkdir(parents=True, exist_ok=True)
    output_css.write_text(css, encoding="utf-8")
    return output_css
