from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl


class ListingFilters(BaseModel):
    min_price: int | None = None
    max_price: int | None = None
    rooms: list[int] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class SearchConfig(BaseModel):
    name: str
    source: Literal["avito"]
    url: HttpUrl
    enabled: bool = True
    filters: ListingFilters = Field(default_factory=ListingFilters)


class NotificationConfig(BaseModel):
    max_items_per_run: int = 10


class AppConfig(BaseModel):
    searches: list[SearchConfig] = Field(default_factory=list)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    return AppConfig.model_validate(raw)

