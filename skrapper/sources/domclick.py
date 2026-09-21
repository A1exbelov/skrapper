from skrapper.sources.generic_html import GenericHtmlSource


class DomclickSource(GenericHtmlSource):
    source_name = "domclick"
    card_selectors = (
        '[data-testid*="offer"]',
        '[class*="card"]',
        'article',
    )
    title_selectors = (
        'a[href*="/card/"]',
        'a[href*="/offers/"]',
        'a[href*="/sale/"]',
        "a[href]",
    )
    price_selectors = (
        '[data-testid*="price"]',
        '[class*="price"]',
    )
    location_selectors = (
        '[data-testid*="address"]',
        '[class*="address"]',
    )
    description_selectors = (
        '[data-testid*="description"]',
        '[class*="description"]',
    )
