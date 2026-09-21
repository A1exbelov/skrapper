from skrapper.sources.generic_html import GenericHtmlSource


class CianSource(GenericHtmlSource):
    source_name = "cian"
    card_selectors = (
        '[data-name="CardComponent"]',
        '[data-testid="offer-card"]',
        'article',
    )
    title_selectors = (
        '[data-name="LinkArea"] a[href]',
        'a[href*="/sale/flat/"]',
        'a[href*="/rent/flat/"]',
        "a[href]",
    )
    price_selectors = (
        '[data-mark="MainPrice"]',
        '[data-testid="price-amount"]',
        '[class*="price"]',
    )
    location_selectors = (
        '[data-name="GeoLabel"]',
        '[data-testid="address"]',
        '[class*="address"]',
    )
    description_selectors = (
        '[data-name="Description"]',
        '[data-testid="description"]',
    )
