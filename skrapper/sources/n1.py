from skrapper.sources.generic_html import GenericHtmlSource


class N1Source(GenericHtmlSource):
    source_name = "n1"
    url_markers = (
        "/view/",
        "/kupit/kvartiry/",
        "saratov-1.n1.ru/view/",
    )
    card_selectors = (
        '[data-test*="offer"]',
        '[class*="living-list-card"]',
        '[class*="card"]',
        'article',
    )
    title_selectors = (
        'a[href*="/view/"]',
        'a[href*="/kupit/kvartiry/"]',
        "a[href]",
    )
    price_selectors = (
        '[data-test*="price"]',
        '[class*="price"]',
    )
    location_selectors = (
        '[data-test*="address"]',
        '[class*="address"]',
        '[class*="location"]',
    )
    description_selectors = (
        '[class*="description"]',
        '[data-test*="description"]',
    )
