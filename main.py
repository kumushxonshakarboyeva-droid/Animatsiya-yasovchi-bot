"""
Telegram Sticker & Custom Emoji Bot with Pack Creator
SVG-free version for simple deployment on Render.com
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputSticker,
    Message,
)

from sticker_renderer import (
    COLORS,
    FONTS,
    render_360_spin_sticker,
    render_custom_emoji,
    render_sticker,
)

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("sticker-bot")

router = Router()
HEX_COLOR_RE = re.compile(r"^#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")

# ─────────────────────────────────────────────────────────────────────────────
# User Session Management
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class UserSession:
    item_type: str = "sticker"    # "sticker" (512x512) | "emoji" (100x100)
    method: str = ""              # "logo" | "text" | "ai"
    
    # Text data
    text_content: str = ""
    font: str = "fredoka"
    color: str = "#8A2BE2"
    animation: str = "bounce"
    
    # Output file & Pack info
    temp_file_path: str = ""
    pack_title: str = ""
    pack_name: str = ""
    target_emoji: str = "⭐"
    
    # State control
    waiting_for_logo: bool = False
    waiting_for_text: bool = False
    waiting_for_hex: bool = False
    waiting_for_pack_title: bool = False
    waiting_for_target_emoji: bool = False

sessions: dict[int, UserSession] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Keyboards (Inline Menus)
# ─────────────────────────────────────────────────────────────────────────────
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎨 Stiker (512x512)", callback_data="type:sticker"),
            InlineKeyboardButton(text="🎭 Custom Emoji (100x100)", callback_data="type:emoji")
        ]
    ])

def method_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Logo Animatsiya (360° Spin)", callback_data="method:logo")],
        [InlineKeyboardButton(text="✍️ Text Animatsiya", callback_data="method:text")],
        [InlineKeyboardButton(text="🤖 AI orqali yaratish", callback_data="method:ai")]
    ])

def font_kb() -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=v["label"], callback_data=f"font:{k}") for k, v in FONTS.items()]
    return InlineKeyboardMarkup(inline_keyboard=[btns[i:i+2] for i in range(0, len(btns), 2)])

def color_kb() -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=v["label"], callback_data=f"color:{k}") for k, v in COLORS.items()]
    rows = [btns[i:i+2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton(text="🎨 Custom Hex (#...)", callback_data="color:custom")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ─────────────────────────────────────────────────────────────────────────────
# Command & Start Handlers
# ─────────────────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    sessions[message.from_user.id] = UserSession()
    await message.answer(
        "👋 **Xush kelibsiz!**\n\nStiker yoki Custom Emoji yaratish uchun menyudan birini tanlang:",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data.startswith("type:"))
async def cb_type_select(callback: CallbackQuery) -> None:
    session = sessions.setdefault(callback.from_user.id, UserSession())
    session.item_type = callback.data.split(":")[1]
    await callback.answer()
    await callback.message.edit_text("Yaratish usulini tanlang:", reply_markup=method_menu_kb())

@router.callback_query(F.data.startswith("method:"))
async def cb_method_select(callback: CallbackQuery) -> None:
    session = sessions.get(callback.from_user.id, UserSession())
    method = callback.data.split(":")[1]
    session.method = method
    await callback.answer()

    if method == "logo":
        session.waiting_for_logo = True
        await callback.message.edit_text(
            "📥 **Logo rasmingizni yuboring** (PNG yoki JPEG formatida):\n\n"
            "Bot uni yumaloq shaklda kesib, 360° Spin animatsiyaga aylantiradi."
        )
    elif method == "text":
        session.waiting_for_text = True
        await callback.message.edit_text("✍️ Stiker uchun matn kiriting:")
    elif method == "ai":
        await callback.message.edit_text("🤖 AI uchun tasvir tavsifini (prompt) kiriting:")

# ── 1. LOGO UPLOAD & PROCESSING (360° SPIN) ─────────────────────────────────
@router.message(F.photo | F.document)
async def handle_logo_upload(message: Message) -> None:
    session = sessions.get(message.from_user.id)
    if not session or not session.waiting_for_logo:
        return

    session.waiting_for_logo = False
    status_msg = await message.answer("🔄 Rasm yumaloq qirqilmoqda va 360° Spin animatsiya qilinmoqda...")

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    file_info = await message.bot.get_file(file_id)

    tmp_dir = Path(tempfile.mkdtemp())
    input_path = tmp_dir / "input_logo.png"
    await message.bot.download_file(file_info.file_path, destination=input_path)

    # Yumaloq kesish va 360 Spin yaratish
    out_path = render_360_spin_sticker(input_path, tmp_dir)
    session.temp_file_path = str(out_path)

    await status_msg.delete()
    session.waiting_for_pack_title = True
    await message.answer("✅ **Animatsiya tayyor!**\n\nEndi ushbu stiker uchun **Yangi Stiker Paketi nomini** kiriting:")

# ── 2. TEXT FLOW & CUSTOM HEX COLOR ─────────────────────────────────────────
@router.message(F.text)
async def handle_text_inputs(message: Message) -> None:
    session = sessions.get(message.from_user.id)
    if not session:
        return

    # Matn kiritish
    if session.waiting_for_text:
        session.waiting_for_text = False
        session.text_content = message.text
        await message.answer("Shriftni tanlang:", reply_markup=font_kb())
        return

    # Custom Hex Color
    if session.waiting_for_hex:
        if not HEX_COLOR_RE.fullmatch(message.text):
            await message.answer("⚠️ Format noto'g'ri! Masalan `#FF5733` yoki `FF5733` yuboring:")
            return
        session.waiting_for_hex = False
        session.color = message.text if message.text.startswith("#") else f"#{message.text}"
        
        # Stiker render qilish
        tmp_dir = Path(tempfile.mkdtemp())
        if session.item_type == "emoji":
            out_path = render_custom_emoji(session.text_content, tmp_dir, session.font, session.color, session.animation)
        else:
            out_path = render_sticker(session.text_content, tmp_dir, session.font, session.color, session.animation)
        
        session.temp_file_path = str(out_path)
        session.waiting_for_pack_title = True
        await message.answer("✅ Matnli stiker yaratildi.\n\nEndi yangi **Stiker Paketi nomini** kiriting:")
        return

    # Pack nomini olish
    if session.waiting_for_pack_title:
        session.waiting_for_pack_title = False
        session.pack_title = message.text
        bot_info = await message.bot.get_me()
        session.pack_name = f"pack_{message.from_user.id}_{int(asyncio.get_event_loop().time())}_by_{bot_info.username}"
        
        session.waiting_for_target_emoji = True
        await message.answer("Ushbu stikerga biriktirish uchun **Emoji yuboring** (masalan: 🔥, 😎, 🚀):")
        return

    # Emoji biriktirish va Telegram Pack yaratish
    if session.waiting_for_target_emoji:
        session.waiting_for_target_emoji = False
        session.target_emoji = message.text[0]
        await message.answer("📦 Telegram Stiker Paketi yaratilmoqda...")
        await create_sticker_pack_on_telegram(message, session)

# ── CALLBACK HANDLERS ────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("font:"))
async def cb_font(callback: CallbackQuery) -> None:
    session = sessions.get(callback.from_user.id)
    if session:
        session.font = callback.data.split(":")[1]
        await callback.answer()
        await callback.message.edit_text("Rangni tanlang:", reply_markup=color_kb())

@router.callback_query(F.data.startswith("color:"))
async def cb_color(callback: CallbackQuery) -> None:
    session = sessions.get(callback.from_user.id)
    if not session:
        return
    choice = callback.data.split(":")[1]
    await callback.answer()

    if choice == "custom":
        session.waiting_for_hex = True
        await callback.message.edit_text("🎨 **Hex rang kodini kiriting** (masalan: `#FF5733`):")
    else:
        session.color = COLORS.get(choice, {}).get("fill", choice)
        tmp_dir = Path(tempfile.mkdtemp())
        
        if session.item_type == "emoji":
            out_path = render_custom_emoji(session.text_content, tmp_dir, session.font, session.color, session.animation)
        else:
            out_path = render_sticker(session.text_content, tmp_dir, session.font, session.color, session.animation)
            
        session.temp_file_path = str(out_path)
        session.waiting_for_pack_title = True
        await callback.message.edit_text("Ajoyib! Endi **Yangi Stiker Paketi nomini** kiriting:")

# ── TELEGRAM STICKER PACK CREATION LOGIC ─────────────────────────────────────
async def create_sticker_pack_on_telegram(message: Message, session: UserSession) -> None:
    user_id = message.from_user.id
    try:
        sticker_item = InputSticker(
            sticker=FSInputFile(session.temp_file_path),
            emoji_list=[session.target_emoji]
        )
        
        # Telegram API orqali pack yaratish
        await message.bot.create_new_sticker_set(
            user_id=user_id,
            name=session.pack_name,
            title=session.pack_title,
            stickers=[sticker_item],
            sticker_format="animated" if session.method == "logo" else "static"
        )
        
        pack_url = f"https://t.me/addstickers/{session.pack_name}"
        await message.answer(
            f"🎉 **Stiker paketingiz muvaffaqiyatli yaratildi!**\n\n"
            f"📌 **Nomi:** {session.pack_title}\n"
            f"🔗 **Ulanish havolasi:** {pack_url}"
        )
    except Exception as err:
        logger.exception("Pack creation failed")
        await message.answer(f"❌ Xatolik yuz berdi: `{err}`")

# ─────────────────────────────────────────────────────────────────────────────
from aiohttp import web

# Render porti uchun soxta Web Server funksiyasi
async def handle_ping(request):
    return web.Response(text="Bot is live and running!")

async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN topilmadi!")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Botingizdagi routerni ulash (agar mavjud bo'lsa)
    if 'router' in globals():
        dp.include_router(router)

    # --- Render Port Sozlamasi ---
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server {port}-portda ishga tushdi.")
    # -----------------------------

    # Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
