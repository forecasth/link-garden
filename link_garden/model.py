from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Bookmark(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    url: str
    tags: list[str] = Field(default_factory=list)
    saved_at: str
    source: str = "manual"
    folder_path: str = ""
    chrome_guid: str | None = None
    notes: str = ""
    archived: bool = False
    body: str = ""

    def to_frontmatter(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "tags": self.tags,
            "saved_at": self.saved_at,
            "source": self.source,
            "folder_path": self.folder_path,
            "chrome_guid": self.chrome_guid,
            "notes": self.notes,
            "archived": self.archived,
        }


class IndexEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    url: str
    tags: list[str] = Field(default_factory=list)
    path: str
    saved_at: str
    folder_path: str = ""
    chrome_guid: str | None = None
