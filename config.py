import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Paths
VIDEOS_DIR = BASE_DIR / "videos"
THUMBNAILS_DIR = BASE_DIR / "thumbnails"
LOGS_DIR = BASE_DIR / "logs"
STREAM_HISTORY_FILE = LOGS_DIR / "stream_history.json"
FFMPEG_LOG_DIR = LOGS_DIR / "ffmpeg_logs"
CONFIG_JSON_FILE = BASE_DIR / "settings.json"
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE_FILE = BASE_DIR / ".env.example"

VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Load .env file if present
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)
elif ENV_EXAMPLE_FILE.exists():
    load_dotenv(ENV_EXAMPLE_FILE, override=True)

# Placeholders to ignore
PLACEHOLDERS = {
    "your_telegram_bot_token_here",
    "your_token_here",
    "your_youtube_stream_key_here",
    "your_stream_key_here",
    ""
}

def is_valid_token(tok: str) -> bool:
    """Validates if token is non-empty and not a placeholder."""
    if not tok:
        return False
    t = tok.strip().lower()
    return t not in PLACEHOLDERS and "your_" not in t

# Default Slot Template
DEFAULT_SLOT_TEMPLATE = {
    "name": "লাইভ স্লট",
    "stream_key": "dj2s-bf51-pfd3-q21t-8tp2",
    "title": "24/7 Live Stream",
    "description": "Welcome to our 24/7 Live Stream!",
    "thumbnail": "",
    "mode": "long",
    "video": "",
    "video_bitrate": "3000k",
    "audio_bitrate": "128k",
    "fps": 30,
    "preset": "veryfast"
}

# Default Multi-Slot Config Structure
DEFAULT_CONFIG = {
    "NODE_ID": "RDP-1 (Main Server)",
    "TELEGRAM_BOT_TOKEN": "8054588099:AAGCUxAcp7SRxePW07X4_3Qx1umZgxiHYnA",
    "TELEGRAM_ADMIN_ID": "7190342953",
    "ACTIVE_SLOT": "slot_1",
    "slots": {
        "slot_1": {
            "name": "লাইভ স্লট ১ (Main)",
            "stream_key": "dj2s-bf51-pfd3-q21t-8tp2",
            "title": "24/7 Live Stream",
            "description": "Welcome to our 24/7 Live Stream!",
            "thumbnail": "",
            "mode": "long",
            "video": "",
            "video_bitrate": "3000k",
            "audio_bitrate": "128k",
            "fps": 30,
            "preset": "veryfast"
        },
        "slot_2": {
            "name": "লাইভ স্লট ২",
            "stream_key": "",
            "title": "24/7 Continuous Live",
            "description": "Non-stop 24/7 Live Broadcast",
            "thumbnail": "",
            "mode": "long",
            "video": "",
            "video_bitrate": "3000k",
            "audio_bitrate": "128k",
            "fps": 30,
            "preset": "veryfast"
        },
        "slot_3": {
            "name": "লাইভ স্লট ৩",
            "stream_key": "",
            "title": "24/7 Special Stream",
            "description": "Continuous Live Stream Channel",
            "thumbnail": "",
            "mode": "long",
            "video": "",
            "video_bitrate": "3000k",
            "audio_bitrate": "128k",
            "fps": 30,
            "preset": "veryfast"
        }
    }
}

