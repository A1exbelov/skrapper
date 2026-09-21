from abc import ABC, abstractmethod

import httpx

from skrapper.models import Listing


class ListingSource(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> list[Listing]:
        raise NotImplementedError


class RateLimitedSourceMixin:
    source_name = "source"

    def handle_rate_limit(self, response: httpx.Response, url: str) -> bool:
        if response.status_code != 429:
            return False
        return True
