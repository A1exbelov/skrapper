from email.message import EmailMessage

from skrapper.sources.email_alerts import extract_message_text, extract_supported_urls


def test_extract_supported_urls_unwraps_redirect_url() -> None:
    text = (
        "Новое объявление: "
        "https://mail.example/redirect?url=https%3A%2F%2Fwww.avito.ru%2Fsaratov%2Fkvartiry%2F"
        "1-k._kvartira_123456789"
    )

    assert extract_supported_urls(text) == [
        "https://www.avito.ru/saratov/kvartiry/1-k._kvartira_123456789"
    ]


def test_extract_message_text_reads_html_body() -> None:
    message = EmailMessage()
    message["Subject"] = "Новое объявление"
    message.set_content("plain fallback")
    message.add_alternative(
        '<html><body><a href="https://saratov.cian.ru/sale/flat/123/">Квартира</a></body></html>',
        subtype="html",
    )

    text = extract_message_text(message)

    assert "plain fallback" in text
    assert "Квартира" in text
