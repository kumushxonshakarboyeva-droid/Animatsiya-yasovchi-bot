import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

# Logging sozlamasi (xatoliklarni Render logs-da ko'rish uchun)
logging.basicConfig(level=logging.INFO)

# sticker_renderer.py faylidan routerni import qilish
try:
    from sticker_renderer import router as sticker_router
except ImportError as e:
    logging.error(f"sticker_renderer import qilishda xatolik: {e}")
    sticker_router = None

# Render serveri uchun soxta Web handler (portni ushlab turish uchun)
async def handle_ping(request):
    return web.Response(text="Bot is running active and live!")

async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN topilmadi!")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Stiker routerni ulash
    if sticker_router:
        dp.include_router(sticker_router)
        logging.info("Stiker router muvaffaqiyatli ulandi.")
    else:
        logging.error("Stiker router topilmadi!")

    # Render port sozlamasi
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server {port}-portda ishga tushdi.")

    # Webhook-ni tozalash
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Pollingni boshlash
    logging.info("Bot polling rejimi boshlandi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
