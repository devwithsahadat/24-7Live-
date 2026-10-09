import os
import re
import logging
from pathlib import Path
import yt_dlp

from config import VIDEOS_DIR, BASE_DIR
from video_manager import format_size

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
    r'www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
    r'https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|'
    r'youtu\.be\/[a-zA-Z0-9_-]+|'
    r'youtube\.com\/[^\s]+)',
    re.IGNORECASE
)

def extract_url(text: str) -> str | None:
    """Extracts first valid HTTP/HTTPS URL from text message."""
    if not text:
        return None
    match = URL_REGEX.search(text.strip())
    if match:
        url = match.group(0)
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        return url
    return None

def is_video_url(text: str) -> bool:
    """Checks if message contains a video URL."""
    return extract_url(text) is not None

def sanitize_filename(name: str) -> str:
    """Removes invalid filesystem characters."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def download_video_from_url(url: str, progress_callback=None) -> tuple[bool, dict]:
    """
    Downloads video using yt-dlp, merges best video + best audio to MP4.
    Returns: (success: bool, info_dict: dict)
    """
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check for local ffmpeg binary path if available
    ffmpeg_bin_dir = BASE_DIR / "ffmpeg" / "bin"
    ffmpeg_loc = str(ffmpeg_bin_dir) if (ffmpeg_bin_dir / "ffmpeg.exe").exists() else None

    downloaded_file = None

    def internal_progress_hook(d):
        nonlocal downloaded_file
        if d.get('status') == 'finished':
            downloaded_file = d.get('filename')
        if progress_callback:
            try:
                progress_callback(d)
            except Exception:
                pass

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
        'outtmpl': str(VIDEOS_DIR / '%(title).60s [%(id)s].%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [internal_progress_hook],
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    if ffmpeg_loc:
        ydl_opts['ffmpeg_location'] = ffmpeg_loc

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(url, download=True)
            if not meta:
                return False, {"error": "ভিডিও মেটাডেটা পাওয়া যায়নি। লিঙ্কটি সঠিক কিনা যাচাই করুন।"}

            title = meta.get('title', 'Downloaded_Video')
            video_id = meta.get('id', 'unknown')
            duration_sec = meta.get('duration', 0)
            
            # Find the actual output file
            expected_filename = ydl.prepare_filename(meta)
            target_mp4 = Path(expected_filename).with_suffix('.mp4')
            
            final_path = None
            if target_mp4.exists():
                final_path = target_mp4
            elif Path(expected_filename).exists():
                final_path = Path(expected_filename)
            elif downloaded_file and Path(downloaded_file).exists():
                final_path = Path(downloaded_file)
            else:
                # Search recently created file in VIDEOS_DIR
                for f in VIDEOS_DIR.glob(f"*{video_id}*"):
                    if f.is_file():
                        final_path = f
                        break

            if not final_path or not final_path.exists():
                return False, {"error": "ভিডিও ডাউনলোড সফল হলেও ফাইলটি খুঁজে পাওয়া যায়নি।"}

            # Calculate duration string
            m, s = divmod(int(duration_sec or 0), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

            file_size_str = format_size(final_path.stat().st_size)

            return True, {
                "title": title,
                "file_name": final_path.name,
                "file_path": str(final_path),
                "duration_str": dur_str,
                "duration_sec": duration_sec,
                "size_str": file_size_str,
                "thumbnail_url": meta.get('thumbnail')
            }

    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e)
        if "Private video" in err_msg:
            return False, {"error": "এই ভিডিওটি প্রাইভেট (Private) হওয়ায় ডাউনলোড করা যাচ্ছে না।"}
        elif "Video unavailable" in err_msg:
            return False, {"error": "ভিডিওটি অনুপলব্ধ (Unavailable) বা মুছে ফেলা হয়েছে।"}
        return False, {"error": f"ডাউনলোড ত্রুটি: {err_msg[:120]}"}
    except Exception as e:
        return False, {"error": f"অপ্রত্যাশিত ত্রুটি: {str(e)[:120]}"}
