import os
import uuid
import asyncio
from typing import Optional, Tuple, Dict, Any
import yt_dlp

# Ffmpeg yo'lini aniqlash
FFMPEG_PATH = None
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    pass


def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_video_info(url: str) -> Dict[str, Any]:
    """Video haqidagi asosiy ma'lumotlarni yuklab olmasdan oladi."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'id': info.get('id'),
            'title': info.get('title', 'Noma\'lum video'),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'Noma\'lum kanal'),
            'thumbnail': info.get('thumbnail'),
            'is_live': info.get('is_live', False),
            'filesize_approx': info.get('filesize_approx', 0),
        }


def download_youtube_video(url: str, output_dir: str = "downloads") -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    YouTube videoni mp4 formatida yuklab oladi.
    Telegram limitiga (50MB) moslashtirilgan.
    Qaytaradi: (fayl_yo'li, ma'lumotlar_lug'ati, xatolik_xabari)
    """
    os.makedirs(output_dir, exist_ok=True)
    task_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(output_dir, f"video_{task_id}.%(ext)s")

    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[ext=mp4][filesize<48M]/bestvideo[ext=mp4][filesize<40M]+bestaudio[ext=m4a]/best[filesize<48M]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        # 50MB dan ortiq yuklamaslik
        'max_filesize': 50 * 1024 * 1024,
    }

    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, None, "Video topilmadi."

            if info.get('is_live'):
                return None, None, "Jonli efir (Live stream) videolarini yuklab bo'lmaydi."

            # Yuklangan fayl nomini aniqlash
            filename = ydl.prepare_filename(info)
            # Ba'zan kengaytmasi mp4 bo'lmasligi mumkin yoki merge bo'lgandan keyin o'zgaradi
            base, _ = os.path.splitext(filename)
            mp4_filename = f"{base}.mp4"

            final_file = None
            if os.path.exists(filename):
                final_file = filename
            elif os.path.exists(mp4_filename):
                final_file = mp4_filename
            else:
                # Papkadagi yuklangan faylni qidirish
                for f in os.listdir(output_dir):
                    if f.startswith(f"video_{task_id}"):
                        final_file = os.path.join(output_dir, f)
                        break

            if not final_file or not os.path.exists(final_file):
                return None, None, "Fayl diskda topilmadi."

            file_size = os.path.getsize(final_file)
            if file_size > 50 * 1024 * 1024:
                try:
                    os.remove(final_file)
                except Exception:
                    pass
                return None, None, f"Video hajmi juda katta ({file_size / (1024 * 1024):.1f} MB). Telegram botlari orqali faqat 50 MB gacha yuborish mumkin."

            video_data = {
                'title': info.get('title', 'YouTube Video'),
                'uploader': info.get('uploader', 'YouTube'),
                'duration': info.get('duration', 0),
                'duration_str': format_duration(info.get('duration', 0)),
                'width': info.get('width'),
                'height': info.get('height'),
                'file_size': file_size,
            }
            return final_file, video_data, None

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "File is larger than max-filesize" in msg:
            return None, None, "Video hajmi 50 MB dan katta bo'lgani sababli yuklab bo'lmadi."
        return None, None, f"Yuklab olishda xatolik yuz berdi: {msg[:100]}"
    except Exception as e:
        return None, None, f"Kutilmagan xatolik: {str(e)[:100]}"


async def async_download_youtube_video(url: str, output_dir: str = "downloads") -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Taqdim etilgan funksiyani alohida thread'da asinxron ishga tushirish."""
    return await asyncio.to_thread(download_youtube_video, url, output_dir)
