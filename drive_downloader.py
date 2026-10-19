import os
import re
import shutil
import logging
from pathlib import Path
import gdown

from config import VIDEOS_DIR, BASE_DIR
from video_manager import format_size

logger = logging.getLogger(__name__)

DRIVE_URL_REGEX = re.compile(
    r'(https?:\/\/(?:drive|docs)\.google\.com\/[^\s]+)',
    re.IGNORECASE
)

DRIVE_FOLDER_REGEX = re.compile(
    r'drive\.google\.com\/(?:drive\/(?:u\/\d+\/)?folders\/|folderview\?id=)([a-zA-Z0-9_-]+)',
    re.IGNORECASE
)

DRIVE_FILE_REGEX = re.compile(
    r'drive\.google\.com\/(?:file\/d\/|open\?id=|uc\?id=)([a-zA-Z0-9_-]+)',
    re.IGNORECASE
)

def extract_drive_url(text: str) -> str | None:
    """Extracts first Google Drive link from text message."""
    if not text:
        return None
    match = DRIVE_URL_REGEX.search(text.strip())
    if match:
        url = match.group(0)
        return url.strip()
    return None

def is_drive_url(text: str) -> bool:
    """Checks if message contains a Google Drive URL."""
    return extract_drive_url(text) is not None

def is_folder_url(url: str) -> bool:
    """Checks if Google Drive URL points to a folder."""
    return "folders/" in url or "folderview" in url

def sanitize_filename(name: str) -> str:
    """Removes invalid filesystem characters."""
    clean = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', name)
    return re.sub(r'[\\/*?:"<>|]', "", clean).strip()

def scan_google_drive_folder(url: str) -> tuple[bool, dict]:
    """
    Quickly scans a Google Drive folder without downloading content.
    Returns: (success: bool, info_dict: dict)
    """
    clean_url = extract_drive_url(url) or url
    try:
        logger.info(f"Scanning Google Drive folder: {clean_url}")
        files = gdown.download_folder(url=clean_url, skip_download=True, use_cookies=False)
        if not files:
            return False, {
                "error": "ড্রাইভ ফোল্ডারে কোনো ফাইল পাওয়া যায়নি অথবা অ্যাক্সেস পারমিশন নেই।"
            }

        mp4_files = []
        for f in files:
            fname = Path(f.path).name
            if fname.lower().endswith(".mp4"):
                mp4_files.append({
                    "id": f.id,
                    "name": fname,
                    "rel_path": f.path
                })

        if not mp4_files:
            return False, {
                "error": f"ফোল্ডারে মোট {len(files)}টি ফাইল পাওয়া গেছে, কিন্তু কোনো .mp4 ভিডিও পাওয়া যায়নি।"
            }

        return True, {
            "total_files": len(files),
            "mp4_count": len(mp4_files),
            "mp4_files": mp4_files,
            "url": clean_url
        }
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error scanning Drive folder: {err_msg}")
        return False, {"error": f"ড্রাইভ স্ক্যান ত্রুটি: {err_msg[:120]}"}

def download_drive_batch(mp4_files: list[dict], max_count: int | None = None, progress_callback=None) -> tuple[bool, dict]:
    """
    Downloads .mp4 files file-by-file directly into VIDEOS_DIR.
    Provides incremental saving and real-time progress.
    """
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    target_files = mp4_files[:max_count] if max_count else mp4_files
    total_target = len(target_files)

    downloaded = []
    total_bytes = 0

    for i, item in enumerate(target_files):
        file_id = item["id"]
        raw_name = item["name"]
        clean_name = sanitize_filename(raw_name)
        if not clean_name.lower().endswith(".mp4"):
            clean_name += ".mp4"

        dest_path = VIDEOS_DIR / clean_name

        # If file already exists and has content, skip redownload
        if dest_path.exists() and dest_path.stat().st_size > 1024:
            fsize = dest_path.stat().st_size
            downloaded.append({"name": dest_path.name, "path": str(dest_path), "size": fsize})
            total_bytes += fsize
        else:
            try:
                temp_file = dest_path.with_suffix(".downloading")
                res = gdown.download(id=file_id, output=str(temp_file), quiet=True)
                if res and Path(res).exists():
                    fsize = Path(res).stat().st_size
                    if fsize > 1024:
                        if dest_path.exists():
                            dest_path.unlink()
                        Path(res).rename(dest_path)
                        downloaded.append({"name": dest_path.name, "path": str(dest_path), "size": fsize})
                        total_bytes += fsize
                    else:
                        Path(res).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to download file {clean_name} ({file_id}): {e}")

        # Trigger progress callback
        if progress_callback:
            try:
                progress_callback({
                    "current": i + 1,
                    "target": total_target,
                    "total_available": len(mp4_files),
                    "latest_file": clean_name,
                    "downloaded_count": len(downloaded),
                    "total_bytes": total_bytes,
                    "size_str": format_size(total_bytes)
                })
            except Exception:
                pass

    if not downloaded:
        return False, {"error": "একটিও .mp4 ভিডিও ডাউনলোড সম্পন্ন করা যায়নি।"}

    return True, {
        "count": len(downloaded),
        "total_size": total_bytes,
        "total_size_str": format_size(total_bytes),
        "files": downloaded
    }

def download_single_drive_file(url: str) -> tuple[bool, dict]:
    """Downloads a single Google Drive file link directly into VIDEOS_DIR."""
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    clean_url = extract_drive_url(url) or url

    temp_staging = BASE_DIR / "temp_single.mp4"
    try:
        output_file = gdown.download(url=clean_url, output=str(temp_staging), quiet=True, fuzzy=True)
        if not output_file or not Path(output_file).exists():
            return False, {"error": "ফাইলটি ডাউনলোড করা যায়নি। লিংকটির পারমিশন চেক করুন।"}

        src_path = Path(output_file)
        clean_name = sanitize_filename(src_path.name)
        if not clean_name.lower().endswith(".mp4"):
            clean_name += ".mp4"

        dest_path = VIDEOS_DIR / clean_name
        counter = 1
        while dest_path.exists():
            stem = Path(clean_name).stem
            dest_path = VIDEOS_DIR / f"{stem}_{counter}.mp4"
            counter += 1

        fsize = src_path.stat().st_size
        shutil.move(str(src_path), str(dest_path))

        return True, {
            "count": 1,
            "total_size": fsize,
            "total_size_str": format_size(fsize),
            "files": [{"name": dest_path.name, "path": str(dest_path), "size": fsize}]
        }
    except Exception as e:
        return False, {"error": f"ডাউনলোড ত্রুটি: {str(e)[:120]}"}
