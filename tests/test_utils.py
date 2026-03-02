from link_garden.utils import build_bookmark_filename, normalize_url


def test_build_bookmark_filename_is_sanitized_and_deterministic() -> None:
    saved_at = "2026-03-02T12:34:56Z"
    title = 'A <bad> "title" / with : chars?*'
    bookmark_id = "ABC123XYZ9"
    filename = build_bookmark_filename(saved_at=saved_at, title=title, bookmark_id=bookmark_id)

    assert filename == "20260302T123456Z__a-bad-title-with-chars__abc123xyz9.md"
    assert all(char not in filename for char in '<>:"/\\|?*')


def test_normalize_url_removes_utm_trailing_slash_and_fragment() -> None:
    raw = "HTTPS://Example.COM/Path/?utm_source=x&a=2&b=1&utm_medium=y#frag"
    normalized = normalize_url(raw)
    assert normalized == "https://example.com/Path?a=2&b=1"


def test_normalize_url_drops_default_https_port() -> None:
    raw = "https://example.com:443/docs/"
    normalized = normalize_url(raw)
    assert normalized == "https://example.com/docs"
