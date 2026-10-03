import logging
from dataclasses import dataclass

import httpx
from aiogram import Bot

from skrapper.config import AppConfig, SearchConfig
from skrapper.filters import matches_filters
from skrapper.sources import AvitoSource, CianSource, DomclickSource, RssSource
from skrapper.sources.base import ListingSource
from skrapper.storage import ListingStorage
from skrapper.telegram import send_listing

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SearchRunResult:
    name: str
    source: str
    fetched: int = 0
    sent: int = 0
    new: int = 0
    bootstrapped: bool = False
    skipped_initial_sync: bool = False
    error: str | None = None


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

    async def run_once(self) -> list[SearchRunResult]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        results: list[SearchRunResult] = []
        async with httpx.AsyncClient(
            timeout=self.http_timeout_seconds,
            headers=headers,
            follow_redirects=True,
        ) as client:
            for search in self.config.searches:
                if not search.enabled:
                    continue
                results.append(await self._process_search(search, client))
        return results

    async def _process_search(self, search: SearchConfig, client: httpx.AsyncClient) -> SearchRunResult:
        source = build_source(search, client)
        state = self.storage.get_search_state(search.name)

        try:
            listings = await source.fetch(str(search.url))
        except httpx.HTTPError as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.warning("Search failed: search=%s url=%s", search.name, search.url, exc_info=True)
            self.storage.update_search_state(search.name, error=error)
            return SearchRunResult(name=search.name, source=search.source, error=error)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.exception("Unexpected search failure: search=%s url=%s", search.name, search.url)
            self.storage.update_search_state(search.name, error=error)
            return SearchRunResult(name=search.name, source=search.source, error=error)

        if not state.bootstrapped and not listings:
            self.storage.update_search_state(
                search.name,
                bootstrapped=False,
                fetched_count=0,
                sent_count=0,
                success=True,
            )
            logger.warning(
                "Initial sync postponed because search returned no listings: search=%s",
                search.name,
            )
            return SearchRunResult(
                name=search.name,
                source=search.source,
                fetched=0,
                sent=0,
                new=0,
                bootstrapped=False,
                skipped_initial_sync=True,
            )

        if not state.bootstrapped:
            for listing in listings:
                self.storage.upsert_observed(listing)
            self.storage.update_search_state(
                search.name,
                bootstrapped=True,
                fetched_count=len(listings),
                sent_count=0,
                success=True,
            )
            logger.info(
                "Initial sync completed: search=%s fetched=%d sent=0",
                search.name,
                len(listings),
            )
            return SearchRunResult(
                name=search.name,
                source=search.source,
                fetched=len(listings),
                sent=0,
                new=0,
                bootstrapped=True,
                skipped_initial_sync=True,
            )

        sent_count = 0
        new_count = 0
        for listing in listings:
            is_new = self.storage.upsert_observed(listing)
            if not is_new:
                continue
            new_count += 1

            if sent_count >= self.config.notification.max_items_per_run:
                continue
            if not matches_filters(listing, search.filters):
                continue
            if self.storage.was_notified(listing):
                continue

            if not await send_listing(self.bot, self.chat_id, listing):
                logger.warning(
                    "Stopping notifications for search=%s until Telegram delivery is fixed",
                    search.name,
                )
                break
            self.storage.mark_notified(listing)
            sent_count += 1

        self.storage.update_search_state(
            search.name,
            bootstrapped=True,
            fetched_count=len(listings),
            sent_count=sent_count,
            success=True,
        )
        logger.info(
            "Processed search=%s fetched=%d new=%d sent=%d",
            search.name,
            len(listings),
            new_count,
            sent_count,
        )
        return SearchRunResult(
            name=search.name,
            source=search.source,
            fetched=len(listings),
            sent=sent_count,
            new=new_count,
            bootstrapped=True,
        )


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
