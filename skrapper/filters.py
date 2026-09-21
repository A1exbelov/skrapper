from skrapper.config import ListingFilters
from skrapper.models import Listing


def matches_filters(listing: Listing, filters: ListingFilters) -> bool:
    if filters.min_price is not None and listing.price is not None:
        if listing.price < filters.min_price:
            return False

    if filters.max_price is not None and listing.price is not None:
        if listing.price > filters.max_price:
            return False

    if filters.rooms and listing.rooms is not None and listing.rooms not in filters.rooms:
        return False

    text = listing.text_for_filtering

    include_keywords = [word.casefold() for word in filters.include_keywords if word.strip()]
    if include_keywords and not any(word in text for word in include_keywords):
        return False

    exclude_keywords = [word.casefold() for word in filters.exclude_keywords if word.strip()]
    if exclude_keywords and any(word in text for word in exclude_keywords):
        return False

    return True

