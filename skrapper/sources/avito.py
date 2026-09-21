import re
import logging
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser, Node

from skrapper.models import Listing
from skrapper.sources.base import ListingSource


PRICE_RE = re.compile(r"(\d[\d\s]{2,})")
ROOMS_RE = re.compile(r"(?<!\d)([1-5])[-\s]?(?:к|комн|комнат)", re.IGNORECASE)
logger = logging.getLogger(__name__)


class AvitoSource(ListingSource):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, url: str) -> list[Listing]:
        response = await self.client.get(url)
        response.raise_for_status()

        parser = HTMLParser(response.text)
        cards = find_cards(parser)
        if not cards:
            title = parser.css_first("title")
            body = parser.body.text(separator=" ", strip=True) if parser.body else ""
            logger.warning(
                "Avito returned no listing cards. title=%r body_preview=%r",
                clean_text(title.text()) if title else "",
                clean_text(body)[:180],
            )

        listings = [self._parse_card(card, url) for card in cards]
        return [listing for listing in listings if listing is not None]

    def _parse_card(self, card: Node, base_url: str) -> Listing | None:
        link = card.css_first('[data-marker="item-title"]')
        if link is None:
            link = card.css_first("a[itemprop='url']")
        if link is None:
            return None

        href = link.attributes.get("href")
        if not href:
            return None

        title = clean_text(link.text())
        absolute_url = urljoin(base_url, href)
        external_id = extract_external_id(absolute_url)

        price_node = card.css_first('[data-marker="item-price"]')
        location_node = card.css_first('[data-marker="item-address"]')
        description_node = card.css_first('[data-marker="item-specific-params"]')
        image_node = card.css_first("img")

        price_text = clean_text(price_node.text()) if price_node else ""
        description = clean_text(description_node.text()) if description_node else None
        image_url = image_node.attributes.get("src") if image_node else None

        return Listing(
            external_id=external_id,
            source="avito",
            title=title,
            url=absolute_url,
            price=parse_price(price_text),
            rooms=parse_rooms(" ".join(part for part in [title, description or ""] if part)),
            location=clean_text(location_node.text()) if location_node else None,
            description=description,
            image_url=image_url,
        )


def clean_text(value: str) -> str:
    return " ".join(value.split())


def find_cards(parser: HTMLParser) -> list[Node]:
    selectors = [
        '[data-marker="item"]',
        '[data-marker^="item-"]',
        '[data-item-id]',
        "div[itemtype='http://schema.org/Product']",
    ]
    for selector in selectors:
        cards = parser.css(selector)
        if cards:
            return cards
    return []


def parse_price(value: str) -> int | None:
    match = PRICE_RE.search(value.replace("\xa0", " "))
    if not match:
        return None
    return int(match.group(1).replace(" ", ""))


def parse_rooms(value: str) -> int | None:
    match = ROOMS_RE.search(value)
    if not match:
        return None
    return int(match.group(1))


def extract_external_id(url: str) -> str:
    path = urlparse(url).path
    tail = path.rstrip("/").rsplit("_", maxsplit=1)[-1]
    return tail if tail.isdigit() else path
