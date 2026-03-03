from __future__ import annotations

import json
from math import ceil
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import markdown
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from link_garden.bookmarks import BookmarkRecord, find_records_by_url, load_record_by_id, persist_record
from link_garden.config import load_config
from link_garden.enrich import apply_enrichment_to_bookmark, fetch_url_metadata
from link_garden.index import find_duplicate_entries, load_index, search_entries
from link_garden.model import Bookmark, IndexEntry
from link_garden.storage import init_storage, read_bookmark_file, relative_to_root, write_bookmark
from link_garden.utils import generate_short_id, normalize_folder_path, split_tags, utc_now_iso
from link_garden.web.theme import compile_theme, resolve_theme_file


def _entry_domain(url: str) -> str:
    return urlsplit(url).netloc or "-"


def _build_page_url(page: int, per_page: int, search: str, tag: str, folder: str, include_archived: bool) -> str:
    params: dict[str, str | int] = {"page": page, "per_page": per_page, "include_archived": int(include_archived)}
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


def _entry_rows(entries: list[IndexEntry]) -> list[dict[str, object]]:
    return [
        {
            "id": entry.id,
            "title": entry.title,
            "url": entry.url,
            "tags": entry.tags,
            "saved_at": entry.saved_at,
            "folder_path": entry.folder_path,
            "domain": _entry_domain(entry.url),
            "archived": entry.archived,
            "description": entry.description,
        }
        for entry in entries
    ]


def _build_folder_tree(entries: list[IndexEntry]) -> list[dict[str, object]]:
    root: dict[str, dict[str, object]] = {}

    for entry in entries:
        folder_path = normalize_folder_path(entry.folder_path)
        if not folder_path:
            continue
        parts = [part for part in folder_path.split("/") if part]
        current_level = root
        path_parts: list[str] = []
        for part in parts:
            path_parts.append(part)
            key = "/".join(path_parts)
            node = current_level.setdefault(
                part,
                {
                    "name": part,
                    "path": key,
                    "count": 0,
                    "children": {},
                },
            )
            node["count"] = int(node["count"]) + 1
            current_level = node["children"]  # type: ignore[assignment]

    def _render(nodes: dict[str, dict[str, object]]) -> list[dict[str, object]]:
        rendered: list[dict[str, object]] = []
        for name in sorted(nodes.keys()):
            node = nodes[name]
            rendered.append(
                {
                    "name": node["name"],
                    "path": node["path"],
                    "count": node["count"],
                    "children": _render(node["children"]),  # type: ignore[arg-type]
                }
            )
        return rendered

    return _render(root)


def _write_guard(enable_write: bool, enable_capture: bool, is_capture: bool = False) -> None:
    if enable_write:
        return
    if is_capture and enable_capture:
        return
    raise HTTPException(status_code=403, detail="Write endpoints are disabled. Start server with --enable-write.")


