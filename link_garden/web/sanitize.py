from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

ALLOWED_TAGS = {
    "a",
    "p",
    "br",
    "hr",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}
VOID_TAGS = {"br", "hr"}
ALLOWED_LINK_SCHEMES = {"http", "https"}


def sanitize_link_url(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    parsed = urlsplit(cleaned)
    scheme = parsed.scheme.lower()
    if scheme in ALLOWED_LINK_SCHEMES and parsed.netloc:
        return cleaned
    return None


class _HTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized not in ALLOWED_TAGS:
            return
        rendered_attrs: list[str] = []
        if normalized == "a":
            href = ""
            title = ""
            for name, value in attrs:
                key = name.lower()
                raw = (value or "").strip()
                if key == "href":
                    href = raw
                elif key == "title":
                    title = raw
            safe_href = sanitize_link_url(href)
            if safe_href:
                rendered_attrs.append(f'href="{escape(safe_href, quote=True)}"')
                rendered_attrs.append('rel="noopener noreferrer nofollow"')
                rendered_attrs.append('target="_blank"')
            if title:
                rendered_attrs.append(f'title="{escape(title, quote=True)}"')
        attr_text = (" " + " ".join(rendered_attrs)) if rendered_attrs else ""
        self.parts.append(f"<{normalized}{attr_text}>")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in ALLOWED_TAGS and normalized not in VOID_TAGS:
            self.parts.append(f"</{normalized}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data))


def sanitize_html(value: str) -> str:
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(value)
    sanitizer.close()
    return "".join(sanitizer.parts)

