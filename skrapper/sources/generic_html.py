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
    url_markers: tuple[str, ...] = ()
    card_selectors: tuple[str, ...] = ()
    title_selectors: tuple[str, ...] = ("a", "h2", "h3")
    price_selectors: tuple[str, ...] = ()
    location_selectors: tuple[str, ...] = ()
    description_selectors: tuple[str, ...] = ()
    required_url_pattern: str | None = None

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, url: str) -> list[Listing]:
        response = await self.client.get(url)
        if response.status_code in {401, 403}:
            logger.warning(
                "%s requires authorization or blocked request: status=%s url=%s",
                self.source_name,
                response.status_code,
                url,
            )
            return []
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            logger.warning(
                "%s rate limit hit: 429 Too Many Requests. retry_after=%s url=%s",
                self.source_name,
                retry_after or "unknown",
                url,
            )
            return []
        if response.status_code == 503:
            logger.warning("%s blocked or unavailable: status=%s url=%s", self.source_name, response.status_code, url)
            return []

        response.raise_for_status()

        parser = HTMLParser(response.text)
        title = parser.css_first("title")
        page_title = clean_text(title.text()) if title else ""
        if is_antibot_page(page_title, str(response.url), response.text):
            logger.warning(
                "%s returned an anti-bot page. title=%r url=%s",
                self.source_name,
                page_title,
                response.url,
            )
            return []

        listings = self._parse_cards(parser, url)
        if listings:
            return filter_by_required_url_pattern(listings, self.required_url_pattern)

        json_ld_listings = parse_json_ld_listings(response.text, url, self.source_name)
        if json_ld_listings:
            logger.info("Parsed %d %s listings from JSON-LD", len(json_ld_listings), self.source_name)
            return filter_by_required_url_pattern(json_ld_listings, self.required_url_pattern)

        embedded_json_listings = parse_embedded_json_listings(
            response.text,
            url,
            self.source_name,
            self.url_markers,
            self.required_url_pattern,
        )
        if embedded_json_listings:
            logger.info(
                "Parsed %d %s listings from embedded JSON",
                len(embedded_json_listings),
                self.source_name,
            )
            return filter_by_required_url_pattern(embedded_json_listings, self.required_url_pattern)

        logger.warning(
            "%s returned no listing cards. title=%r",
            self.source_name,
            page_title,
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

        absolute_url = urljoin(base_url, href)
        if not is_listing_href(absolute_url, self.url_markers):
            return None
        if self.required_url_pattern and not re.search(self.required_url_pattern, absolute_url):
            return None

        title = clean_text(link.text())
        if not title:
            return None

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


def is_listing_href(url: str, url_markers: tuple[str, ...]) -> bool:
    if not url_markers:
        return True
    return any(marker in url for marker in url_markers)


def filter_by_required_url_pattern(
    listings: list[Listing],
    required_url_pattern: str | None,
) -> list[Listing]:
    if not required_url_pattern:
        return listings
    return [listing for listing in listings if re.search(required_url_pattern, listing.url)]


def is_antibot_page(title: str, url: str, html: str) -> bool:
    title_lower = title.casefold()
    url_lower = url.casefold()
    if "captcha" in url_lower or "showcaptcha" in url_lower:
        return True
    if "вы не робот" in title_lower or "not a robot" in title_lower:
        return True
    preview = html[:5000].casefold()
    return "showcaptcha" in preview or "captcha" in preview and "robot" in preview


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


def parse_embedded_json_listings(
    html: str,
    base_url: str,
    source_name: str,
    url_markers: tuple[str, ...],
    required_url_pattern: str | None = None,
) -> list[Listing]:
    if not url_markers:
        return []

    parser = HTMLParser(html)
    listings: dict[str, Listing] = {}
    for script in parser.css("script"):
        raw = script.text()
        if not raw or not any(marker in raw for marker in url_markers):
            continue
        for data in possible_json_values(raw):
            for node in walk_json(data):
                if not isinstance(node, dict):
                    continue
                listing = listing_from_embedded_json(
                    node,
                    base_url,
                    source_name,
                    url_markers,
                    required_url_pattern,
                )
                if listing is not None:
                    listings.setdefault(listing.stable_key, listing)
    return list(listings.values())


def possible_json_values(raw: str) -> list[object]:
    candidates = [raw.strip()]
    assignment_match = re.search(r"=\s*({.*})\s*;?\s*$", raw.strip(), re.DOTALL)
    if assignment_match:
        candidates.append(assignment_match.group(1))

    values = []
    for candidate in candidates:
        if not candidate.startswith(("{", "[")):
            continue
        try:
            values.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    return values


def listing_from_embedded_json(
    data: dict,
    base_url: str,
    source_name: str,
    url_markers: tuple[str, ...],
    required_url_pattern: str | None = None,
) -> Listing | None:
    raw_url = first_text(data, ("url", "href", "uri", "link", "canonicalUrl", "fullUrl"))
    title = first_text(data, ("title", "name", "header", "displayTitle", "seoTitle"))
    if not raw_url or not title:
        return None
    if not any(marker in raw_url for marker in url_markers):
        return None

    absolute_url = urljoin(base_url, raw_url)
    if required_url_pattern and not re.search(required_url_pattern, absolute_url):
        return None

    price = first_price(data)
    description = first_text(data, ("description", "text", "subtitle", "snippet"))

    return Listing(
        external_id=extract_external_id(absolute_url),
        source=source_name,
        title=clean_text(title),
        url=absolute_url,
        price=price,
        rooms=parse_rooms(" ".join(part for part in [title, description or ""] if part)),
        location=first_location(data),
        description=description,
        image_url=first_image(data, base_url),
    )


def first_text(data: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
        if isinstance(value, (int, float)):
            return str(value)
    return None


def first_price(data: dict) -> int | None:
    for key in ("price", "priceValue", "cost", "amount"):
        value = data.get(key)
        if isinstance(value, dict):
            nested = first_price(value)
            if nested is not None:
                return nested
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            parsed = parse_price(value)
            if parsed is not None:
                return parsed
    return None


def first_location(data: dict) -> str | None:
    for key in ("location", "address", "geo", "undergrounds"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
        if isinstance(value, dict):
            text = first_text(value, ("title", "name", "address", "fullName"))
            if text:
                return text
        if isinstance(value, list):
            names = []
            for item in value[:3]:
                if isinstance(item, dict):
                    text = first_text(item, ("title", "name"))
                    if text:
                        names.append(text)
            if names:
                return ", ".join(names)
    return None


def first_image(data: dict, base_url: str) -> str | None:
    for key in ("image", "imageUrl", "photo", "photos", "images"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http", "/")):
            return urljoin(base_url, value)
        if isinstance(value, dict):
            text = first_text(value, ("url", "src", "fullUrl"))
            if text and text.startswith(("http", "/")):
                return urljoin(base_url, text)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.startswith(("http", "/")):
                    return urljoin(base_url, item)
                if isinstance(item, dict):
                    text = first_text(item, ("url", "src", "fullUrl"))
                    if text and text.startswith(("http", "/")):
                        return urljoin(base_url, text)
    return None


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
