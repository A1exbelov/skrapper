import json
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser, Node

from skrapper.models import Listing
from skrapper.sources.avito import clean_text, parse_price, parse_rooms
from skrapper.sources.base import ListingSource

logger = logging.getLogger(__name__)


class GenericHtmlSource(ListingSource):
    source_name = "html"
    card_selectors: tuple[str, ...] = ()
    title_selectors: tuple[str, ...] = ("a", "h2", "h3")
    price_selectors: tuple[str, ...] = ()
    location_selectors: tuple[str, ...] = ()
    description_selectors: tuple[str, ...] = ()

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, url: str) -> list[Listing]:
        response = await self.client.get(url)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            logger.warning(
                "%s rate limit hit: 429 Too Many Requests. retry_after=%s url=%s",
                self.source_name,
                retry_after or "unknown",
                url,
            )
            return []
        if response.status_code in {403, 503}:
            logger.warning("%s blocked or unavailable: status=%s url=%s", self.source_name, response.status_code, url)
            return []

        response.raise_for_status()

        parser = HTMLParser(response.text)
        listings = self._parse_cards(parser, url)
        if listings:
            return listings

        json_ld_listings = parse_json_ld_listings(response.text, url, self.source_name)
        if json_ld_listings:
            logger.info("Parsed %d %s listings from JSON-LD", len(json_ld_listings), self.source_name)
            return json_ld_listings

        title = parser.css_first("title")
        logger.warning(
            "%s returned no listing cards. title=%r",
            self.source_name,
            clean_text(title.text()) if title else "",
        )
        return []

    def _parse_cards(self, parser: HTMLParser, base_url: str) -> list[Listing]:
        listings: dict[str, Listing] = {}
        for selector in self.card_selectors:
            for card in parser.css(selector):
                listing = self._parse_card(card, base_url)
                if listing is not None:
                    listings.setdefault(listing.stable_key, listing)
            if listings:
                return list(listings.values())
        return []

    def _parse_card(self, card: Node, base_url: str) -> Listing | None:
        link = first_node(card, self.title_selectors)
        if link is None:
            return None

        href = link.attributes.get("href")
        if not href:
            link = card.css_first("a[href]")
            href = link.attributes.get("href") if link else None
        if not href:
            return None

        title = clean_text(link.text())
        if not title:
            return None

        absolute_url = urljoin(base_url, href)
        external_id = extract_external_id(absolute_url)
        description = node_text(card, self.description_selectors)

        return Listing(
            external_id=external_id,
            source=self.source_name,
            title=title,
            url=absolute_url,
            price=parse_price(node_text(card, self.price_selectors) or ""),
            rooms=parse_rooms(" ".join(part for part in [title, description or ""] if part)),
            location=node_text(card, self.location_selectors),
            description=description,
            image_url=extract_image_url(card, base_url),
        )


def first_node(root: Node, selectors: tuple[str, ...]) -> Node | None:
    for selector in selectors:
        node = root.css_first(selector)
        if node is not None:
            return node
    return None


def node_text(root: Node, selectors: tuple[str, ...]) -> str | None:
    node = first_node(root, selectors)
    return clean_text(node.text()) if node else None


def extract_image_url(card: Node, base_url: str) -> str | None:
    image = card.css_first("img")
    if image is None:
        return None
    for attribute in ("src", "data-src", "srcset"):
        value = image.attributes.get(attribute)
        if value:
            return urljoin(base_url, value.split()[0])
    return None


def extract_external_id(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    match = re.search(r"(\d+)(?:/)?$", path)
    return match.group(1) if match else path


def parse_json_ld_listings(html: str, base_url: str, source_name: str) -> list[Listing]:
    parser = HTMLParser(html)
    listings: dict[str, Listing] = {}
    for script in parser.css('script[type="application/ld+json"]'):
        raw = script.text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in walk_json(data):
            if not isinstance(node, dict):
                continue
            listing = listing_from_json_ld(node, base_url, source_name)
            if listing is not None:
                listings.setdefault(listing.stable_key, listing)
    return list(listings.values())


def walk_json(value: object) -> list[object]:
    stack = [value]
    result = []
    while stack:
        current = stack.pop()
        result.append(current)
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return result


def listing_from_json_ld(data: dict, base_url: str, source_name: str) -> Listing | None:
    raw_url = data.get("url")
    title = data.get("name") or data.get("title")
    if not isinstance(raw_url, str) or not isinstance(title, str):
        return None

    absolute_url = urljoin(base_url, raw_url)
    price = None
    offers = data.get("offers")
    if isinstance(offers, dict):
        price = parse_price(str(offers.get("price") or offers.get("lowPrice") or ""))

    return Listing(
        external_id=extract_external_id(absolute_url),
        source=source_name,
        title=clean_text(title),
        url=absolute_url,
        price=price,
        rooms=parse_rooms(title),
        location=json_ld_location(data),
        description=clean_text(data.get("description", "")) or None,
        image_url=json_ld_image(data, base_url),
    )


def json_ld_location(data: dict) -> str | None:
    address = data.get("address")
    if isinstance(address, str):
        return clean_text(address)
    if isinstance(address, dict):
        parts = [
            address.get("addressLocality"),
            address.get("streetAddress"),
            address.get("addressRegion"),
        ]
        text = ", ".join(str(part) for part in parts if part)
        return clean_text(text) or None
    return None


def json_ld_image(data: dict, base_url: str) -> str | None:
    image = data.get("image")
    if isinstance(image, str):
        return urljoin(base_url, image)
    if isinstance(image, list) and image and isinstance(image[0], str):
        return urljoin(base_url, image[0])
    return None
