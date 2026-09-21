import logging

import httpx
from aiogram import Bot

from skrapper.config import AppConfig, SearchConfig
from skrapper.filters import matches_filters
from skrapper.sources import AvitoSource, CianSource, DomclickSource, RssSource
from skrapper.sources.base import ListingSource
from skrapper.storage import ListingStorage
from skrapper.telegram import send_listing

logger = logging.getLogger(__name__)


class ListingWorker:
    def __init__(
        self,
        *,
        config: AppConfig,
        storage: ListingStorage,
        bot: Bot,
        chat_id: str,
        http_timeout_seconds: int,
        user_agent: str,
    ) -> None:
        self.config = config
        self.storage = storage
        self.bot = bot
        self.chat_id = chat_id
        self.http_timeout_seconds = http_timeout_seconds
        self.user_agent = user_agent

    async def run_once(self) -> None:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(
            timeout=self.http_timeout_seconds,
            headers=headers,
            follow_redirects=True,
        ) as client:
            for search in self.config.searches:
                if not search.enabled:
                    continue
                await self._process_search(search, client)

    async def _process_search(self, search: SearchConfig, client: httpx.AsyncClient) -> None:
        source = build_source(search, client)
        try:
            listings = await source.fetch(str(search.url))
        except httpx.HTTPError:
            logger.warning("Search failed: search=%s url=%s", search.name, search.url, exc_info=True)
            return

        sent_count = 0
        for listing in listings:
            if sent_count >= self.config.notification.max_items_per_run:
                break
            if self.storage.is_seen(listing):
                continue
            if not matches_filters(listing, search.filters):
                self.storage.mark_seen(listing)
                continue

            if not await send_listing(self.bot, self.chat_id, listing):
                logger.warning(
                    "Stopping notifications for search=%s until Telegram delivery is fixed",
                    search.name,
                )
                break
            self.storage.mark_seen(listing)
            sent_count += 1

        logger.info("Processed search=%s fetched=%d sent=%d", search.name, len(listings), sent_count)


def build_source(search: SearchConfig, client: httpx.AsyncClient) -> ListingSource:
    if search.source == "avito":
        return AvitoSource(client)
    if search.source == "cian":
        return CianSource(client)
    if search.source == "domclick":
        return DomclickSource(client)
    if search.source == "rss":
        return RssSource(client)
    raise ValueError(f"Unsupported source: {search.source}")
