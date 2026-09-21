from abc import ABC, abstractmethod

from skrapper.models import Listing


class ListingSource(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> list[Listing]:
        raise NotImplementedError

