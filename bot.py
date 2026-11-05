import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import settings
from database.database import init_db, engine
from middlewares.database import DatabaseMiddleware

# Handlers
from handlers.start import router as start_router
from handlers.registration import router as registration_router
from handlers.profile import router as profile_router
from handlers.applications import router as applications_router
from handlers.my_applications import router as my_applications_router
from handlers.tracking import router as tracking_router
from handlers.correspondence import router as correspondence_router
from handlers.admin import router as admin_main_router
from handlers.admin_applications import router as admin_applications_router
from handlers.admin_staff import router as admin_staff_router
from handlers.admin_statistics import router as admin_statistics_router
from handlers.admin_settings import router as admin_settings_router


def setup_logging():
    """Configures structured logging to console and rotating log file."""
    os.makedirs("logs", exist_ok=True)
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handlers = [
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            "logs/bot.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
    ]

    logging.basicConfig(level=level, format=log_format, handlers=handlers)


async def setup_bot_commands(bot: Bot):
    """Sets standard bot commands visible in Telegram menu."""
    commands = [
        BotCommand(command="start", description="Bosh menyu / Botni ishga tushirish"),
        BotCommand(command="admin", description="Boshqaruv paneli (mas'ullar uchun)")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main():
    setup_logging()
    logger = logging.getLogger("e_murojaat")
    logger.info("Starting E-MUROJAAT Telegram Bot for Gumanitar fanlar va jismoniy madaniyat fakulteti...")

    if not settings.BOT_TOKEN or settings.BOT_TOKEN.startswith("7777777777"):
        logger.warning(
            "DIQQAT: .env faylida BOT_TOKEN haqiqiy token bilan to‘ldirilmagan! "
            "Botni haqiqiy Telegramda ishga tushirishdan oldin BOT_TOKEN ga o‘z tokeningizni yozing."
        )

    # Initialize Database
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Fatal error during database init: {e}", exc_info=True)
        sys.exit(1)

    # Initialize Storage (Redis with fallback to MemoryStorage)
    storage = None
    if settings.REDIS_URL:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            storage = RedisStorage.from_url(settings.REDIS_URL)
            logger.info("Connected to Redis for FSM storage.")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis ({e}), falling back to MemoryStorage.")
            storage = MemoryStorage()
    else:
        logger.info("Using in-memory FSM storage (MemoryStorage).")
        storage = MemoryStorage()

    # Bot & Dispatcher setup
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    # Register Middlewares
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # Include Routers in specific sequence
    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(profile_router)
    dp.include_router(applications_router)
    dp.include_router(my_applications_router)
    dp.include_router(tracking_router)
    dp.include_router(correspondence_router)
    dp.include_router(admin_main_router)
    dp.include_router(admin_applications_router)
    dp.include_router(admin_staff_router)
    dp.include_router(admin_statistics_router)
    dp.include_router(admin_settings_router)

    # Bot commands
    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning(f"Could not setup bot commands: {e}")

    # Start Keep-Alive Web Server for UptimeRobot
    web_runner = None
    self_ping_task = None
    if settings.ENABLE_WEB_SERVER:
        try:
            from services.web_server import start_web_server, run_self_ping
            port = int(os.environ.get("PORT", settings.WEB_PORT))
            host = os.environ.get("HOST", settings.WEB_HOST)
            web_runner = await start_web_server(host=host, port=port)
            logger.info(f"Health-check web server for UptimeRobot started on http://{host}:{port}")

            if settings.SELF_PING_URL:
                self_ping_task = asyncio.create_task(
                    run_self_ping(settings.SELF_PING_URL, settings.SELF_PING_INTERVAL_MINUTES)
                )
                logger.info(f"Self-ping background task started for {settings.SELF_PING_URL}")
        except Exception as e:
            logger.warning(f"Could not start UptimeRobot web server: {e}")

    logger.info("Bot is ready and listening for updates...")

    try:
        # Delete webhook and drop pending updates before starting polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down bot...")
        if self_ping_task and not self_ping_task.done():
            self_ping_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        await engine.dispose()
        logger.info("Shutdown completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user.")

