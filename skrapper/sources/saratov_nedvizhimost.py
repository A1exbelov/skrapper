from skrapper.sources.generic_html import GenericHtmlSource


class SaratovNedvizhimostSource(GenericHtmlSource):
    source_name = "saratov_nedvizhimost"
    url_markers = (
        "/kvartiry/prodam/",
        "saratov-nedvizhimost.ru/kvartiry/prodam/",
    )
    card_selectors = (
        '[class*="object"]',
        '[class*="item"]',
        '[class*="card"]',
        'article',
        'li',
    )
    title_selectors = (
        'a[href*="/kvartiry/prodam/"]',
        "a[href]",
    )
    price_selectors = (
        '[class*="price"]',
        '[class*="cost"]',
    )
    location_selectors = (
        '[class*="address"]',
        '[class*="location"]',
        '[class*="rayon"]',
    )
    description_selectors = (
        '[class*="description"]',
        '[class*="text"]',
    )
