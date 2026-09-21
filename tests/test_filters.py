from skrapper.config import ListingFilters
from skrapper.filters import matches_filters
from skrapper.models import Listing


def test_listing_matches_price_rooms_and_keywords() -> None:
    listing = Listing(
        external_id="1",
        source="avito",
        title="1-к квартира рядом с метро",
        url="https://example.com/1",
        price=80000,
        rooms=1,
    )

    filters = ListingFilters(
        min_price=50000,
        max_price=100000,
        rooms=[1],
        include_keywords=["метро"],
        exclude_keywords=["апартаменты"],
    )

    assert matches_filters(listing, filters)


def test_listing_rejects_excluded_keyword() -> None:
    listing = Listing(
        external_id="1",
        source="avito",
        title="1-к апартаменты рядом с метро",
        url="https://example.com/1",
        price=80000,
        rooms=1,
    )

    filters = ListingFilters(exclude_keywords=["апартаменты"])

    assert not matches_filters(listing, filters)

