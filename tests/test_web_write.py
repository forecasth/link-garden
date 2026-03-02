from pathlib import Path

from fastapi.testclient import TestClient

from link_garden.index import entry_from_bookmark, load_index, save_index
from link_garden.model import Bookmark
from link_garden.storage import init_storage, read_bookmark_file, relative_to_root, write_bookmark
from link_garden.web.app import create_app


def _seed(tmp_path: Path) -> str:
    paths = init_storage(tmp_path)
    bookmark = Bookmark(
        id="webwrite01",
        title="Web Write",
        url="https://example.com",
        tags=["one"],
        saved_at="2026-03-02T00:00:00Z",
        source="manual",
        folder_path="bookmark_bar/Test",
        chrome_guid=None,
        notes="seed",
        archived=False,
        description="",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body="seed",
    )
    path = write_bookmark(paths, bookmark)
    save_index(paths, [entry_from_bookmark(bookmark, relative_to_root(paths, path))])
    return bookmark.id


def test_web_write_endpoints_return_403_when_disabled(tmp_path: Path) -> None:
    bookmark_id = _seed(tmp_path)
    app = create_app(repo_dir=tmp_path, enable_write=False)
    client = TestClient(app)

    response = client.post(f"/api/bookmarks/{bookmark_id}/tags", data={"add": "two"}, follow_redirects=False)
    assert response.status_code == 403


def test_web_write_endpoints_persist_updates_when_enabled(tmp_path: Path) -> None:
    bookmark_id = _seed(tmp_path)
    app = create_app(repo_dir=tmp_path, enable_write=True)
    client = TestClient(app)

    tags_resp = client.post(
        f"/api/bookmarks/{bookmark_id}/tags",
        data={"add": "two,three", "remove": "one"},
        follow_redirects=False,
    )
    assert tags_resp.status_code == 303

    archive_resp = client.post(f"/api/bookmarks/{bookmark_id}/archive", data={"archived": "1"}, follow_redirects=False)
    assert archive_resp.status_code == 303

    notes_resp = client.post(
        f"/api/bookmarks/{bookmark_id}/notes",
        data={"notes": "updated notes body"},
        follow_redirects=False,
    )
    assert notes_resp.status_code == 303

    paths = init_storage(tmp_path)
    entry = load_index(paths)[0]
    bookmark = read_bookmark_file((paths.root / entry.path).resolve())
    assert bookmark.tags == ["two", "three"]
    assert bookmark.archived is True
    assert bookmark.body == "updated notes body"
    assert entry.archived is True
    assert entry.tags == ["two", "three"]
