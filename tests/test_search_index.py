from pathlib import Path

from link_garden.index import load_index, rebuild_index_with_report, search_entries
from link_garden.model import Bookmark
from link_garden.storage import init_storage, write_bookmark


def test_search_text_contains_notes_and_description_and_respects_archived_filter(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    active = Bookmark(
        id="search1",
        title="Protein Notes",
        url="https://example.com/alpha",
        tags=["biology"],
        saved_at="2026-03-02T00:00:00Z",
        source="manual",
        folder_path="bookmark_bar/Research",
        chrome_guid=None,
        notes="focus on GPCR pathways",
        archived=False,
        description="A compact receptor overview",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body="## Highlights\nThe receptor pathways are *important*.",
    )
    archived = Bookmark(
        id="search2",
        title="Archived Doc",
        url="https://example.com/beta",
        tags=["archive"],
        saved_at="2026-03-01T00:00:00Z",
        source="manual",
        folder_path="bookmark_bar/Research",
        chrome_guid=None,
        notes="legacy reference",
        archived=True,
        description="Old note",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body="legacy content",
    )
    write_bookmark(paths, active)
    write_bookmark(paths, archived)

    report = rebuild_index_with_report(paths)
    assert report.indexed == 2

    entries = load_index(paths)
    entry_map = {entry.id: entry for entry in entries}
    assert "receptor pathways" in entry_map["search1"].search_text
    assert "compact receptor overview" in entry_map["search1"].search_text

    default_results = search_entries(entries, search="legacy")
    assert [item.id for item in default_results] == []

    archived_results = search_entries(entries, search="legacy", include_archived=True)
    assert [item.id for item in archived_results] == ["search2"]
