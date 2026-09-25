import os
import json
import time
import psutil
import threading
import subprocess
from pathlib import Path
from datetime import datetime

from config import (
    YOUTUBE_RTMP_URL,
    FFMPEG_LOG_DIR,
    STREAM_HISTORY_FILE,
    get_slot,
    get_all_slots,
    get_node_id
)

def has_audio_stream(file_path: str) -> bool:
    """Checks if the video file contains an audio stream."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "json",
            str(file_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            return len(data.get("streams", [])) > 0
    except Exception:
        pass
    return False

class StreamSlotRunner:
    """Manages an individual stream process in a specific slot."""
    def __init__(self, slot_id: str):
        self.slot_id = slot_id
        self.process: subprocess.Popen | None = None
        self.is_running = False
        self.current_video: str | None = None
        self.current_mode: str = "long"
        self.start_time: datetime | None = None
        self.watchdog_thread: threading.Thread | None = None
        self.stop_requested = False
        self.restart_count = 0
        self.lock = threading.Lock()

    def _build_ffmpeg_command(self, video_path: str, mode: str, stream_key: str) -> list[str]:
        rtmp_dest = f"{YOUTUBE_RTMP_URL}/{stream_key}"
        slot_cfg = get_slot(self.slot_id)
        video_bitrate = slot_cfg.get("video_bitrate", "3000k")
        audio_bitrate = slot_cfg.get("audio_bitrate", "128k")
        fps = int(slot_cfg.get("fps", 30))
        preset = slot_cfg.get("preset", "veryfast")

        if mode == "shorts":
            video_filter = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
        else:
            video_filter = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"

        has_audio = has_audio_stream(video_path)

        cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1",
            "-i", str(video_path)
        ]

        if not has_audio:
            cmd.extend([
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"
            ])

        cmd.extend([
            "-vf", video_filter,
            "-c:v", "libx264",
            "-preset", preset,
            "-b:v", video_bitrate,
            "-maxrate", video_bitrate,
            "-bufsize", "6000k",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-g", str(fps * 2),
        ])

        if not has_audio:
            cmd.extend([
                "-map", "0:v:0",
                "-map", "1:a:0"
            ])
        else:
            cmd.extend([
                "-map", "0:v:0",
                "-map", "0:a:0"
            ])

        cmd.extend([
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-ar", "44100",
            "-ac", "2",
            "-flvflags", "no_duration_filesize",
            "-f", "flv",
            rtmp_dest
        ])

        return cmd

    def _watchdog(self, video_path: str, mode: str, stream_key: str):
        log_file_path = FFMPEG_LOG_DIR / f"{self.slot_id}.log"
        while not self.stop_requested and self.is_running:
            if self.process is not None:
                ret = self.process.poll()
                if ret is not None:
                    if not self.stop_requested:
                        self.restart_count += 1
                        time.sleep(5)
                        if not self.stop_requested:
                            try:
                                log_file = open(log_file_path, "a", encoding="utf-8", errors="ignore")
                                cmd = self._build_ffmpeg_command(video_path, mode, stream_key)
                                self.process = subprocess.Popen(
                                    cmd,
                                    stdout=log_file,
                                    stderr=log_file,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                                )
                            except Exception as e:
                                print(f"[Watchdog Error {self.slot_id}] {e}")
            time.sleep(2)

    def start(self, video_path: str, mode: str, stream_key: str) -> tuple[bool, str]:
        with self.lock:
            if self.is_running:
                return False, f"স্লট ({self.slot_id}) ইতিমধ্যে লাইভে চলছে!"

            target_path = Path(video_path)
            if not target_path.exists():
                return False, f"ভিডিও ফাইলটি পাওয়া যায়নি: {target_path.name}"

            if not stream_key:
                return False, "ইউটিউব স্ট্রিম কি সেট করা নেই!"

            self.stop_requested = False
            self.restart_count = 0
            self.current_video = target_path.name
            self.current_mode = mode
            self.start_time = datetime.now()

            cmd = self._build_ffmpeg_command(str(target_path), mode, stream_key)
            log_file_path = FFMPEG_LOG_DIR / f"{self.slot_id}.log"

            try:
                log_file = open(log_file_path, "w", encoding="utf-8", errors="ignore")
                log_file.write(f"[{datetime.now()}] Starting Slot: {self.slot_id}\nCommand: {' '.join(cmd)}\n\n")
                log_file.flush()

                self.process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=log_file,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )
                self.is_running = True

                self.watchdog_thread = threading.Thread(
                    target=self._watchdog,
                    args=(str(target_path), mode, stream_key),
                    daemon=True
                )
                self.watchdog_thread.start()

                slot_name = get_slot(self.slot_id).get("name", self.slot_id)
                return True, f"✅ [{slot_name}] লাইভ স্ট্রিম সফলভাবে শুরু হয়েছে!\n🎬 ভিডিও: {self.current_video}\n📐 মোড: {'শর্টস (9:16)' if mode == 'shorts' else 'লং (16:9)'}"
            except Exception as e:
                self.is_running = False
                self.process = None
                return False, f"FFmpeg চালাতে ব্যর্থ: {str(e)}"

    def stop(self) -> tuple[bool, str]:
        with self.lock:
            if not self.is_running and self.process is None:
                return False, f"স্লট ({self.slot_id})-এ কোনো লাইভ চলছে না।"

            self.stop_requested = True
            self.is_running = False
            end_time = datetime.now()

            # Record history
            if self.current_video and self.start_time:
                duration_sec = (end_time - self.start_time).total_seconds()
                m, s = divmod(int(duration_sec), 60)
                h, m = divmod(m, 60)
                dur_str = f"{h:02d}h {m:02d}m {s:02d}s"

                history_item = {
                    "node": get_node_id(),
                    "slot_id": self.slot_id,
                    "slot_name": get_slot(self.slot_id).get("name", self.slot_id),
                    "video_name": self.current_video,
                    "mode": "Shorts (9:16)" if self.current_mode == "shorts" else "Long (16:9)",
                    "start_time": self.start_time.strftime("%Y-%m-%d %I:%M:%S %p"),
                    "end_time": end_time.strftime("%Y-%m-%d %I:%M:%S %p"),
                    "duration": dur_str
                }
                try:
                    history = []
                    if STREAM_HISTORY_FILE.exists():
                        with open(STREAM_HISTORY_FILE, "r", encoding="utf-8") as f:
                            history = json.load(f)
                    history.insert(0, history_item)
                    history = history[:100]
                    with open(STREAM_HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump(history, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass

            if self.process is not None:
                try:
                    parent = psutil.Process(self.process.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                    self.process.wait(timeout=5)
                except Exception:
                    pass
                self.process = None

            video_stopped = self.current_video
            self.current_video = None
            self.start_time = None
            slot_name = get_slot(self.slot_id).get("name", self.slot_id)

            return True, f"⏹️ [{slot_name}] লাইভ স্ট্রিম সফলভাবে বন্ধ করা হয়েছে!\n(ভিডিও: {video_stopped or 'N/A'})"

    def get_status(self) -> dict:
        if self.process is not None:
            if self.process.poll() is not None:
                self.is_running = False

        slot_cfg = get_slot(self.slot_id)
        slot_name = slot_cfg.get("name", self.slot_id)

        if not self.is_running or self.start_time is None:
            return {
                "slot_id": self.slot_id,
                "slot_name": slot_name,
                "status": "STOPPED",
                "is_running": False,
                "video": None,
                "mode": slot_cfg.get("mode", "long"),
                "uptime": "00:00:00",
                "uptime_seconds": 0,
                "restarts": self.restart_count
            }

        uptime_seconds = int((datetime.now() - self.start_time).total_seconds())
        m, s = divmod(uptime_seconds, 60)
        h, m = divmod(m, 60)
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

        return {
            "slot_id": self.slot_id,
            "slot_name": slot_name,
            "status": "LIVE",
            "is_running": True,
            "video": self.current_video,
            "mode": "Shorts (9:16)" if self.current_mode == "shorts" else "Long (16:9)",
            "start_time": self.start_time.strftime("%I:%M:%S %p (%d %b)"),
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds,
            "restarts": self.restart_count
        }


class StreamManager:
    """Central manager managing multiple concurrent stream runners."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StreamManager, cls).__new__(cls)
                cls._instance._runners = {}
            return cls._instance

    def _get_runner(self, slot_id: str) -> StreamSlotRunner:
        if slot_id not in self._runners:
            self._runners[slot_id] = StreamSlotRunner(slot_id)
        return self._runners[slot_id]

    def start_stream(self, video_path: str, mode: str = "long", stream_key: str | None = None, slot_id: str = "slot_1") -> tuple[bool, str]:
        slot_cfg = get_slot(slot_id)
        actual_key = stream_key or slot_cfg.get("stream_key", "")
        runner = self._get_runner(slot_id)
        return runner.start(video_path, mode, actual_key)

    def stop_stream(self, slot_id: str = "slot_1") -> tuple[bool, str]:
        runner = self._get_runner(slot_id)
        return runner.stop()

    def stop_all_streams(self) -> list[str]:
        results = []
        for slot_id, runner in self._runners.items():
            if runner.is_running:
                _, msg = runner.stop()
                results.append(msg)
        return results

    def get_slot_status(self, slot_id: str = "slot_1") -> dict:
        runner = self._get_runner(slot_id)
        return runner.get_status()

    def get_all_status(self) -> dict:
        cpu_usage = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()

        slots_cfg = get_all_slots()
        slots_status = {}
        active_count = 0

        for slot_id in slots_cfg:
            st = self.get_slot_status(slot_id)
            slots_status[slot_id] = st
            if st["is_running"]:
                active_count += 1

        return {
            "node_id": get_node_id(),
            "cpu": f"{cpu_usage}%",
            "ram": f"{ram.percent}%",
            "active_streams_count": active_count,
            "total_slots_count": len(slots_cfg),
            "slots": slots_status
        }

    # Backward compatibility helper
    def get_status(self) -> dict:
        from config import get_active_slot_id
        active_id = get_active_slot_id()
        st = self.get_slot_status(active_id)
        cpu_usage = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        st["cpu"] = f"{cpu_usage}%"
        st["ram"] = f"{ram.percent}%"
        return st

    def get_history(self) -> list[dict]:
        if STREAM_HISTORY_FILE.exists():
            try:
                with open(STREAM_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []
