from __future__ import annotations

import base64
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

INVALID_FILENAME_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1F]")
MULTI_DASH_RE = re.compile(r"-{2,}")
SLUG_INVALID_RE = re.compile(r"[^a-z0-9]+")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
MARKDOWN_CODE_RE = re.compile(r"`([^`]+)`")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
MARKDOWN_PUNCT_RE = re.compile(r"[*_~>#-]+")
WHITESPACE_RE = re.compile(r"\s+")
URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def utc_now_iso() -> str:
    now = datetime.now(UTC).replace(microsecond=0)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def ensure_utc_iso(value: str) -> str:
    return parse_iso_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_short_id(length: int = 10) -> str:
    token = base64.b32encode(uuid.uuid4().bytes).decode("ascii").rstrip("=").lower()
    return token[:length]


def slugify(text: str, max_len: int = 64) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = SLUG_INVALID_RE.sub("-", ascii_text.lower()).strip("-")
    if not slug:
        slug = "untitled"
    return slug[:max_len].strip("-") or "untitled"


def sanitize_filename_component(value: str, max_len: int = 80) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("-", value)
    cleaned = cleaned.replace(" ", "-")
    cleaned = MULTI_DASH_RE.sub("-", cleaned).strip(" .-_")
    if not cleaned:
        cleaned = "item"
    return cleaned[:max_len]


def saved_at_filename_part(saved_at: str) -> str:
    parsed = parse_iso_utc(saved_at)
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def build_bookmark_filename(saved_at: str, title: str, bookmark_id: str) -> str:
    timestamp = saved_at_filename_part(saved_at)
    slug = slugify(title)
    short_id = sanitize_filename_component(bookmark_id.lower(), max_len=16)
    return f"{timestamp}__{slug}__{short_id}.md"


def normalize_folder_path(folder_path: str) -> str:
    cleaned = folder_path.replace("\\", "/").strip("/")
    cleaned = re.sub(r"/{2,}", "/", cleaned)
    return cleaned


def split_tags(raw_tags: str | list[str] | None) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, list):
        parts = raw_tags
    else:
        parts = raw_tags.split(",")

    output: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tag = part.strip()
        if not tag:
            continue
        tag_key = tag.lower()
        if tag_key in seen:
            continue
        seen.add(tag_key)
        output.append(tag)
    return output


def strip_markdown(text: str) -> str:
    value = MARKDOWN_LINK_RE.sub(r"\1", text)
    value = MARKDOWN_CODE_RE.sub(r"\1", value)
    value = MARKDOWN_HEADING_RE.sub("", value)
    value = MARKDOWN_PUNCT_RE.sub(" ", value)
    value = WHITESPACE_RE.sub(" ", value).strip()
    return value


def normalize_search_text(text: str) -> str:
    lowered = strip_markdown(text).lower()
    return WHITESPACE_RE.sub(" ", lowered).strip()


def normalize_url(url: str) -> str:
    stripped = url.strip()
    if not stripped:
        return ""
    candidate = stripped
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    elif not URI_SCHEME_RE.match(candidate):
        candidate = "https://" + candidate.lstrip("/")

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return candidate

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or ""

    if netloc:
        host, sep, port = netloc.partition(":")
        if sep and ((scheme == "http" and port == "80") or (scheme == "https" and port == "443")):
            netloc = host

    if path == "/":
        path = ""
    else:
        path = path.rstrip("/")

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [(k, v) for (k, v) in query_items if not k.lower().startswith("utm_")]
    filtered.sort(key=lambda item: (item[0], item[1]))
    query = urlencode(filtered, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def chrome_micros_to_iso(value: str | int | None) -> str | None:
    if value is None:
        return None
    try:
        micros = int(value)
    except (TypeError, ValueError):
        return None
    if micros <= 0:
        return None
    dt = datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=micros)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
