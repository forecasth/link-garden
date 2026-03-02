from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from link_garden.model import Bookmark
from link_garden.utils import normalize_url, utc_now_iso

DEFAULT_USER_AGENT = "link-garden/0.2 (+local)"
DEFAULT_MAX_BYTES = 500_000


@dataclass
class EnrichMetadata:
    requested_url: str
    final_url: str | None = None
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    fetched_at: str | None = None
    ok: bool = False
    error: str | None = None


class _MetadataHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_title = False
        self.title_parts: list[str] = []
        self.description: str | None = None
        self.canonical_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        lower_tag = tag.lower()
        if lower_tag == "title":
            self._inside_title = True
            return
        if lower_tag == "meta":
            key = (attr_map.get("name") or attr_map.get("property") or "").lower()
            if key in ("description", "og:description") and not self.description:
                content = attr_map.get("content", "").strip()
                if content:
                    self.description = content
            return
        if lower_tag == "link":
            rel = attr_map.get("rel", "").lower()
            href = attr_map.get("href", "").strip()
            if "canonical" in rel and href and not self.canonical_url:
                self.canonical_url = href

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            stripped = data.strip()
            if stripped:
                self.title_parts.append(stripped)

    @property
    def title(self) -> str | None:
        if not self.title_parts:
            return None
        return " ".join(self.title_parts).strip() or None


def extract_metadata_from_html(html_text: str) -> tuple[str | None, str | None, str | None]:
    parser = _MetadataHTMLParser()
    parser.feed(html_text)
    return parser.title, parser.description, parser.canonical_url


def fetch_html(
    url: str,
    timeout: float,
    user_agent: str,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[str, str]:
    request = Request(url=url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            content = content[:max_bytes]
        charset = response.headers.get_content_charset() or "utf-8"
        decoded = content.decode(charset, errors="replace")
        final_url = response.geturl()
    return decoded, final_url


def fetch_url_metadata(
    url: str,
    *,
    timeout: float = 5.0,
    user_agent: str = DEFAULT_USER_AGENT,
    no_network: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    fetcher: Callable[[str, float, str, int], tuple[str, str]] = fetch_html,
) -> EnrichMetadata:
    result = EnrichMetadata(requested_url=url)
    if no_network:
        result.error = "Network disabled (--no-network)"
        return result

    try:
        html_text, final_url = fetcher(url, timeout, user_agent, max_bytes)
    except (TimeoutError, URLError, OSError, ValueError) as exc:
        result.error = str(exc)
        return result

    title, description, canonical_url = extract_metadata_from_html(html_text)
    result.ok = True
    result.final_url = final_url
    result.title = title
    result.description = description
    result.canonical_url = canonical_url
    result.fetched_at = utc_now_iso()
    return result


def apply_enrichment_to_bookmark(
    bookmark: Bookmark,
    metadata: EnrichMetadata,
    *,
    overwrite_title: bool = False,
) -> Bookmark:
    if not metadata.ok:
        return bookmark

    if metadata.description:
        bookmark.description = metadata.description
    if metadata.canonical_url:
        bookmark.canonical_url = metadata.canonical_url
    if metadata.fetched_at:
        bookmark.fetched_at = metadata.fetched_at
    bookmark.source_meta = "enrich"

    if metadata.title and (overwrite_title or not bookmark.title.strip() or bookmark.title == bookmark.url):
        bookmark.title = metadata.title

    if metadata.final_url and not bookmark.url.strip():
        bookmark.url = normalize_url(metadata.final_url)
    return bookmark
