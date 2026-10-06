import asyncio
import hashlib
import html
import imaplib
import logging
import re
from dataclasses import dataclass
from email import policy
from email.message import Message
from email.parser import BytesParser
from urllib.parse import parse_qs, unquote, urlsplit

from skrapper.config import EmailAlertConfig
from skrapper.models import Listing
from skrapper.sources.avito import clean_text, parse_price, parse_rooms

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>'\"\\)]+", re.IGNORECASE)
SUPPORTED_DOMAINS = (
    "avito.ru",
    "cian.ru",
    "domclick.ru",
    "realty.yandex.ru",
    "youla.ru",
    "n1.ru",
    "gdeetotdom.ru",
    "akula.com",
    "saratov-nedvizhimost.ru",
)
REDIRECT_KEYS = ("url", "u", "to", "target", "redirect", "redirect_url", "retpath")


@dataclass(frozen=True, slots=True)
class EmailImapSettings:
    host: str | None
    port: int
    username: str | None
    password: str | None
    use_ssl: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)


class EmailAlertSource:
    def __init__(self, settings: EmailImapSettings, config: EmailAlertConfig) -> None:
        self.settings = settings
        self.config = config

    async def fetch(self) -> list[Listing]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[Listing]:
        if not self.config.enabled:
            return []
        if not self.settings.is_configured:
            logger.warning("Email alerts are enabled but IMAP credentials are not configured")
            return []

        client = self._connect()
        try:
            client.login(self.settings.username, self.settings.password)
            client.select(self.config.mailbox, readonly=True)
            status, data = client.search(None, "ALL")
            if status != "OK" or not data:
                logger.warning("IMAP search failed: status=%s", status)
                return []

            message_ids = data[0].split()[-self.config.limit :]
            listings: dict[str, Listing] = {}
            for message_id in message_ids:
                for listing in self._fetch_message_listings(client, message_id):
                    listings.setdefault(listing.stable_key, listing)
            return list(listings.values())
        finally:
            try:
                client.close()
            except imaplib.IMAP4.error:
                pass
            client.logout()

    def _connect(self):
        if self.settings.use_ssl:
            return imaplib.IMAP4_SSL(self.settings.host, self.settings.port)
        return imaplib.IMAP4(self.settings.host, self.settings.port)

    def _fetch_message_listings(self, client, message_id: bytes) -> list[Listing]:
        status, data = client.fetch(message_id, "(BODY.PEEK[])")
        if status != "OK":
            logger.warning("IMAP fetch failed: message_id=%s status=%s", message_id, status)
            return []

        raw_message = next((part[1] for part in data if isinstance(part, tuple)), None)
        if not raw_message:
            return []

        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        subject = clean_text(str(message.get("subject", ""))) or "Новое объявление"
        body = extract_message_text(message)
        urls = extract_supported_urls(body)

        listings = []
        for url in urls:
            text = f"{subject} {body[:1500]}"
            listings.append(
                Listing(
                    external_id=hash_url(url),
                    source="email_alert",
                    title=subject,
                    url=url,
                    price=parse_price(text),
                    rooms=parse_rooms(text),
                    description=clean_text(body[:800]) or None,
                )
            )
        return listings


def extract_message_text(message: Message) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            parts.append(part_text(part))
    else:
        parts.append(part_text(message))
    return "\n".join(part for part in parts if part)


def part_text(part: Message) -> str:
    try:
        content = part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True)
        if not payload:
            return ""
        content = payload.decode(part.get_content_charset() or "utf-8", "replace")

    if part.get_content_type() == "text/html":
        content = html.unescape(re.sub(r"<[^>]+>", " ", str(content)))
    return clean_text(str(content))


def extract_supported_urls(text: str) -> list[str]:
    urls: dict[str, None] = {}
    for raw_url in URL_RE.findall(text):
        url = normalize_email_url(raw_url)
        if is_supported_listing_url(url):
            urls[url] = None
    return list(urls)


def normalize_email_url(raw_url: str) -> str:
    url = html.unescape(raw_url).rstrip(".,;:!?)\"]}")
    for _ in range(3):
        decoded = unquote(url)
        if decoded == url:
            break
        url = decoded

    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    for key in REDIRECT_KEYS:
        values = query.get(key)
        if values and values[0].startswith("http"):
            return normalize_email_url(values[0])
    return url


def is_supported_listing_url(url: str) -> bool:
    host = urlsplit(url).netloc.casefold()
    path = urlsplit(url).path.casefold()
    if not any(domain in host for domain in SUPPORTED_DOMAINS):
        return False
    return any(
        marker in path
        for marker in (
            "kvart",
            "flat",
            "offer",
            "card",
            "object",
            "nedvijimost",
            "realty",
            "prodaja",
            "kupit",
        )
    )


def hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
