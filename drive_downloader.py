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

def download_from_google_drive(url: str, progress_callback=None) -> tuple[bool, dict]:
    """
    Downloads .mp4 video files from a Google Drive folder or single file link into VIDEOS_DIR.
    Filters exclusively for .mp4 files as requested.
    Returns: (success: bool, info_dict: dict)
    """
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    temp_download_dir = BASE_DIR / "temp_drive_downloads"
    if temp_download_dir.exists():
        shutil.rmtree(temp_download_dir, ignore_errors=True)
    temp_download_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files = []
    total_bytes = 0

    try:
        clean_url = extract_drive_url(url) or url

        if is_folder_url(clean_url):
            logger.info(f"Downloading Google Drive folder: {clean_url}")
            # Download folder to temporary staging area
            results = gdown.download_folder(
                url=clean_url,
                output=str(temp_download_dir),
                quiet=True,
                use_cookies=False,
                remaining_ok=True
            )

            # Search temp_download_dir recursively for all .mp4 files
            for root, _, files in os.walk(temp_download_dir):
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext == ".mp4":
                        src_path = Path(root) / f
                        clean_name = sanitize_filename(src_path.name)
                        if not clean_name.lower().endswith(".mp4"):
                            clean_name += ".mp4"

                        dest_path = VIDEOS_DIR / clean_name
                        # Handle duplicate filenames
                        counter = 1
                        while dest_path.exists():
                            stem = Path(clean_name).stem
                            dest_path = VIDEOS_DIR / f"{stem}_{counter}.mp4"
                            counter += 1

                        file_size = src_path.stat().st_size
                        shutil.move(str(src_path), str(dest_path))
                        downloaded_files.append({
                            "name": dest_path.name,
                            "path": str(dest_path),
                            "size": file_size
                        })
                        total_bytes += file_size

        else:
            logger.info(f"Downloading single Google Drive file: {clean_url}")
            output_file = gdown.download(
                url=clean_url,
                output=str(temp_download_dir) + os.sep,
                quiet=True,
                fuzzy=True
            )

            if output_file and Path(output_file).exists():
                src_path = Path(output_file)
                ext = src_path.suffix.lower()
                if ext != ".mp4":
                    # If file has no extension but is mp4, or user wants mp4 only
                    if not ext:
                        clean_name = sanitize_filename(src_path.name) + ".mp4"
                    else:
                        shutil.rmtree(temp_download_dir, ignore_errors=True)
                        return False, {
                            "error": f"ফাইলটি .mp4 ফরম্যাট নয় (ফরম্যাট: {ext})। শুধু .mp4 ভিডিও ডাউনলোড করা হবে।"
                        }
                else:
                    clean_name = sanitize_filename(src_path.name)

                dest_path = VIDEOS_DIR / clean_name
                counter = 1
                while dest_path.exists():
                    stem = Path(clean_name).stem
                    dest_path = VIDEOS_DIR / f"{stem}_{counter}.mp4"
                    counter += 1

                file_size = src_path.stat().st_size
                shutil.move(str(src_path), str(dest_path))
                downloaded_files.append({
                    "name": dest_path.name,
                    "path": str(dest_path),
                    "size": file_size
                })
                total_bytes += file_size

        # Cleanup temp directory
        shutil.rmtree(temp_download_dir, ignore_errors=True)

        if not downloaded_files:
            return False, {
                "error": "ড্রাইভ লিংক থেকে কোনো .mp4 ভিডিও পাওয়া যায়নি। অনুগ্রহ করে নিশ্চিত করুন ফোল্ডারে .mp4 ভিডিও আছে এবং লিংকটি 'Anyone with the link can view' করা আছে।"
            }

        return True, {
            "count": len(downloaded_files),
            "files": downloaded_files,
            "total_size": total_bytes,
            "total_size_str": format_size(total_bytes)
        }

    except Exception as e:
        shutil.rmtree(temp_download_dir, ignore_errors=True)
        err_msg = str(e)
        logger.error(f"Google Drive download error: {err_msg}")
        if "Cannot retrieve" in err_msg or "Permission denied" in err_msg:
            return False, {
                "error": "ড্রাইভ ফাইল অ্যাক্সেস করা যায়নি। অনুগ্রহ করে নিশ্চিত করুন গুগল ড্রাইভে লিংকটির পারমিশন 'Anyone with the link' (Viewer) সেট করা আছে।"
            }
        return False, {"error": f"ড্রাইভ ডাউনলোড ত্রুটি: {err_msg[:150]}"}
