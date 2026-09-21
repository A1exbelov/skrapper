import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from skrapper.models import Listing
from skrapper.sources.avito import clean_text, parse_price, parse_rooms
from skrapper.sources.base import ListingSource

logger = logging.getLogger(__name__)


class RssSource(ListingSource):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, url: str) -> list[Listing]:
        response = await self.client.get(url)
        if response.status_code == 429:
            logger.warning("RSS source rate limit hit: 429 Too Many Requests. url=%s", url)
            return []
        response.raise_for_status()

        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        if not items:
            items = root.findall("{http://www.w3.org/2005/Atom}entry")
        return [listing for item in items if (listing := parse_feed_item(item)) is not None]


def parse_feed_item(item: ET.Element) -> Listing | None:
    title = text(item, "title")
    url = text(item, "link")
    if not url:
        link = item.find("{http://www.w3.org/2005/Atom}link")
        url = link.attrib.get("href") if link is not None else None
    if not title or not url:
        return None

    description = text(item, "description") or text(item, "summary")
    guid = text(item, "guid") or url

    return Listing(
        external_id=guid,
        source="rss",
        title=clean_text(title),
        url=url,
        price=parse_price(" ".join(part for part in [title, description or ""] if part)),
        rooms=parse_rooms(" ".join(part for part in [title, description or ""] if part)),
        description=clean_text(description or "") or None,
        published_at=parse_date(text(item, "pubDate") or text(item, "updated")),
    )


def text(item: ET.Element, name: str) -> str | None:
    node = item.find(name) or item.find(f"{{http://www.w3.org/2005/Atom}}{name}")
    if node is None or node.text is None:
        return None
    return node.text.strip()


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
