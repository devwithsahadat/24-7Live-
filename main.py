import os
import sys
import time
import logging
from colorama import init, Fore, Style

from config import (
    BASE_DIR,
    VIDEOS_DIR,
    THUMBNAILS_DIR,
    LOGS_DIR,
    FFMPEG_LOG_DIR,
    TELEGRAM_BOT_TOKEN,
    get_node_id,
    get_all_slots,
    save_setting,
    is_valid_token,
    load_settings
)
from streamer import StreamManager
from video_manager import list_stock_videos
from bot import setup_telegram_bot

# Initialize Colorama
init(autoreset=True)

BANNER = f"""
{Fore.CYAN}====================================================================
{Fore.LIGHTGREEN_EX}   ____  __ __   __    _____ _   _ _____ _   _ _   _ _____  
{Fore.LIGHTGREEN_EX}  |___ \\| || |  | |   |_   _| \\ | | ____| \\ | | | | |_   _| 
{Fore.LIGHTGREEN_EX}    __) | || |_ | |     | | |  \\| |  _| |  \\| | | | | | |   
{Fore.LIGHTGREEN_EX}   / __/|__   _|| |___ _| |_| |\\  | |___| |\\  | |_| | | |   
{Fore.LIGHTGREEN_EX}  |_____|  |_|  |_____|_____|_| \\_|_____|_| \\_|\\___/  |_|   
{Fore.YELLOW}  24/7 Multi-Stream & Multi-RDP Live Hub (Parallel Channels)
{Fore.CYAN}===================================================================={Style.RESET_ALL}
"""

def print_banner():
    print(BANNER)

def check_setup():
    """Validates configuration and prompts if needed."""
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    FFMPEG_LOG_DIR.mkdir(parents=True, exist_ok=True)

    cfg = load_settings()
    token = cfg.get("TELEGRAM_BOT_TOKEN", "").strip()

    if not is_valid_token(token):
        print(f"\n{Fore.RED}[!] TELEGRAM_BOT_TOKEN পাওয়া যায়নি বা প্লেসহোল্ডার রয়েছে!{Style.RESET_ALL}")
        new_token = input(f"{Fore.YELLOW}দয়া করে আপনার Telegram Bot Token দিন (BotFather থেকে পাওয়া): {Style.RESET_ALL}").strip()
        if is_valid_token(new_token):
            save_setting("TELEGRAM_BOT_TOKEN", new_token)
            print(f"{Fore.GREEN}[✓] Bot Token সেভ করা হয়েছে!{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[x] সঠিক Bot Token ছাড়া টেলিগ্রাম বট চালু করা সম্ভব নয়।{Style.RESET_ALL}")
            sys.exit(1)

def main():
    print_banner()
    check_setup()

    node_name = get_node_id()
    slots = get_all_slots()
    videos = list_stock_videos()

    print(f"\n{Fore.GREEN}[✓] মাল্টি-স্ট্রিম সিস্টেম প্রস্তুত!{Style.RESET_ALL}")
    print(f"🖥️  হোস্ট নোড: {Fore.MAGENTA}{node_name}{Style.RESET_ALL}")
    print(f"🎛️  কনফিগার করা স্লট সংখ্যা: {Fore.CYAN}{len(slots)}টি চ্যানেল/স্লট{Style.RESET_ALL}")
    print(f"📁 বর্তমান ভিডিও স্টক: {Fore.CYAN}{len(videos)}টি ভিডিও{Style.RESET_ALL}")
    print(f"🤖 টেলিগ্রাম বট সার্ভিস শুরু হচ্ছে...")
    print(f"{Fore.YELLOW}💡 এখন থেকে আপনার টেলিগ্রাম বট থেকে যাবতীয় মাল্টিপল লাইভ স্ট্রিমিং ও আরডিপি নিয়ন্ত্রণ করুন।{Style.RESET_ALL}\n")

    try:
        app = setup_telegram_bot()
        print(f"{Fore.GREEN}[🚀 LIVE] বট সফলভাবে চালু হয়েছে এবং নতুন নির্দেশের অপেক্ষায় আছে...{Style.RESET_ALL}")
        print(f"{Fore.WHITE}(বট বন্ধ করতে কীবোর্ডে Ctrl+C চাপুন){Style.RESET_ALL}\n")
        app.run_polling()
    except Exception as e:
        print(f"\n{Fore.RED}[x] বট চালু হতে সমস্যা হয়েছে: {e}{Style.RESET_ALL}")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
