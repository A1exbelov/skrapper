from skrapper.sources.generic_html import GenericHtmlSource


class GdeEtotDomSource(GenericHtmlSource):
    source_name = "gdeetotdom"
    url_markers = (
        "/object/",
        "/realty/",
        "gdeetotdom.ru/object/",
    )
    card_selectors = (
        '[class*="catalog"] [class*="item"]',
        '[class*="object"]',
        'article',
        'li',
    )
    title_selectors = (
        'a[href*="/object/"]',
        'a[href*="/realty/"]',
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
