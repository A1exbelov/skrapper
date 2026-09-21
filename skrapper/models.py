from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class Listing:
    external_id: str
    source: str
    title: str
    url: str
    price: int | None = None
    rooms: int | None = None
    location: str | None = None
    description: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None

    @property
    def text_for_filtering(self) -> str:
        parts = [self.title, self.location or "", self.description or ""]
        return " ".join(parts).casefold()

    @property
    def stable_key(self) -> str:
        return f"{self.source}:{self.external_id}"

    @property
    def published_or_now(self) -> datetime:
        return self.published_at or datetime.now(timezone.utc)

