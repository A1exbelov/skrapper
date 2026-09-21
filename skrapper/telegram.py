from html import escape

from aiogram import Bot

from skrapper.models import Listing


def format_listing_message(listing: Listing) -> str:
    lines = [
        f"<b>{escape(listing.title)}</b>",
        f"Источник: {escape(listing.source)}",
    ]

    if listing.price is not None:
        lines.append(f"Цена: {listing.price:,} ₽".replace(",", " "))
    if listing.rooms is not None:
        lines.append(f"Комнат: {listing.rooms}")
    if listing.location:
        lines.append(f"Локация: {escape(listing.location)}")

    lines.append("")
    lines.append(f'<a href="{escape(listing.url)}">Открыть объявление</a>')
    return "\n".join(lines)


async def send_listing(bot: Bot, chat_id: str, listing: Listing) -> None:
    text = format_listing_message(listing)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=False)

