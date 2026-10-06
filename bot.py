import os
import sys
import re
import html
import asyncio
import logging
from dotenv import load_dotenv

# Windows konsolida UTF-8 emoji xatolarini oldini olish
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from downloader import async_download_youtube_video

# .env yuklash
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "yuklaydi1408_bot")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! .env faylini tekshiring.")

# Logging sozlash
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Bot va Dispetcher - Katta fayllar uchun timeoutni 300 soniyaga (5 daqiqa) oshiramiz
session = AiohttpSession(timeout=300.0)
bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# YouTube URL regex
YOUTUBE_REGEX = re.compile(
    r'(https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)[a-zA-Z0-9_-]+[^\s]*)'
)


async def start_web_server():
    """Render kabi bepul hostinglar uchun kichik health-check veb-server."""
    from aiohttp import web
    port = int(os.getenv("PORT", 0))
    if port > 0:
        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Health-check server {port}-portda ishga tushdi.")


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_name = html.escape(message.from_user.first_name)
    text = (
        f"👋 Assalomu alaykum, <b>{user_name}</b>!\n\n"
        f"Men YouTube va YouTube Shorts videolarini yuklab beruvchi botman. 🎬\n\n"
        f"Menga YouTube havolasini yuboring (masalan: <code>https://youtu.be/...</code> yoki Shorts havolasi), "
        f"men uni sizga video ko'rinishida yuboraman! 🚀"
    )
    await message.answer(text)


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "ℹ️ <b>Botdan qanday foydalanish kerak?</b>\n\n"
        "1. YouTube'dan istalgan video yoki Shorts havolasini nusxalang.\n"
        "2. Ushbu botga yuboring.\n"
        "3. Bir necha soniya kuting va videoni qabul qilib oling! ✅\n\n"
        "<i>Eslatma: Telegram botlarida video yuborish limiti 50 MB ni tashkil etadi.</i>"
    )
    await message.answer(text)


@dp.message(F.text)
async def handle_text(message: types.Message):
    match = YOUTUBE_REGEX.search(message.text)
    if not match:
        await message.answer("⚠️ Iltimos, to'g'ri YouTube yoki Shorts havolasini yuboring!")
        return

    url = match.group(0)
    status_msg = await message.answer("🔍 Video ma'lumotlari tekshirilmoqda...")

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)
        await status_msg.edit_text("⏳ Video yuklab olinmoqda, iltimos kuting...")

        file_path, video_data, error = await async_download_youtube_video(url)

        if error:
            await status_msg.edit_text(f"❌ {error}")
            return

        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Videoni yuklab olishda xatolik yuz berdi.")
            return

        await status_msg.edit_text("📤 Video Telegramga yuborilmoqda...")

        caption = (
            f"🎬 <b>{html.escape(video_data['title'])}</b>\n\n"
            f"👤 <b>Kanal:</b> {html.escape(video_data['uploader'])}\n"
            f"⏱ <b>Davomiyligi:</b> {video_data['duration_str']}\n\n"
            f"🤖 @{BOT_USERNAME} orqali yuklandi"
        )

        video_file = FSInputFile(file_path)
        await message.answer_video(
            video=video_file,
            caption=caption,
            duration=video_data.get('duration') or 0,
            width=video_data.get('width'),
            height=video_data.get('height'),
            supports_streaming=True,
            request_timeout=300
        )

        # Xabarni o'chirish
        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Xatolik: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)[:150]}")

    finally:
        # Faylni diskdan o'chirib tozalash
        if 'file_path' in locals() and file_path:
            await asyncio.sleep(1)
            for _ in range(3):
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    break
                except Exception:
                    await asyncio.sleep(1)


async def main():
    print("Bot ishga tushmoqda...")
    await start_web_server()
    # Eski yangilanishlarni tashlab yuborish
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi.")
