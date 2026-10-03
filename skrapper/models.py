from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
    def normalized_url(self) -> str:
        parsed = urlsplit(self.url)
        query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if not key.lower().startswith(("utm_", "yclid", "gclid", "fbclid"))
            ],
            doseq=True,
        )
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), query, ""))

    @property
    def fingerprint(self) -> str:
        price = str(self.price or "")
        rooms = str(self.rooms or "")
        location = (self.location or "").casefold()
        title = self.title.casefold()
        return "|".join(part.strip() for part in [self.source, title, price, rooms, location])

    @property
    def published_or_now(self) -> datetime:
        return self.published_at or datetime.now(timezone.utc)
