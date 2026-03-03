from pathlib import Path

from fastapi.testclient import TestClient

from link_garden.index import entry_from_bookmark, save_index
from link_garden.model import Bookmark
from link_garden.storage import init_storage, relative_to_root, write_bookmark
from link_garden.web.app import create_app


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


def test_web_responses_include_security_headers(tmp_path: Path) -> None:
    _seed_bookmark(tmp_path, bookmark_id="headers01", url="https://example.com", body="hello")
    app = create_app(repo_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


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

