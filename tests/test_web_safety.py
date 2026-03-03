from pathlib import Path

from fastapi.testclient import TestClient

from link_garden.index import entry_from_bookmark, save_index
from link_garden.model import Bookmark
from link_garden.storage import init_storage, relative_to_root, write_bookmark
from link_garden.web.app import WEB_LIST_DEFAULT_LIMIT, WEB_LIST_MAX_LIMIT, create_app


def _seed_bookmark(tmp_path: Path, *, bookmark_id: str, url: str, body: str) -> None:
    paths = init_storage(tmp_path)
    bookmark = Bookmark(
        id=bookmark_id,
        title="Safety Test",
        url=url,
        tags=["security"],
        saved_at="2026-03-03T00:00:00Z",
        source="manual",
        folder_path="bookmark_bar/Security",
        chrome_guid=None,
        notes=body,
        archived=False,
        description="",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body=body,
    )
    path = write_bookmark(paths, bookmark)
    save_index(paths, [entry_from_bookmark(bookmark, relative_to_root(paths, path))])


def _seed_many_bookmarks(tmp_path: Path, count: int) -> None:
    paths = init_storage(tmp_path)
    entries = []
    for index in range(count):
        bookmark = Bookmark(
            id=f"bulk{index:03d}",
            title=f"Bookmark {index:03d}",
            url=f"https://example.com/{index}",
            tags=["bulk"],
            saved_at=f"2026-03-03T00:{index % 60:02d}:00Z",
            source="manual",
            folder_path="bookmark_bar/Bulk",
            chrome_guid=None,
            notes="",
            archived=False,
            description="",
            fetched_at=None,
            source_meta="",
            canonical_url=None,
            body="",
        )
        path = write_bookmark(paths, bookmark)
        entries.append(entry_from_bookmark(bookmark, relative_to_root(paths, path)))
    save_index(paths, entries)


def test_web_responses_include_security_headers(tmp_path: Path) -> None:
    _seed_bookmark(tmp_path, bookmark_id="headers01", url="https://example.com", body="hello")
    app = create_app(repo_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "charset=utf-8" in response.headers.get("content-type", "").lower()

    api_response = client.get("/api/config")
    assert api_response.status_code == 200
    assert "charset=utf-8" in api_response.headers.get("content-type", "").lower()


def test_web_detail_sanitizes_script_and_javascript_urls(tmp_path: Path) -> None:
    _seed_bookmark(
        tmp_path,
        bookmark_id="xss01",
        url="javascript:alert(1)",
        body="<script>alert(1)</script>\n[bad](javascript:alert(1))\n[good](https://example.com/docs)",
    )
    app = create_app(repo_dir=tmp_path)
    client = TestClient(app)

    detail = client.get("/bookmark/xss01")
    assert detail.status_code == 200
    text = detail.text.lower()
    assert "<script" not in text
    assert 'href="javascript:alert(1)"' not in text
    assert "open url disabled (unsafe scheme)" in text
    assert 'href="https://example.com/docs"' in text


def test_web_index_does_not_render_clickable_javascript_bookmark_url(tmp_path: Path) -> None:
    _seed_bookmark(tmp_path, bookmark_id="xss02", url="javascript:alert(1)", body="unsafe url in index")
    app = create_app(repo_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    text = response.text.lower()
    assert 'href="javascript:alert(1)"' not in text
    assert "open url disabled (unsafe scheme)" in text


def test_web_list_default_limit_and_clamp(tmp_path: Path) -> None:
    _seed_many_bookmarks(tmp_path, WEB_LIST_MAX_LIMIT + 20)
    app = create_app(repo_dir=tmp_path)
    client = TestClient(app)

    default_response = client.get("/")
    assert default_response.status_code == 200
    assert f"Showing {WEB_LIST_DEFAULT_LIMIT} of {WEB_LIST_MAX_LIMIT + 20} bookmark(s)" in default_response.text

    clamped_response = client.get("/?limit=999")
    assert clamped_response.status_code == 200
    assert f"Showing {WEB_LIST_MAX_LIMIT} of {WEB_LIST_MAX_LIMIT + 20} bookmark(s)" in clamped_response.text


def test_web_list_offset_window(tmp_path: Path) -> None:
    _seed_many_bookmarks(tmp_path, 120)
    app = create_app(repo_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/?limit=10&offset=20")
    assert response.status_code == 200
    assert "Showing 10 of 120 bookmark(s)" in response.text
