import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser, Node

from skrapper.models import Listing
from skrapper.sources.avito import clean_text, parse_rooms
from skrapper.sources.base import ListingSource

LISTING_HREF_RE = re.compile(r"/prodaja/kvartira/.+-r(\d+)\.html")
PRICE_RE = re.compile(r"(\d{1,3}(?:\s\d{3})+)\s*₽")


class AkulaSource(ListingSource):
    source_name = "akula"
    url_markers = (
        "/prodaja/kvartira/",
        "saratov.akula.com/prodaja/kvartira/",
    )

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, url: str) -> list[Listing]:
        response = await self.client.get(url)
        response.raise_for_status()

        parser = HTMLParser(response.text)
        listings: dict[str, Listing] = {}
        for card in parser.css(".offer-snippet"):
            listing = self._parse_card(card, url)
            if listing is not None:
                listings.setdefault(listing.stable_key, listing)
        return list(listings.values())

    def _parse_card(self, card: Node, base_url: str) -> Listing | None:
        link = card.css_first('a[href*="/prodaja/kvartira/"][href*="-r"]')
        if link is None:
            return None

        href = link.attributes.get("href") or ""
        match = LISTING_HREF_RE.search(href)
        if not match:
            return None

        text = clean_text(card.text())
        title = extract_title(text, href)
        return Listing(
            external_id=match.group(1),
            source=self.source_name,
            title=title,
            url=urljoin(base_url, href),
            price=extract_price(text),
            rooms=parse_rooms(title),
            location=extract_location(text),
            description=extract_description(text),
            image_url=extract_image_url(card, base_url),
        )


def extract_title(text: str, href: str) -> str:
    title_match = re.search(r"(\d+\s*м²\s*,\s*[1-5][-\s]комнатн\w+\s+квартир\w*)", text)
    if title_match:
        raw = title_match.group(1)
        rooms = parse_rooms(raw)
        area_match = re.search(r"(\d+(?:[,.]\d+)?)\s*м²", raw)
        if rooms and area_match:
            return f"{rooms}-комнатная квартира, {area_match.group(1).replace(',', '.')} м²"
        return raw

    slug = href.rstrip("/").rsplit("/", 1)[-1].split("-r", 1)[0]
    return clean_text(slug.replace("-", " "))


def extract_price(text: str) -> int | None:
    match = PRICE_RE.search(text)
    if not match:
        return None
    return int(match.group(1).replace(" ", ""))


def extract_location(text: str) -> str | None:
    if "Подробнее" not in text:
        return None
    location = text.rsplit("Подробнее", 1)[0].split("...", 1)[-1].strip()
    return clean_text(location) or None


def extract_description(text: str) -> str | None:
    parts = text.split("этаж", 1)
    if len(parts) < 2:
        return None
    description = parts[1].split("Подробнее", 1)[0]
    return clean_text(description) or None


def extract_image_url(card: Node, base_url: str) -> str | None:
    image = card.css_first("img")
    if image is None:
        return None
    for attribute in ("src", "data-src", "srcset"):
        value = image.attributes.get(attribute)
        if value:
            return urljoin(base_url, value.split()[0])
    return None
