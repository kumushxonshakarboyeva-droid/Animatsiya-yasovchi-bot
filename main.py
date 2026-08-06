import asyncio
import os
import logging
import tempfile
import subprocess
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, InputSticker, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# --- FSM (Holatlar zanjiri) ---
class StickerPackSG(StatesGroup):
    waiting_for_content = State()
    waiting_for_title = State()
    waiting_for_emoji = State()

router = Router()

# --- ANIMATSIYA YARATISH FUNKSIYASI (512x512 WEBM Video Sticker) ---
def generate_animation_file(content_type: str, text_or_path: str, output_webm: str):
    """ Matn yoki rasmdan 512x512 o'lchamli animatsiyali stiker faylini yaratadi """
    size = (512, 512)
    frames = []

    # 15 kadrli harakatli animatsiya kadri tayyorlash
    for i in range(15):
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Kadrlar bo'yicha masshtab/pulsatsiya effekti
        scale = 1 + 0.04 * (i if i < 8 else 15 - i)
        
        if content_type == "text":
            font_size = int(40 * scale)
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()

            text = text_or_path
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x, y = (512 - w) / 2, (512 - h) / 2
            
            # Soya va matn
            draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 200))
            draw.text((x, y), text, font=font, fill=(255, 215, 0, 255))
        
        elif content_type == "photo" and os.path.exists(text_or_path):
            user_img = Image.open(text_or_path).convert("RGBA")
            new_w = int(400 * scale)
            new_h = int(400 * scale)
            user_img = user_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            x, y = (512 - new_w) // 2, (512 - new_h) // 2
            img.paste(user_img, (x, y), user_img)

        frames.append(img)

    # Vaqtincha GIF fayl saqlash
    temp_gif = output_webm.replace(".webm", ".gif")
    frames[0].save(
        temp_gif,
        save_all=True,
        append_images=frames[1:],
        duration=60,
        loop=0,
        disposal=2
    )

    # Telegram talab qiladigan WEBM (VP9) formatiga o'tkazish
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", temp_gif,
            "-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
            "-vf", "scale=512:512", "-an", output_webm
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # ffmpeg bo'lmagan holatda GIF faylni qaytarish
        os.rename(temp_gif, output_webm)
        return

    if os.path.exists(temp_gif):
        os.remove(temp_gif)

# --- BOT HANDLERLARI ---
@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(StickerPackSG.waiting_for_content)
    await message.answer("Salom! Animatsion stiker yaratish botiga xush kelibsiz.\n\nStiker yaratish uchun **matn yoki rasm/GIF** yuboring:")

@router.message(StickerPackSG.waiting_for_content)
async def process_content(message: Message, state: FSMContext, bot: Bot):
    if message.text:
        await state.update_data(content_type="text", content=message.text)
    elif message.photo:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        
        temp_dir = tempfile.gettempdir()
        photo_path = os.path.join(temp_dir, f"input_{message.from_user.id}.png")
        await bot.download_file(file_info.file_path, photo_path)
        
        await state.update_data(content_type="photo", content=photo_path)
    else:
        await message.answer("Iltimos, faqat matn yoki rasm yuboring.")
        return

    await state.set_state(StickerPackSG.waiting_for_title)
    await message.answer("Ajoyib! Endi **Yangi Stiker Paketi nomini** kiriting:")

@router.message(StickerPackSG.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Iltimos, paket uchun nom yuboring:")
        return

    await state.update_data(pack_title=title)
    await state.set_state(StickerPackSG.waiting_for_emoji)
    await message.answer("Ushbu stikerga biriktirish uchun **Emoji yuboring** (masalan: 🔥, 😎, 🚀):")

@router.message(StickerPackSG.waiting_for_emoji)
async def process_emoji(message: Message, state: FSMContext, bot: Bot):
    emoji = message.text.strip() if message.text else "✨"
    data = await state.get_data()
    
    await message.answer("📦 Animatsiyali stiker ishlanmoqda va Telegram serveriga yuklanmoqda...")

    bot_info = await bot.get_me()
    short_name = f"anim_{message.from_user.id}_{int(asyncio.get_event_loop().time())}_by_{bot_info.username}"
    
    temp_dir = tempfile.gettempdir()
    output_sticker_path = os.path.join(temp_dir, f"sticker_{message.from_user.id}.webm")

    try:
        # Animatsiya render qilish
        await asyncio.to_thread(
            generate_animation_file,
            data.get("content_type"),
            data.get("content"),
            output_sticker_path
        )

        sticker_format = "video" if output_sticker_path.endswith(".webm") else "static"

        # Stiker paket yaratish
        await bot.create_new_sticker_set(
            user_id=message.from_user.id,
            name=short_name,
            title=data.get("pack_title", "Animatsion Stikerlar"),
            stickers=[
                InputSticker(
                    sticker=FSInputFile(output_sticker_path),
                    format=sticker_format,
                    emoji_list=[emoji]
                )
            ]
        )
        
        sticker_set_link = f"https://t.me/addstickers/{short_name}"
        await message.answer(f"🎉 **Animatsion stiker paketingiz yaratildi!**\n\nQuyidagi havola orqali qoʻshib oling:\n{sticker_set_link}")

    except Exception as e:
        logging.error(f"Stiker yaratishda xatolik: {e}")
        await message.answer(f"⚠️ Stiker yaratishda xatolik yuz berdi:\n`{e}`")

    finally:
        # Vaqtincha fayllarni tozalash
        if os.path.exists(output_sticker_path):
            os.remove(output_sticker_path)
        if data.get("content_type") == "photo" and os.path.exists(data.get("content")):
            os.remove(data.get("content"))
        await state.clear()

# --- Render Port tinglash serveri ---
async def handle_ping(request):
    return web.Response(text="Sticker Bot Active & Live!")

async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN topilmadi!")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