def load_settings() -> dict:
    """Loads settings from settings.json and environment with placeholder filtering."""
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_JSON_FILE.exists():
        try:
            with open(CONFIG_JSON_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if "slots" not in saved:
                    migrated_slot_1 = DEFAULT_SLOT_TEMPLATE.copy()
                    migrated_slot_1.update({
                        "name": "লাইভ স্লট ১ (Main)",
                        "stream_key": saved.get("YOUTUBE_STREAM_KEY", "dj2s-bf51-pfd3-q21t-8tp2"),
                        "title": saved.get("YOUTUBE_STREAM_TITLE", "24/7 Live Stream"),
                        "description": saved.get("YOUTUBE_STREAM_DESC", "Welcome to our 24/7 Live Stream!"),
                        "thumbnail": saved.get("CURRENT_THUMBNAIL", ""),
                        "video_bitrate": saved.get("VIDEO_BITRATE", "3000k"),
                        "audio_bitrate": saved.get("AUDIO_BITRATE", "128k"),
                        "fps": saved.get("FPS", 30),
                        "preset": saved.get("PRESET", "veryfast")
                    })
                    cfg["slots"] = {"slot_1": migrated_slot_1}
                    if "NODE_ID" in saved:
                        cfg["NODE_ID"] = saved["NODE_ID"]
                    if "TELEGRAM_BOT_TOKEN" in saved and is_valid_token(saved["TELEGRAM_BOT_TOKEN"]):
                        cfg["TELEGRAM_BOT_TOKEN"] = saved["TELEGRAM_BOT_TOKEN"]
                    if "TELEGRAM_ADMIN_ID" in saved:
                        cfg["TELEGRAM_ADMIN_ID"] = saved["TELEGRAM_ADMIN_ID"]
                else:
                    cfg.update(saved)
        except Exception:
            pass

    # Override from env if valid
    env_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if is_valid_token(env_token):
        cfg["TELEGRAM_BOT_TOKEN"] = env_token

    env_admin = os.getenv("TELEGRAM_ADMIN_ID", "").strip()
    if env_admin and env_admin not in PLACEHOLDERS:
        cfg["TELEGRAM_ADMIN_ID"] = env_admin

    env_node = os.getenv("NODE_ID", "").strip()
    if env_node and env_node not in PLACEHOLDERS:
        cfg["NODE_ID"] = env_node

    # If cfg token is placeholder, fallback to default hardcoded token
    if not is_valid_token(cfg.get("TELEGRAM_BOT_TOKEN", "")):
        cfg["TELEGRAM_BOT_TOKEN"] = DEFAULT_CONFIG["TELEGRAM_BOT_TOKEN"]

    return cfg

def save_all_settings(cfg: dict):
    """Saves entire config dict into settings.json."""
    with open(CONFIG_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_node_id() -> str:
    cfg = load_settings()
    return cfg.get("NODE_ID", "RDP-1 (Main Server)")

def set_node_id(node_id: str):
    cfg = load_settings()
    cfg["NODE_ID"] = node_id.strip()
    save_all_settings(cfg)

def get_all_slots() -> dict:
    cfg = load_settings()
    return cfg.get("slots", {})

def get_slot(slot_id: str) -> dict:
    slots = get_all_slots()
    if slot_id in slots:
        return slots[slot_id]
    t = DEFAULT_SLOT_TEMPLATE.copy()
    t["name"] = f"স্লট {slot_id}"
    return t

def save_slot(slot_id: str, slot_data: dict):
    cfg = load_settings()
    if "slots" not in cfg:
        cfg["slots"] = {}
    cfg["slots"][slot_id] = slot_data
    save_all_settings(cfg)

def update_slot_field(slot_id: str, field: str, value: any):
    slot = get_slot(slot_id)
    slot[field] = value
    save_slot(slot_id, slot)

def create_new_slot(name: str | None = None) -> str:
    cfg = load_settings()
    if "slots" not in cfg:
        cfg["slots"] = {}
    slots = cfg["slots"]
    new_num = 1
    while f"slot_{new_num}" in slots:
        new_num += 1
    new_slot_id = f"slot_{new_num}"
    new_slot_data = DEFAULT_SLOT_TEMPLATE.copy()
    new_slot_data["name"] = name or f"লাইভ স্লট {new_num}"
    slots[new_slot_id] = new_slot_data
    save_all_settings(cfg)
    return new_slot_id

def delete_slot(slot_id: str) -> bool:
    cfg = load_settings()
    if "slots" in cfg and slot_id in cfg["slots"]:
        if len(cfg["slots"]) <= 1:
            return False
        del cfg["slots"][slot_id]
        save_all_settings(cfg)
        return True
    return False

def get_active_slot_id() -> str:
    cfg = load_settings()
    active = cfg.get("ACTIVE_SLOT", "slot_1")
    slots = get_all_slots()
    if active not in slots and slots:
        active = list(slots.keys())[0]
    return active

def set_active_slot_id(slot_id: str):
    cfg = load_settings()
    cfg["ACTIVE_SLOT"] = slot_id
    save_all_settings(cfg)

def get_setting(key: str, default: str = "") -> str:
    cfg = load_settings()
    if key in cfg:
        return str(cfg[key])
    active_slot = get_slot(get_active_slot_id())
    field_map = {
        "YOUTUBE_STREAM_KEY": "stream_key",
        "YOUTUBE_STREAM_TITLE": "title",
        "YOUTUBE_STREAM_DESC": "description",
        "CURRENT_THUMBNAIL": "thumbnail",
        "VIDEO_BITRATE": "video_bitrate",
        "AUDIO_BITRATE": "audio_bitrate",
        "FPS": "fps",
        "PRESET": "preset"
    }
    if key in field_map:
        val = active_slot.get(field_map[key], default)
        if str(val) in PLACEHOLDERS:
            return default
        return str(val)
    return default

def save_setting(key: str, value: str):
    cfg = load_settings()
    if key in ["NODE_ID", "TELEGRAM_BOT_TOKEN", "TELEGRAM_ADMIN_ID", "ACTIVE_SLOT"]:
        cfg[key] = str(value).strip()
        save_all_settings(cfg)
        return

    active_id = get_active_slot_id()
    field_map = {
        "YOUTUBE_STREAM_KEY": "stream_key",
        "YOUTUBE_STREAM_TITLE": "title",
        "YOUTUBE_STREAM_DESC": "description",
        "CURRENT_THUMBNAIL": "thumbnail",
        "VIDEO_BITRATE": "video_bitrate",
        "AUDIO_BITRATE": "audio_bitrate",
        "FPS": "fps",
        "PRESET": "preset"
    }
    if key in field_map:
        update_slot_field(active_id, field_map[key], str(value).strip())
    else:
        cfg[key] = str(value).strip()
        save_all_settings(cfg)

def update_env_variable(key: str, value: str):
    save_setting(key, value)

# Supported Extensions
SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".flv", ".avi", ".ts", ".webm", ".m4v"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Static config exports
YOUTUBE_RTMP_URL = "rtmp://a.rtmp.youtube.com/live2"
TELEGRAM_BOT_TOKEN = get_setting("TELEGRAM_BOT_TOKEN", "8054588099:AAGCUxAcp7SRxePW07X4_3Qx1umZgxiHYnA")
TELEGRAM_ADMIN_ID = get_setting("TELEGRAM_ADMIN_ID", "7190342953")
