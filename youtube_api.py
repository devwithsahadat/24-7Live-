import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Paths for Google OAuth tokens
BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

def is_youtube_api_authenticated() -> bool:
    """Checks if valid YouTube OAuth token exists."""
    return TOKEN_FILE.exists()

def get_authenticated_service():
    """Builds and returns authorized YouTube Data API service."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            elif CLIENT_SECRETS_FILE.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            else:
                return None

        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Error authenticating YouTube API: {e}")
        return None

def update_live_broadcast_metadata(title: str, description: str, broadcast_id: str | None = None) -> tuple[bool, str]:
    """Updates live stream Title and Description directly on YouTube Studio."""
    youtube = get_authenticated_service()
    if not youtube:
        return False, "YouTube API Token পাওয়া যায়নি! (client_secrets.json দিয়ে অথেন্টিকেট করুন)"

    try:
        # If broadcast_id not provided, find currently active or scheduled live broadcast
        if not broadcast_id:
            req = youtube.liveBroadcasts().list(
                part="id,snippet,status",
                broadcastStatus="active",
                maxResults=5
            )
            res = req.execute()
            items = res.get("items", [])
            if not items:
                req = youtube.liveBroadcasts().list(
                    part="id,snippet,status",
                    broadcastStatus="all",
                    maxResults=5
                )
                res = req.execute()
                items = res.get("items", [])

            if items:
                broadcast_id = items[0]["id"]
            else:
                return False, "কোনো সক্রিয় বা শিডিউল করা লাইভ ব্রডকাস্ট পাওয়া যায়নি।"

        # Update metadata
        update_req = youtube.liveBroadcasts().update(
            part="snippet",
            body={
                "id": broadcast_id,
                "snippet": {
                    "title": title,
                    "description": description
                }
            }
        )
        update_req.execute()
        return True, f"✅ ইউটিউব স্টুডিওতে টাইটেল ও ডেসক্রিপশন সফলভাবে আপডেট হয়েছে! (Broadcast ID: {broadcast_id})"
    except Exception as e:
        return False, f"YouTube API এরর: {str(e)}"

def update_live_broadcast_thumbnail(image_path: str, broadcast_id: str | None = None) -> tuple[bool, str]:
    """Uploads custom thumbnail for live stream on YouTube Studio."""
    youtube = get_authenticated_service()
    if not youtube:
        return False, "YouTube API Token পাওয়া যায়নি।"

    img = Path(image_path)
    if not img.exists():
        return False, f"থাম্বনেইল ইমেজ পাওয়া যায়নি: {img.name}"

    try:
        from googleapiclient.http import MediaFileUpload

        if not broadcast_id:
            req = youtube.liveBroadcasts().list(
                part="id,snippet",
                broadcastStatus="all",
                maxResults=5
            )
            res = req.execute()
            items = res.get("items", [])
            if items:
                broadcast_id = items[0]["id"]
            else:
                return False, "কোনো লাইভ ব্রডকাস্ট পাওয়া যায়নি।"

        media = MediaFileUpload(str(img), mimetype="image/jpeg" if img.suffix.lower() in [".jpg", ".jpeg"] else "image/png")
        req = youtube.thumbnails().set(
            videoId=broadcast_id,
            media_body=media
        )
        req.execute()
        return True, f"✅ ইউটিউব স্টুডিওতে থাম্বনেইল সফলভাবে আপলোড হয়েছে! (Broadcast ID: {broadcast_id})"
    except Exception as e:
        return False, f"থাম্বনেইল আপলোড এরর: {str(e)}"
