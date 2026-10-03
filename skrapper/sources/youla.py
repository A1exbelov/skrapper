from skrapper.sources.generic_html import GenericHtmlSource


class YoulaSource(GenericHtmlSource):
    source_name = "youla"
    url_markers = (
        "/saratov/nedvijimost/prodaja-kvartiri/",
        "youla.ru/saratov/nedvijimost/prodaja-kvartiri/",
    )
    card_selectors = (
        '[data-test-component*="Product"]',
        '[data-test*="product"]',
        'article',
        'li',
    )
    title_selectors = (
        'a[href*="/nedvijimost/prodaja-kvartiri/"]',
        "a[href]",
    )
    price_selectors = (
        '[data-test*="price"]',
        '[class*="price"]',
    )
    location_selectors = (
        '[data-test*="location"]',
        '[class*="location"]',
    )
    description_selectors = (
        '[data-test*="description"]',
        '[class*="description"]',
    )
