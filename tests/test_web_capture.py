from pathlib import Path

from fastapi.testclient import TestClient

from link_garden.index import load_index
from link_garden.storage import init_storage, read_bookmark_file
from link_garden.web.app import MAX_NOTES_LENGTH, MAX_TAGS, MAX_TITLE_LENGTH, create_app


def test_capture_endpoint_creates_bookmark_and_redirects(tmp_path: Path) -> None:
    app = create_app(repo_dir=tmp_path, enable_capture=True)
    client = TestClient(app)

    response = client.get(
        "/capture",
        params={
            "url": "https://example.com/path",
            "title": "Captured Example",
            "tags": "capture,example",
            "notes": "hello from bookmarklet",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/bookmark/")

    paths = init_storage(tmp_path)
    entries = load_index(paths)
    assert len(entries) == 1
    assert entries[0].title == "Captured Example"

    detail = client.get(location)
    assert detail.status_code == 200
    assert "Captured Example" in detail.text
    assert "hello from bookmarklet" in detail.text


def test_capture_endpoint_dedupes_by_normalized_url(tmp_path: Path) -> None:
    app = create_app(repo_dir=tmp_path, enable_capture=True)
    client = TestClient(app)

    first = client.get(
        "/capture",
        params={"url": "https://example.com/path/", "title": "One", "tags": "tag1"},
        follow_redirects=False,
    )
    assert first.status_code == 303

    second = client.get(
        "/capture",
        params={
            "url": "https://example.com/path/?utm_source=feed",
            "title": "Two",
            "tags": "tag2",
            "notes": "extra note",
        },
        follow_redirects=False,
    )
    assert second.status_code == 303

    paths = init_storage(tmp_path)
    entries = load_index(paths)
    assert len(entries) == 1
    entry = entries[0]
    bookmark_path = (paths.root / entry.path).resolve()
    bookmark = read_bookmark_file(bookmark_path)

    assert bookmark.title == "Two"
    assert bookmark.tags == ["tag1", "tag2"]
    assert "extra note" in bookmark.body


def test_capture_endpoint_forbidden_when_write_and_capture_disabled(tmp_path: Path) -> None:
    app = create_app(repo_dir=tmp_path)
    client = TestClient(app)
    response = client.get("/capture", params={"url": "https://example.com"}, follow_redirects=False)
    assert response.status_code == 403


def test_capture_endpoint_supports_post(tmp_path: Path) -> None:
    app = create_app(repo_dir=tmp_path, enable_capture=True)
    client = TestClient(app)

    response = client.post(
        "/capture",
        data={
            "url": "https://example.com/post",
            "title": "Captured Via Post",
            "tags": "capture,post",
            "notes": "post path",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/bookmark/")

    paths = init_storage(tmp_path)
    entries = load_index(paths)
    assert len(entries) == 1
    assert entries[0].title == "Captured Via Post"


def test_capture_post_rejects_overlong_title(tmp_path: Path) -> None:
    app = create_app(repo_dir=tmp_path, enable_capture=True)
    client = TestClient(app)

    response = client.post(
        "/capture",
        data={"url": "https://example.com/limit", "title": "t" * (MAX_TITLE_LENGTH + 1)},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "title exceeds max length" in response.json()["detail"]


def test_capture_get_rejects_overlong_notes(tmp_path: Path) -> None:
    app = create_app(repo_dir=tmp_path, enable_capture=True)
    client = TestClient(app)

    response = client.get(
        "/capture",
        params={"url": "https://example.com/limit", "notes": "n" * (MAX_NOTES_LENGTH + 1)},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "notes exceeds max length" in response.json()["detail"]


def test_capture_post_rejects_too_many_tags(tmp_path: Path) -> None:
    app = create_app(repo_dir=tmp_path, enable_capture=True)
    client = TestClient(app)
    tags = ",".join(f"tag{i}" for i in range(MAX_TAGS + 1))

    response = client.post(
        "/capture",
        data={"url": "https://example.com/limit", "tags": tags},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "max tag count" in response.json()["detail"]