def create_app(
    repo_dir: Path,
    data_dir: Path | None = None,
    *,
    enable_write: bool = False,
    enable_capture: bool = False,
    capture_enrich: bool = False,
) -> FastAPI:
    paths = init_storage(repo_dir, data_dir=data_dir)
    app_config, _ = load_config(Path(repo_dir).resolve())
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
        include_archived: bool = Query(False),
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
    ) -> HTMLResponse:
        entries = load_index(paths)
        filtered = search_entries(
            entries,
            search=search,
            tag=tag,
            folder=folder,
            include_archived=include_archived,
        )
        total = len(filtered)
        total_pages = max(1, ceil(total / per_page)) if total else 1
        if page > total_pages:
            page = total_pages
        start = (page - 1) * per_page
        page_entries = filtered[start : start + per_page]

        rows = _entry_rows(page_entries)
        all_tags = sorted({tag_item for entry in entries if include_archived or not entry.archived for tag_item in entry.tags})
        all_folders = sorted({entry.folder_path for entry in entries if entry.folder_path and (include_archived or not entry.archived)})
        folder_tree = _build_folder_tree([entry for entry in entries if include_archived or not entry.archived])
        prev_url = _build_page_url(page - 1, per_page, search, tag, folder, include_archived) if page > 1 else None
        next_url = _build_page_url(page + 1, per_page, search, tag, folder, include_archived) if page < total_pages else None

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
                "include_archived": include_archived,
                "folder_tree": folder_tree,
                "enable_write": enable_write,
                "enable_capture": enable_capture,
                "view": "all",
            },
        )

    @app.get("/recent", response_class=HTMLResponse)
    def recent(
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        include_archived: bool = Query(False),
    ) -> HTMLResponse:
        entries = load_index(paths)
        filtered = search_entries(entries, include_archived=include_archived)[:limit]
        rows = _entry_rows(filtered)
        folder_tree = _build_folder_tree([entry for entry in entries if include_archived or not entry.archived])
        return templates.TemplateResponse(
            name="index.html",
            request=request,
            context={
                "rows": rows,
                "search": "",
                "tag": "",
                "folder": "",
                "all_tags": sorted({tag_item for entry in entries for tag_item in entry.tags}),
                "all_folders": sorted({entry.folder_path for entry in entries if entry.folder_path}),
                "page": 1,
                "per_page": limit,
                "total": len(rows),
                "total_pages": 1,
                "prev_url": None,
                "next_url": None,
                "include_archived": include_archived,
                "folder_tree": folder_tree,
                "enable_write": enable_write,
                "enable_capture": enable_capture,
                "view": "recent",
            },
        )

    @app.get("/duplicates", response_class=HTMLResponse)
    def duplicates(request: Request, include_archived: bool = Query(False)) -> HTMLResponse:
        entries = load_index(paths)
        filtered = entries if include_archived else [entry for entry in entries if not entry.archived]
        groups = find_duplicate_entries(filtered)
        folder_tree = _build_folder_tree(filtered)
        return templates.TemplateResponse(
            name="duplicates.html",
            request=request,
            context={
                "groups": groups,
                "include_archived": include_archived,
                "enable_write": enable_write,
                "enable_capture": enable_capture,
                "folder_tree": folder_tree,
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
                "enable_write": enable_write,
                "enable_capture": enable_capture,
            },
        )

    @app.post("/api/bookmarks/{bookmark_id}/tags")
    def update_tags(
        bookmark_id: str,
        add: str = Form(""),
        remove: str = Form(""),
        set_tags: str = Form(""),
    ) -> RedirectResponse:
        _write_guard(enable_write, enable_capture)
        record = load_record_by_id(paths, bookmark_id)
        tags = record.bookmark.tags
        if set_tags.strip():
            tags = split_tags(set_tags)
        if add.strip():
            tags = _merge_tags(tags, split_tags(add))
        if remove.strip():
            remove_set = {item.lower() for item in split_tags(remove)}
            tags = [item for item in tags if item.lower() not in remove_set]
        record.bookmark.tags = tags
        persist_record(paths, record, rename_file=False)
        return RedirectResponse(url=f"/bookmark/{bookmark_id}", status_code=303)

    @app.post("/api/bookmarks/{bookmark_id}/archive")
    def update_archive(
        bookmark_id: str,
        archived: str = Form("toggle"),
    ) -> RedirectResponse:
        _write_guard(enable_write, enable_capture)
        record = load_record_by_id(paths, bookmark_id)
        if archived == "toggle":
            record.bookmark.archived = not record.bookmark.archived
        else:
            record.bookmark.archived = archived.strip().lower() in ("1", "true", "yes", "on")
        persist_record(paths, record, rename_file=False)
        return RedirectResponse(url=f"/bookmark/{bookmark_id}", status_code=303)

    @app.post("/api/bookmarks/{bookmark_id}/notes")
    def update_notes(
        bookmark_id: str,
        notes: str = Form(""),
    ) -> RedirectResponse:
        _write_guard(enable_write, enable_capture)
        record = load_record_by_id(paths, bookmark_id)
        text = notes.strip()
        record.bookmark.body = text
        record.bookmark.notes = text
        persist_record(paths, record, rename_file=False)
        return RedirectResponse(url=f"/bookmark/{bookmark_id}", status_code=303)

    @app.get("/capture")
    def capture(
        url: str = Query(..., min_length=1),
        title: str = "",
        tags: str = "",
        notes: str = "",
        folder: str = "",
        enrich: int = Query(0),
    ) -> RedirectResponse:
        _write_guard(enable_write, enable_capture, is_capture=True)
        records = find_records_by_url(paths, url, include_archived=True)
        existing_record = records[0] if records else None

        parsed_tags = split_tags(tags)
        note_text = notes.strip()

        if existing_record is not None:
            bookmark = existing_record.bookmark
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
            synced = persist_record(paths, existing_record, rename_file=False)
            if capture_enrich or enrich == 1:
                metadata = fetch_url_metadata(bookmark.url)
                if metadata.ok:
                    apply_enrichment_to_bookmark(synced.bookmark, metadata, overwrite_title=False)
                    persist_record(paths, synced, rename_file=False)
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
            description="",
            fetched_at=None,
            source_meta="",
            canonical_url=None,
            body=note_text,
            visibility=app_config.default_visibility,
        )
        created_path = write_bookmark(paths, bookmark)
        rel_path = relative_to_root(paths, created_path)
        created_record = persist_record(
            paths,
            BookmarkRecord(
                bookmark=bookmark,
                path=created_path,
                rel_path=rel_path,
                entry=IndexEntry(id=bookmark.id, title=bookmark.title, url=bookmark.url, tags=bookmark.tags, path=rel_path, saved_at=bookmark.saved_at),
            ),
            rename_file=False,
        )
        if capture_enrich or enrich == 1:
            metadata = fetch_url_metadata(bookmark.url)
            if metadata.ok:
                apply_enrichment_to_bookmark(created_record.bookmark, metadata, overwrite_title=False)
                persist_record(paths, created_record, rename_file=False)
        return RedirectResponse(url=f"/bookmark/{bookmark.id}", status_code=303)

    @app.get("/api/config")
    def config() -> JSONResponse:
        return JSONResponse(
            {
                "enable_write": enable_write,
                "enable_capture": enable_capture,
                "capture_enrich": capture_enrich,
            }
        )

    return app
