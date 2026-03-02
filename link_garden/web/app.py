from __future__ import annotations

import json
from math import ceil
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import markdown
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from link_garden.index import entry_from_bookmark, load_index, save_index, upsert_entry
from link_garden.model import Bookmark, IndexEntry
from link_garden.storage import init_storage, read_bookmark_file, relative_to_root, write_bookmark
from link_garden.utils import generate_short_id, normalize_folder_path, normalize_url, split_tags, utc_now_iso
from link_garden.web.theme import compile_theme, resolve_theme_file


def _filter_entries(
    entries: list[IndexEntry],
    search: str | None = None,
    tag: str | None = None,
    folder: str | None = None,
) -> list[IndexEntry]:
    filtered = entries
    if tag:
        tag_key = tag.lower().strip()
        filtered = [entry for entry in filtered if any(existing.lower() == tag_key for existing in entry.tags)]
    if folder:
        prefix = normalize_folder_path(folder)
        filtered = [entry for entry in filtered if normalize_folder_path(entry.folder_path).startswith(prefix)]
    if search:
        needle = search.lower().strip()
        matching: list[IndexEntry] = []
        for entry in filtered:
            haystack = " ".join([entry.title, entry.url, " ".join(entry.tags), entry.folder_path]).lower()
            if needle in haystack:
                matching.append(entry)
        filtered = matching
    return sorted(filtered, key=lambda item: item.saved_at, reverse=True)


def _entry_domain(url: str) -> str:
    return urlsplit(url).netloc or "-"


def _build_page_url(page: int, per_page: int, search: str, tag: str, folder: str) -> str:
    params: dict[str, str | int] = {"page": page, "per_page": per_page}
    if search:
        params["search"] = search
    if tag:
        params["tag"] = tag
    if folder:
        params["folder"] = folder
    return "/?" + urlencode(params)


def _merge_tags(existing: list[str], new_values: list[str]) -> list[str]:
    seen = {item.lower() for item in existing}
    merged = existing[:]
    for value in new_values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(value)
    return merged


def create_app(repo_dir: Path, data_dir: Path | None = None) -> FastAPI:
    paths = init_storage(repo_dir, data_dir=data_dir)
    module_dir = Path(__file__).resolve().parent
    static_dir = module_dir / "static"
    templates = Jinja2Templates(directory=str(module_dir / "templates"))

    theme_file = resolve_theme_file(Path(repo_dir).resolve())
    compile_theme(theme_file, static_dir / "theme.css")

    app = FastAPI(title="link-garden")
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(
        request: Request,
        search: str = "",
        tag: str = "",
        folder: str = "",
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
    ) -> HTMLResponse:
        entries = load_index(paths)
        filtered = _filter_entries(entries, search=search, tag=tag, folder=folder)
        total = len(filtered)
        total_pages = max(1, ceil(total / per_page)) if total else 1
        if page > total_pages:
            page = total_pages
        start = (page - 1) * per_page
        page_entries = filtered[start : start + per_page]

        rows = [
            {
                "id": entry.id,
                "title": entry.title,
                "url": entry.url,
                "tags": entry.tags,
                "saved_at": entry.saved_at,
                "folder_path": entry.folder_path,
                "domain": _entry_domain(entry.url),
            }
            for entry in page_entries
        ]
        all_tags = sorted({tag_item for entry in entries for tag_item in entry.tags})
        all_folders = sorted({entry.folder_path for entry in entries if entry.folder_path})
        prev_url = _build_page_url(page - 1, per_page, search, tag, folder) if page > 1 else None
        next_url = _build_page_url(page + 1, per_page, search, tag, folder) if page < total_pages else None

        return templates.TemplateResponse(
            name="index.html",
            request=request,
            context={
                "rows": rows,
                "search": search,
                "tag": tag,
                "folder": folder,
                "all_tags": all_tags,
                "all_folders": all_folders,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "prev_url": prev_url,
                "next_url": next_url,
            },
        )

    @app.get("/bookmark/{bookmark_id}", response_class=HTMLResponse)
    def bookmark_detail(request: Request, bookmark_id: str) -> HTMLResponse:
        entries = load_index(paths)
        match = next((entry for entry in entries if entry.id == bookmark_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        bookmark_path = (paths.root / match.path).resolve()
        bookmark = read_bookmark_file(bookmark_path)
        body_html = markdown.markdown(bookmark.body or "", extensions=["extra"])
        frontmatter_text = json.dumps(bookmark.to_frontmatter(), indent=2)
        return templates.TemplateResponse(
            name="detail.html",
            request=request,
            context={
                "bookmark": bookmark,
                "body_html": body_html,
                "frontmatter_text": frontmatter_text,
                "source_path": match.path,
            },
        )

    @app.get("/capture")
    def capture(
        url: str = Query(..., min_length=1),
        title: str = "",
        tags: str = "",
        notes: str = "",
        folder: str = "",
    ) -> RedirectResponse:
        entries = load_index(paths)
        normalized = normalize_url(url)
        existing_entry = next((entry for entry in entries if normalize_url(entry.url) == normalized), None)

        parsed_tags = split_tags(tags)
        note_text = notes.strip()

        if existing_entry is not None:
            bookmark_path = (paths.root / existing_entry.path).resolve()
            bookmark = read_bookmark_file(bookmark_path)
            if title.strip():
                bookmark.title = title.strip()
            if folder.strip():
                bookmark.folder_path = normalize_folder_path(folder)
            if parsed_tags:
                bookmark.tags = _merge_tags(bookmark.tags, parsed_tags)
            if note_text:
                if bookmark.body:
                    if note_text not in bookmark.body:
                        bookmark.body = f"{bookmark.body}\n\n{note_text}"
                else:
                    bookmark.body = note_text
                if not bookmark.notes:
                    bookmark.notes = note_text
            bookmark.source = "capture"
            bookmark.url = url.strip()
            write_bookmark(paths, bookmark, existing_path=bookmark_path)
            entries = upsert_entry(entries, entry_from_bookmark(bookmark, existing_entry.path))
            save_index(paths, entries)
            return RedirectResponse(url=f"/bookmark/{bookmark.id}", status_code=303)

        bookmark = Bookmark(
            id=generate_short_id(),
            title=title.strip() or url.strip(),
            url=url.strip(),
            tags=parsed_tags,
            saved_at=utc_now_iso(),
            source="capture",
            folder_path=normalize_folder_path(folder),
            chrome_guid=None,
            notes=note_text,
            archived=False,
            body=note_text,
        )
        created_path = write_bookmark(paths, bookmark)
        rel_path = relative_to_root(paths, created_path)
        entries = upsert_entry(entries, entry_from_bookmark(bookmark, rel_path))
        save_index(paths, entries)
        return RedirectResponse(url=f"/bookmark/{bookmark.id}", status_code=303)

    return app
