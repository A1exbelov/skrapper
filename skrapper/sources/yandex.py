from skrapper.sources.generic_html import GenericHtmlSource


class YandexRealtySource(GenericHtmlSource):
    source_name = "yandex"
    url_markers = (
        "/offer/",
        "realty.yandex.ru/offer/",
    )
    card_selectors = (
        '[data-test="offer-card"]',
        '[data-test*="serp-item"]',
        'article',
        'li',
    )
    title_selectors = (
        'a[href*="/offer/"]',
        "a[href]",
        "h3",
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
        '[data-test*="description"]',
        '[class*="description"]',
    )
