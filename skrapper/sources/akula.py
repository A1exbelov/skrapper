from skrapper.sources.generic_html import GenericHtmlSource


class AkulaSource(GenericHtmlSource):
    source_name = "akula"
    url_markers = (
        "/prodaja/kvartira/",
        "saratov.akula.com/prodaja/kvartira/",
    )
    card_selectors = (
        '[class*="object"]',
        '[class*="card"]',
        'article',
        'li',
    )
    title_selectors = (
        'a[href*="/prodaja/kvartira/"]',
        "a[href]",
    )
    price_selectors = (
        '[class*="price"]',
    )
    location_selectors = (
        '[class*="address"]',
        '[class*="location"]',
    )
    description_selectors = (
        '[class*="description"]',
        '[class*="text"]',
    )
