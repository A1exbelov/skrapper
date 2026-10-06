import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser, Node

from skrapper.models import Listing
from skrapper.sources.avito import clean_text, parse_price, parse_rooms
from skrapper.sources.base import ListingSource


class GdeEtotDomSource(ListingSource):
    source_name = "gdeetotdom"
    url_markers = (
        "/obj/living/",
        "gdeetotdom.ru/obj/living/",
    )

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, url: str) -> list[Listing]:
        response = await self.client.get(url)
        response.raise_for_status()

        parser = HTMLParser(response.text)
        listings: dict[str, Listing] = {}
        for card in parser.css(".c-card"):
            listing = self._parse_card(card, url)
            if listing is not None:
                listings.setdefault(listing.stable_key, listing)
        return list(listings.values())

    def _parse_card(self, card: Node, base_url: str) -> Listing | None:
        link = card.css_first("a.c-card__title")
        if link is None:
            return None

        href = link.attributes.get("href") or ""
        external_id_match = re.search(r"/obj/living/[^/]+/(\d+)/", href)
        if not external_id_match:
            return None

        title = clean_text(link.text())
        if not title:
            return None

        text = clean_text(card.text())
        return Listing(
            external_id=external_id_match.group(1),
            source=self.source_name,
            title=title,
            url=urljoin(base_url, href),
            price=extract_price(text),
            rooms=parse_rooms(title),
            location=extract_location(text, title),
            description=extract_description(text),
            image_url=extract_image_url(card, base_url),
        )


def extract_price(text: str) -> int | None:
    match = re.search(r"На карте\s+(\d{1,3}(?:\s\d{3})+)", text)
    if match:
        return int(match.group(1).replace(" ", ""))
    return parse_price(text)


def extract_location(text: str, title: str) -> str | None:
    if title not in text or "На карте" not in text:
        return None
    location = text.split(title, 1)[1].split("На карте", 1)[0]
    return clean_text(location) or None


def extract_description(text: str) -> str | None:
    marker = "Еще объявления"
    if marker not in text:
        return None
    return clean_text(text.split(marker, 1)[1]) or None


def extract_image_url(card: Node, base_url: str) -> str | None:
    image = card.css_first("img")
    if image is None:
        return None
    for attribute in ("src", "data-src", "srcset"):
        value = image.attributes.get(attribute)
        if value:
            return urljoin(base_url, value.split()[0])
    return None
