from link_garden.enrich import (
    EnrichMetadata,
    apply_enrichment_to_bookmark,
    extract_metadata_from_html,
    fetch_url_metadata,
)
from link_garden.model import Bookmark


def _bookmark() -> Bookmark:
    return Bookmark(
        id="enrich01",
        title="",
        url="https://example.com",
        tags=[],
        saved_at="2026-03-02T00:00:00Z",
        source="manual",
        folder_path="",
        chrome_guid=None,
        notes="",
        archived=False,
        description="",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body="",
    )


def test_extract_metadata_from_html() -> None:
    html = """
    <html>
      <head>
        <title>Example Title</title>
        <meta name="description" content="Example Description" />
        <link rel="canonical" href="https://example.com/canonical" />
      </head>
      <body>hello</body>
    </html>
    """
    title, description, canonical = extract_metadata_from_html(html)
    assert title == "Example Title"
    assert description == "Example Description"
    assert canonical == "https://example.com/canonical"


def test_fetch_url_metadata_handles_timeout_error() -> None:
    def fake_fetcher(url: str, timeout: float, user_agent: str, max_bytes: int) -> tuple[str, str]:
        raise TimeoutError("timed out")

    metadata = fetch_url_metadata("https://example.com", fetcher=fake_fetcher)
    assert metadata.ok is False
    assert "timed out" in (metadata.error or "")


def test_apply_enrichment_updates_bookmark_fields() -> None:
    bookmark = _bookmark()
    metadata = EnrichMetadata(
        requested_url=bookmark.url,
        ok=True,
        title="Fetched Title",
        description="Fetched Description",
        canonical_url="https://example.com/canonical",
        fetched_at="2026-03-02T01:00:00Z",
    )

    updated = apply_enrichment_to_bookmark(bookmark, metadata, overwrite_title=True)
    assert updated.title == "Fetched Title"
    assert updated.description == "Fetched Description"
    assert updated.canonical_url == "https://example.com/canonical"
    assert updated.fetched_at == "2026-03-02T01:00:00Z"
    assert updated.source_meta == "enrich"
