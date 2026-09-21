import json
import re
import logging
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser, Node

from skrapper.models import Listing
from skrapper.sources.base import ListingSource


PRICE_RE = re.compile(r"(\d[\d\s]{2,})")
ROOMS_RE = re.compile(r"(?<!\d)([1-5])[-\s]?(?:к|комн|комнат)", re.IGNORECASE)
HYDRATION_RE = re.compile(
    r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\("(.*?)"\);',
    re.DOTALL,
)
logger = logging.getLogger(__name__)


class AvitoSource(ListingSource):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, url: str) -> list[Listing]:
        response = await self.client.get(url)
        response.raise_for_status()

        parser = HTMLParser(response.text)
        cards = find_cards(parser)
        listings = [self._parse_card(card, url) for card in cards]
        if listings:
            return [listing for listing in listings if listing is not None]

        hydrated_listings = parse_hydration_listings(response.text, url)
        if hydrated_listings:
            logger.info("Parsed %d Avito listings from hydration data", len(hydrated_listings))
            return hydrated_listings

        if not cards:
            title = parser.css_first("title")
            body = parser.body.text(separator=" ", strip=True) if parser.body else ""
            logger.warning(
                "Avito returned no listing cards. title=%r body_preview=%r",
                clean_text(title.text()) if title else "",
                clean_text(body)[:180],
            )

        return []

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


def parse_hydration_listings(html: str, base_url: str) -> list[Listing]:
    data = extract_hydration_data(html)
    if data is None:
        return []

    listings: dict[str, Listing] = {}
    for node in walk_json(data):
        if not isinstance(node, dict):
            continue
        listing = listing_from_dict(node, base_url)
        if listing is not None:
            listings.setdefault(listing.stable_key, listing)
    return list(listings.values())


def extract_hydration_data(html: str) -> object | None:
    match = HYDRATION_RE.search(html)
    if not match:
        return None

    try:
        json_text = json.loads(f'"{match.group(1)}"')
        return json.loads(json_text)
    except json.JSONDecodeError:
        logger.warning("Failed to decode Avito hydration data", exc_info=True)
        return None


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


def listing_from_dict(data: dict, base_url: str) -> Listing | None:
    title = first_text(data, ("title", "name", "displayTitle", "header"))
    raw_url = first_text(data, ("url", "uri", "href", "urlPath", "path", "canonicalUrl"))
    external_id = first_text(data, ("id", "itemId", "adId", "listingId"))

    if not title or not raw_url:
        return None
    if not looks_like_listing_url(raw_url):
        return None

    absolute_url = urljoin(base_url, raw_url)
    if not external_id:
        external_id = extract_external_id(absolute_url)

    description = first_text(data, ("description", "snippet", "subtitle", "text"))
    location = extract_location(data)
    image_url = extract_image_url(data, base_url)

    return Listing(
        external_id=str(external_id),
        source="avito",
        title=title,
        url=absolute_url,
        price=extract_price(data),
        rooms=parse_rooms(" ".join(part for part in [title, description or ""] if part)),
        location=location,
        description=description,
        image_url=image_url,
    )


def looks_like_listing_url(value: str) -> bool:
    return "/kvartiry/" in value and bool(re.search(r"_\d+(?:\?|$)", value))


def first_text(data: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
        if isinstance(value, (int, float)):
            return str(value)
    return None


def first_int(data: dict, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = data.get(key)
        parsed = normalize_int(value)
        if parsed is not None:
            return parsed
        if isinstance(value, dict):
            nested = first_int(value, keys)
            if nested is not None:
                return nested
    return None


def extract_price(data: dict) -> int | None:
    price = first_int(data, ("price", "priceValue"))
    if price is not None:
        return price

    for key in ("price", "priceDetailed", "priceInfo"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = first_int(value, ("value", "amount", "price", "priceValue"))
            if nested is not None:
                return nested
            text = first_text(value, ("string", "formatted", "text", "title"))
            if text:
                return parse_price(text)

    text_price = first_text(data, ("priceString", "formattedPrice"))
    if text_price:
        return parse_price(text_price)
    return None


def normalize_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return parse_price(value)
    return None


def extract_location(data: dict) -> str | None:
    for key in ("location", "address", "geo"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
        if isinstance(value, dict):
            nested = first_text(value, ("formattedAddress", "address", "name", "title"))
            if nested:
                return nested
    return None


def extract_image_url(data: dict, base_url: str) -> str | None:
    for key in ("image", "imageUrl", "src", "url"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http", "/")):
            return urljoin(base_url, value)
        if isinstance(value, dict):
            nested = extract_image_url(value, base_url)
            if nested:
                return nested

    images = data.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, str) and image.startswith(("http", "/")):
                return urljoin(base_url, image)
            if isinstance(image, dict):
                nested = extract_image_url(image, base_url)
                if nested:
                    return nested
    return None


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
