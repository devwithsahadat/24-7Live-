import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from config import VIDEOS_DIR, THUMBNAILS_DIR, SUPPORTED_EXTENSIONS, SUPPORTED_IMAGE_EXTENSIONS

def format_size(bytes_size: int) -> str:
    """Formats file size into human readable string (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def get_video_info(file_path: Path) -> dict:
    """Extracts resolution, duration, and codec details using ffprobe."""
    info = {
        "duration": 0,
        "duration_str": "Unknown",
        "width": 0,
        "height": 0,
        "aspect_ratio": "Unknown",
        "size_str": format_size(file_path.stat().st_size) if file_path.exists() else "0 B",
        "name": file_path.name,
        "path": str(file_path)
    }

    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "json",
            str(file_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            fmt = data.get("format", {})

            if streams:
                v_stream = streams[0]
                width = int(v_stream.get("width", 0))
                height = int(v_stream.get("height", 0))
                info["width"] = width
                info["height"] = height
                if width > 0 and height > 0:
                    if width > height:
                        info["aspect_ratio"] = "Landscape (16:9)"
                    elif height > width:
                        info["aspect_ratio"] = "Vertical (9:16 Shorts)"
                    else:
                        info["aspect_ratio"] = "Square (1:1)"

            dur_sec = float(fmt.get("duration", 0) or (streams[0].get("duration", 0) if streams else 0))
            if dur_sec > 0:
                info["duration"] = dur_sec
                m, s = divmod(int(dur_sec), 60)
                h, m = divmod(m, 60)
                if h > 0:
                    info["duration_str"] = f"{h:02d}:{m:02d}:{s:02d}"
                else:
                    info["duration_str"] = f"{m:02d}:{s:02d}"
    except Exception:
        pass

    return info

def list_stock_videos() -> list[dict]:
    """Scans videos directory and returns a list of all available videos."""
    videos = []
    if not VIDEOS_DIR.exists():
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        return videos

    for file in sorted(VIDEOS_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS:
            videos.append(get_video_info(file))
    return videos

def get_video_by_index(index: int) -> dict | None:
    """Returns video info by index."""
    videos = list_stock_videos()
    if 0 <= index < len(videos):
        return videos[index]
    return None

def delete_video_by_index(index: int) -> bool:
    """Deletes a video by its index."""
    video = get_video_by_index(index)
    if video:
        try:
            Path(video["path"]).unlink(missing_ok=True)
            return True
        except Exception:
            return False
    return False

def list_stock_thumbnails() -> list[dict]:
    """Scans thumbnails directory and returns list of image files."""
    thumbs = []
    if not THUMBNAILS_DIR.exists():
        THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
        return thumbs

    for file in sorted(THUMBNAILS_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
        if file.is_file() and file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            thumbs.append({
                "name": file.name,
                "path": str(file),
                "size_str": format_size(file.stat().st_size),
                "mtime": datetime.fromtimestamp(file.stat().st_mtime).strftime("%d %b, %I:%M %p")
            })
    return thumbs

def get_latest_thumbnail() -> dict | None:
    """Gets the most recently uploaded thumbnail."""
    thumbs = list_stock_thumbnails()
    if thumbs:
        return thumbs[0]
    return None
