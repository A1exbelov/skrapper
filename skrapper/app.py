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
        await worker.run_once()
        await message.answer("Проверка завершена.")

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(worker.run_once, "interval", seconds=settings.check_interval_seconds)
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

