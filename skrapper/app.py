import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from skrapper.config import load_config
from skrapper.settings import Settings
from skrapper.storage import ListingStorage
from skrapper.worker import ListingWorker


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings()
    config = load_config(settings.config_path)
    storage = ListingStorage(settings.database_path)
    storage.init()

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()

    worker = ListingWorker(
        config=config,
        storage=storage,
        bot=bot,
        chat_id=settings.telegram_chat_id,
        http_timeout_seconds=settings.http_timeout_seconds,
        user_agent=settings.user_agent,
    )

    @dispatcher.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer("Бот запущен. Новые подходящие объявления будут приходить сюда.")

    @dispatcher.message(Command("check"))
    async def check(message: Message) -> None:
        await message.answer("Проверяю объявления...")
        results = await worker.run_once()
        await message.answer(format_run_results(results))

    @dispatcher.message(Command("status"))
    async def status(message: Message) -> None:
        stats = storage.stats()
        states = storage.list_search_states()
        lines = [
            "Статус:",
            f"объявлений в базе: {stats['listings_count']}",
            f"отправлено уведомлений: {stats['notified_count']}",
            f"прогрето поисков: {stats['bootstrapped_count']}",
        ]
        if states:
            lines.append("")
            lines.append("Источники:")
            for state in states:
                status_text = "прогрет" if state.bootstrapped else "ждет прогрева"
                error_text = f", ошибка: {state.last_error}" if state.last_error else ""
                lines.append(
                    f"{state.name}: {status_text}, найдено {state.last_fetched_count}, "
                    f"отправлено {state.last_sent_count}{error_text}"
                )
        await message.answer(
            "\n".join(lines)
        )

    @dispatcher.message(Command("chatid"))
    async def chatid(message: Message) -> None:
        await message.answer(f"chat_id: <code>{message.chat.id}</code>", parse_mode="HTML")

    @dispatcher.message()
    async def fallback(message: Message) -> None:
        await message.answer("Команды: /start, /chatid, /check, /status")

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        worker.run_once,
        "interval",
        seconds=settings.check_interval_seconds,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()

    await worker.run_once()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    polling_task = asyncio.create_task(dispatcher.start_polling(bot))
    stop_task = asyncio.create_task(stop_event.wait())

    done, pending = await asyncio.wait(
        {polling_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
    for task in done:
        task.result()

    scheduler.shutdown(wait=False)
    await bot.session.close()


def format_run_results(results) -> str:
    if not results:
        return "Проверка завершена: активных источников нет."

    lines = ["Проверка завершена:"]
    for result in results:
        if result.error:
            lines.append(f"{result.name}: ошибка ({result.error})")
            continue
        suffix = " первичная синхронизация, без рассылки" if result.skipped_initial_sync else ""
        lines.append(
            f"{result.name}: найдено {result.fetched}, новых {result.new}, отправлено {result.sent}.{suffix}"
        )
    return "\n".join(lines)
