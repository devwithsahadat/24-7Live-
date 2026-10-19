import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import config
from config import (
    TELEGRAM_BOT_TOKEN,
    VIDEOS_DIR,
    THUMBNAILS_DIR,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    get_node_id,
    set_node_id,
    get_all_slots,
    get_slot,
    save_slot,
    update_slot_field,
    create_new_slot,
    delete_slot,
    get_active_slot_id,
    set_active_slot_id,
    get_setting,
    save_setting
)
from streamer import StreamManager, PLAYLIST_LOOP_ALL
from video_manager import (
    list_stock_videos,
    get_video_by_index,
    delete_video_by_index,
    list_stock_thumbnails,
    get_latest_thumbnail,
    format_size
)
from youtube_api import (
    is_youtube_api_authenticated,
    update_live_broadcast_metadata,
    update_live_broadcast_thumbnail
)
from yt_downloader import (
    is_video_url,
    extract_url,
    download_video_from_url
)
from drive_downloader import (
    is_drive_url,
    extract_drive_url,
    download_from_google_drive
)

# Setup Logger
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

stream_manager = StreamManager()

def is_admin(user_id: int) -> bool:
    """Checks if the user is authorized admin."""
    admin_id = get_setting("TELEGRAM_ADMIN_ID", "")
    if not admin_id:
        return True
    return str(user_id) == str(admin_id)

def get_main_keyboard():
    """Persistent bottom reply keyboard."""
    keyboard = [
        [KeyboardButton("📊 মাল্টি-লাইভ ড্যাশবোর্ড"), KeyboardButton("🚀 লাইভ শুরু করুন")],
        [KeyboardButton("🚗 ড্রাইভ থেকে ডাউনলোড"), KeyboardButton("📁 ভিডিও স্টক")],
        [KeyboardButton("🎛️ স্লট ম্যানেজার"), KeyboardButton("⚙️ ইউটিউব ও স্লট সেটআপ")],
        [KeyboardButton("🖼️ থাম্বনেইল গ্যালারি"), KeyboardButton("⏹️ লাইভ বন্ধ করুন")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command and welcomes the user."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ দুঃখিত! এই বটটি ব্যবহারের অনুমতি আপনার নেই।")
        return

    context.user_data.pop("waiting_for", None)

    all_status = stream_manager.get_all_status()
    node_name = get_node_id()
    active_count = all_status["active_streams_count"]
    total_slots = all_status["total_slots_count"]

    text = (
        f"👋 হ্যালো **{user.first_name}**!\n\n"
        "🤖 **24/7 Multi-Stream & Multi-RDP Live Automation Hub**-এ স্বাগতম।\n\n"
        f"🖥️ **হোস্ট নোড:** `{node_name}`\n"
        f"🔴 **চলমান লাইভ:** `{active_count}`টি / মোট `{total_slots}`টি স্লট\n"
        f"💻 **সার্ভার লোড:** CPU: `{all_status['cpu']}` | RAM: `{all_status['ram']}`\n\n"
        "✨ **মূল ফিচারসমূহ:**\n"
        "• 📥 **yt-dlp অটো-ডাউনলোড:** চ্যাটে সরাসরি যেকোনো ইউটিউব/ভিডিও লিংক পেস্ট করলেই অটো-ডাউনলোড হবে!\n"
        "• 🎛️ **একই RDP-তে একাধিক লাইভ:** আলাদা স্লটে একসঙ্গে ৩-৪টি লাইভ চালাতে পারবেন।\n"
        "• 🌐 **মাল্টি-RDP সাপোর্ট:** একাধিক RDP সার্ভার এই বট থেকেই পরিচালিত হবে।\n"
        "• 📝 **টাইটেল ও থাম্বনেইল:** প্রতি স্লটের জন্য আলাদা ইউটিউব টাইটেল ও থাম্বনেইল।\n"
        "• 🔄 **২৪/৭ অটো-লুপ ও রিকানেক্ট:** ভিডিও শেষ হলে অটোমেটিক রিপিট ও নেটওয়ার্ক ব্যাকআপ।"
    )
    await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

async def send_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Displays multi-stream live dashboard with real-time status of all slots."""
    all_status = stream_manager.get_all_status()
    slots_data = all_status["slots"]
    node_name = get_node_id()

    text = (
        f"📊 **[ মাল্টি-লাইভ স্ট্যাটাস ড্যাশবোর্ড ]**\n"
        f"🖥️ **হোস্ট সার্ভার:** `{node_name}`\n"
        f"💻 **CPU:** `{all_status['cpu']}` | **RAM:** `{all_status['ram']}`\n"
        f"🔴 **মোট সক্রিয় লাইভ:** `{all_status['active_streams_count']}` / `{all_status['total_slots_count']}` টি\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    buttons = []

    for slot_id, st in slots_data.items():
        slot_cfg = get_slot(slot_id)
        slot_name = slot_cfg.get("name", slot_id)
        
        if st["is_running"]:
            text += (
                f"🟢 **[{slot_name}] - লাইভ চলছে**\n"
                f"   └ 🎬 ভিডিও: `{st['video']}`\n"
                f"   └ 📐 মোড: `{st['mode']}` | ⏳ আপটাইম: `{st['uptime']}`\n"
                f"   └ 📝 টাইটেল: `{slot_cfg.get('title', 'N/A')[:35]}...`\n\n"
            )
            buttons.append([
                InlineKeyboardButton(f"🟢 {slot_name} (লাইভ)", callback_data=f"manage_slot_{slot_id}"),
                InlineKeyboardButton("⏹️ বন্ধ করুন", callback_data=f"quick_stop_{slot_id}")
            ])
        else:
            has_key = "✅ কি সেট আছে" if slot_cfg.get("stream_key") else "❌ কি নেই"
            text += (
                f"⚪ **[{slot_name}] - বন্ধ (IDLE)**\n"
                f"   └ 🔑 অবস্থা: `{has_key}`\n"
                f"   └ 📝 টাইটেল: `{slot_cfg.get('title', 'N/A')[:35]}...`\n\n"
            )
            buttons.append([
                InlineKeyboardButton(f"⚪ {slot_name}", callback_data=f"manage_slot_{slot_id}"),
                InlineKeyboardButton("🚀 লাইভ চালু", callback_data=f"start_slot_flow_{slot_id}")
            ])

    buttons.append([
        InlineKeyboardButton("🔄 রিফ্রেশ ড্যাশবোর্ড", callback_data="refresh_dashboard"),
        InlineKeyboardButton("➕ নতুন স্লট যোগ", callback_data="create_slot_action")
    ])
    buttons.append([
        InlineKeyboardButton("⏹️ সব লাইভ একসাথে বন্ধ করুন", callback_data="confirm_stop_all")
    ])

    reply_markup = InlineKeyboardMarkup(buttons)

    if is_callback and update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_slot_manager(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Displays interactive slots management menu."""
    slots = get_all_slots()
    node_name = get_node_id()

    text = (
        "🎛️ **স্লট ও আরডিপি ম্যানেজার:**\n"
        f"🖥️ **বর্তমান নোড:** `{node_name}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 যে স্লটের সেটিংস পরিবর্তন বা লাইভ নিয়ন্ত্রণ করতে চান, তা নির্বাচন করুন:\n\n"
    )

    buttons = []
    for slot_id, slot in slots.items():
        st = stream_manager.get_slot_status(slot_id)
        indicator = "🟢 [LIVE]" if st["is_running"] else "⚪"
        btn_text = f"{indicator} {slot.get('name', slot_id)}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"manage_slot_{slot_id}")])

    buttons.append([
        InlineKeyboardButton("➕ নতুন স্লট তৈরি করুন", callback_data="create_slot_action"),
        InlineKeyboardButton("🖥️ নোড নাম পরিবর্তন", callback_data="prompt_set_node_name")
    ])
    buttons.append([InlineKeyboardButton("🔙 মূল মেনু", callback_data="back_to_dashboard")])

    reply_markup = InlineKeyboardMarkup(buttons)

    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_slot_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, slot_id: str, is_callback: bool = True):
    """Shows details and controls for a specific slot."""
    slot = get_slot(slot_id)
    st = stream_manager.get_slot_status(slot_id)
    set_active_slot_id(slot_id)

    curr_key = slot.get("stream_key", "")
    masked_key = f"{curr_key[:4]}****{curr_key[-4:]}" if len(curr_key) > 8 else ("⚠️ সেট করা নেই!" if not curr_key else curr_key)
    thumb_path = slot.get("thumbnail", "")
    thumb_display = f"`{Path(thumb_path).name}`" if thumb_path and Path(thumb_path).exists() else "⚪ সেট করা নেই"
    
    api_status = "🟢 সংযুক্ত" if is_youtube_api_authenticated() else "⚪ অসক্রিয় (লোকাল মোড)"

    text = (
        f"⚙️ **স্লট নিয়ন্ত্রণ: [{slot.get('name', slot_id)}]**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **অবস্থা:** `{'🟢 লাইভ চলছে' if st['is_running'] else '⚪ বন্ধ'}`\n"
        f"⏳ **আপটাইম:** `{st['uptime']}`\n"
        f"🔑 **Stream Key:** `{masked_key}`\n"
        f"📝 **Title:** `{slot.get('title', 'N/A')}`\n"
        f"📄 **Description:** `{slot.get('description', 'N/A')[:100]}...`\n"
        f"🖼️ **Thumbnail:** {thumb_display}\n"
        f"🌐 **YouTube API Sync:** `{api_status}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 নিচের বাটনগুলো দিয়ে এই স্লটটি নিয়ন্ত্রণ করুন:"
    )

    buttons = []
    if st["is_running"]:
        buttons.append([
            InlineKeyboardButton("⏹️ এই স্লটের লাইভ বন্ধ করুন", callback_data=f"quick_stop_{slot_id}"),
            InlineKeyboardButton("🔄 রিফ্রেশ", callback_data=f"manage_slot_{slot_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("🚀 এই স্লটে লাইভ চালু করুন", callback_data=f"start_slot_flow_{slot_id}")
        ])

    buttons.append([
        InlineKeyboardButton("🔑 স্ট্রিম কি পরিবর্তন", callback_data=f"edit_key_{slot_id}"),
        InlineKeyboardButton("📝 টাইটেল পরিবর্তন", callback_data=f"edit_title_{slot_id}")
    ])
    buttons.append([
        InlineKeyboardButton("📄 ডেসক্রিপশন পরিবর্তন", callback_data=f"edit_desc_{slot_id}"),
        InlineKeyboardButton("🖼️ থাম্বনেইল পরিবর্তন", callback_data=f"edit_thumb_{slot_id}")
    ])
    buttons.append([
        InlineKeyboardButton("✏️ স্লটের নাম পরিবর্তন", callback_data=f"edit_slotname_{slot_id}"),
        InlineKeyboardButton("🗑️ স্লট মুছুন", callback_data=f"delete_slot_{slot_id}")
    ])
    buttons.append([InlineKeyboardButton("🔙 স্লট তালিকা", callback_data="show_slot_manager")])

    reply_markup = InlineKeyboardMarkup(buttons)

    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_start_live_slot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Prompts user to select which slot to start live in."""
    slots = get_all_slots()

    text = (
        "🚀 **লাইভ শুরু করার জন্য স্লট নির্বাচন করুন:**\n\n"
        "আপনি কোন স্লটে নতুন লাইভ চালু করতে চান?"
    )

    buttons = []
    for slot_id, slot in slots.items():
        st = stream_manager.get_slot_status(slot_id)
        status_tag = "🔴 [ইতিমধ্যে চলছে]" if st["is_running"] else "⚪ [ফাঁকা]"
        buttons.append([
            InlineKeyboardButton(f"{slot.get('name', slot_id)} {status_tag}", callback_data=f"start_slot_flow_{slot_id}")
        ])

    buttons.append([InlineKeyboardButton("➕ নতুন স্লট তৈরি করে লাইভ করুন", callback_data="create_slot_action")])
    buttons.append([InlineKeyboardButton("🔙 মূল মেনু", callback_data="back_to_dashboard")])

    reply_markup = InlineKeyboardMarkup(buttons)

    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_video_selection_for_slot(update: Update, context: ContextTypes.DEFAULT_TYPE, slot_id: str, is_callback: bool = True):
    """Shows video list to stream in the chosen slot."""
    slot = get_slot(slot_id)
    if not slot.get("stream_key"):
        text = (
            f"⚠️ **[{slot.get('name', slot_id)}] স্লটে ইউটিউব স্ট্রিম কি সেট করা নেই!**\n\n"
            "লাইভ শুরু করার পূর্বে অনুগ্রহ করে এই স্লটের স্ট্রিম কি দিন।"
        )
        keyboard = [
            [InlineKeyboardButton("🔑 স্ট্রিম কি দিন", callback_data=f"edit_key_{slot_id}")],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data=f"manage_slot_{slot_id}")]
        ]
        if is_callback and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    videos = list_stock_videos()
    if not videos:
        text = (
            f"📁 **[{slot.get('name', slot_id)}] ভিডিও স্টক খালি!**\n\n"
            "বর্তমানে কোনো ভিডিও নেই।\n"
            "👉 আপনি চ্যাটে সরাসরি যেকোনো **গুগল ড্রাইভ লিংক** পাঠাতে পারেন (ফোল্ডারের সব .mp4 অটো ডাউনলোড হবে),\n"
            "কিংবা **ইউটিউব লিংক পেস্ট** করতে পারেন অথবা সরাসরি ভিডিও ফাইল সেন্ড করতে পারেন।"
        )
        keyboard = [
            [InlineKeyboardButton("🚗 ড্রাইভ থেকে ডাউনলোড", callback_data="prompt_drive_action")],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_to_dashboard")]
        ]
        if is_callback and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    text = (
        f"🎬 **[{slot.get('name', slot_id)}] স্লটে ভিডিও পছন্দ করুন:**\n\n"
        "👉 আপনি নিচের সব ভিডিও একসাথে একটানা ক্রমিক লুপে (24/7 Playlist Loop) চালাতে পারেন অথবা নির্দিষ্ট একটি ভিডিও নির্বাচন করতে পারেন:\n\n"
    )
    buttons = []

    # Option to loop ALL videos continuously
    buttons.append([InlineKeyboardButton(f"🔄 সকল ভিডিও লুপে চালান ({len(videos)}টি ফাইল Playlist)", callback_data=f"slot_pl_{slot_id}")])

    for i, vid in enumerate(videos):
        text += f"**{i+1}.** 🎬 `{vid['name']}` ({vid['size_str']} | {vid['duration_str']})\n"
        buttons.append([InlineKeyboardButton(f"▶️ {i+1}. {vid['name'][:24]}", callback_data=f"slot_vid_{slot_id}_{i}")])

    buttons.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="select_live_slot_menu")])
    reply_markup = InlineKeyboardMarkup(buttons)

    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_stock_videos(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Displays stock videos list."""
    videos = list_stock_videos()

    if not videos:
        text = (
            "📁 **ভিডিও স্টক খালি!**\n\n"
            "বর্তমানে `videos/` ফোল্ডারে কোনো ভিডিও নেই।\n\n"
            "👉 **ভিডিও যুক্ত করার উপায়:**\n"
            "১. চ্যাটে সরাসরি যেকোনো **YouTube বা ভিডিও লিংক পেস্ট করুন** (yt-dlp দিয়ে অটো ডাউনলোড হবে)।\n"
            "২. অথবা সরাসরি ভিডিও ফাইল এই চ্যাটে সেন্ড করুন।"
        )
        keyboard = [[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_to_dashboard")]]
        if is_callback and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    text = f"📁 **স্টকে থাকা ভিডিও তালিকা ({len(videos)}টি পাওয়া গেছে):**\n\n"
    buttons = []

    for i, vid in enumerate(videos):
        text += (
            f"**{i+1}.** 🎬 `{vid['name']}`\n"
            f"   └ 📦 সাইজ: `{vid['size_str']}` | ⏳ দৈর্ঘ্য: `{vid['duration_str']}`\n"
            f"   └ 📐 মূল রেশিও: `{vid['aspect_ratio']}`\n\n"
        )
        buttons.append([
            InlineKeyboardButton(f"🚀 {i+1}. লাইভ চালান", callback_data="select_live_slot_menu"),
            InlineKeyboardButton("🗑️ মুছুন", callback_data=f"delete_stock_vid_{i}")
        ])

    buttons.append([InlineKeyboardButton("🔙 ড্যাশবোর্ড", callback_data="back_to_dashboard")])
    reply_markup = InlineKeyboardMarkup(buttons)

    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_thumbnail_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Displays uploaded thumbnails."""
    thumbs = list_stock_thumbnails()
    if not thumbs:
        text = (
            "🖼️ **থাম্বনেইল গ্যালারি খালি!**\n\n"
            "বর্তমানে কোনো থাম্বনেইল সংরক্ষিত নেই।\n"
            "👉 যেকোনো থাম্বনেইল ছবি (.jpg, .png) সরাসরি এই চ্যাটে সেন্ড করলেই তা সংরক্ষিত হয়ে যাবে।"
        )
        keyboard = [[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_to_dashboard")]]
        if is_callback and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    text = f"🖼️ **সংরক্ষিত থাম্বনেইল তালিকা ({len(thumbs)}টি):**\n\n"
    buttons = []

    for i, th in enumerate(thumbs):
        text += f"**{i+1}.** 📸 `{th['name']}` ({th['size_str']}) - _{th['mtime']}_\n"
        buttons.append([InlineKeyboardButton(f"🖼️ {i+1}. {th['name'][:22]}", callback_data=f"view_thumb_{i}")])

    buttons.append([InlineKeyboardButton("🔙 ড্যাশবোর্ড", callback_data="back_to_dashboard")])
    reply_markup = InlineKeyboardMarkup(buttons)

    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all inline keyboard button presses."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    if not is_admin(user.id):
        await query.message.reply_text("⛔ আপনি অনুমোদিত নন।")
        return

    if data == "refresh_dashboard" or data == "back_to_dashboard":
        await send_dashboard(update, context, is_callback=True)

    elif data == "show_slot_manager":
        await show_slot_manager(update, context, is_callback=True)

    elif data == "select_live_slot_menu":
        await show_start_live_slot_selection(update, context, is_callback=True)

    elif data == "list_stock_action":
        await show_stock_videos(update, context, is_callback=True)

    elif data == "show_thumb_gallery":
        await show_thumbnail_gallery(update, context, is_callback=True)

    elif data == "create_slot_action":
        new_slot_id = create_new_slot()
        new_slot = get_slot(new_slot_id)
        await query.edit_message_text(
            f"✅ **নতুন স্লট তৈরি হয়েছে: [{new_slot.get('name')}]**\n\nএখন এই স্লটের স্ট্রিম কি ও সেটিংস কনফিগার করুন।",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ এই স্লট কনফিগার করুন", callback_data=f"manage_slot_{new_slot_id}")],
                [InlineKeyboardButton("🔙 ড্যাশবোর্ড", callback_data="back_to_dashboard")]
            ]),
            parse_mode="Markdown"
        )

    elif data.startswith("manage_slot_"):
        slot_id = data.replace("manage_slot_", "")
        await show_slot_detail(update, context, slot_id, is_callback=True)

    elif data.startswith("start_slot_flow_"):
        slot_id = data.replace("start_slot_flow_", "")
        await show_video_selection_for_slot(update, context, slot_id, is_callback=True)

    elif data == "prompt_drive_action":
        await prompt_drive_download(update, context, is_callback=True)

    elif data.startswith("slot_pl_"):
        slot_id = data.replace("slot_pl_", "")
        slot = get_slot(slot_id)
        videos = list_stock_videos()
        text = (
            f"🔄 **স্লট:** `{slot.get('name', slot_id)}`\n"
            f"📦 **মোড:** সকল ভিডিও ক্রমিক লুপ (24/7 Playlist Loop)\n"
            f"📊 **ভিডিও সংখ্যা:** {len(videos)}টি .mp4 ফাইল\n\n"
            "একটি ভিডিও শেষ হলে পরবর্তী ভিডিও চলবে এবং সব শেষ হলে স্বয়ংক্রিয়ভাবে প্রথম থেকে একটানা লুপ হতে থাকবে।\n\n"
            "❓ **আপনি এটি কোন ফরম্যাটে লাইভ চালাতে চান?**"
        )
        keyboard = [
            [InlineKeyboardButton("🖥️ লং ভিডিও (16:9 Landscape)", callback_data=f"run_pl_{slot_id}_long")],
            [InlineKeyboardButton("📱 শর্টস ভিডিও (9:16 Vertical)", callback_data=f"run_pl_{slot_id}_shorts")],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data=f"start_slot_flow_{slot_id}")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("run_pl_"):
        parts = data.split("_")
        slot_id = f"{parts[2]}_{parts[3]}"
        mode = parts[4]

        slot = get_slot(slot_id)
        stream_key = slot.get("stream_key", "")

        await query.edit_message_text(f"⏳ [{slot.get('name')}] সকল ভিডিও লুপে লাইভ শুরু হচ্ছে...")
        success, msg = stream_manager.start_stream(PLAYLIST_LOOP_ALL, mode=mode, stream_key=stream_key, slot_id=slot_id)

        if success:
            api_note = ""
            if is_youtube_api_authenticated():
                title = slot.get("title", "")
                desc = slot.get("description", "")
                thumb = slot.get("thumbnail", "")
                if title:
                    update_live_broadcast_metadata(title, desc)
                if thumb and Path(thumb).exists():
                    update_live_broadcast_thumbnail(thumb)
                api_note = "\n🌐 *ইউটিউব স্টুডিওতেও টাইটেল ও থাম্বনেইল সিঙ্ক করা হয়েছে।*\n"

            await query.edit_message_text(
                f"{msg}\n{api_note}\n📊 স্ট্যাটাস দেখতে নিচের বাটনে চাপুন:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 লাইভ ড্যাশবোর্ড", callback_data="refresh_dashboard")],
                    [InlineKeyboardButton("⚙️ স্লট ম্যানেজার", callback_data="show_slot_manager")]
                ]),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"❌ লাইভ শুরু ব্যর্থ: {msg}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 পুনরায় চেষ্টা করুন", callback_data=f"start_slot_flow_{slot_id}")]
                ])
            )

    elif data.startswith("slot_vid_"):
        parts = data.split("_")
        slot_id = f"{parts[2]}_{parts[3]}"
        vid_index = int(parts[4])
        video = get_video_by_index(vid_index)

        if not video:
            await query.edit_message_text("❌ ভিডিওটি পাওয়া যায়নি।")
            return

        slot = get_slot(slot_id)
        text = (
            f"🎬 **স্লট:** `{slot.get('name', slot_id)}`\n"
            f"📦 **ভিডিও:** `{video['name']}` ({video['size_str']})\n"
            f"📝 **টাইটেল:** `{slot.get('title', 'N/A')}`\n\n"
            "❓ **আপনি এটি কোন ফরম্যাটে লাইভ চালাতে চান?**"
        )
        keyboard = [
            [InlineKeyboardButton("🖥️ লং ভিডিও (16:9 Landscape)", callback_data=f"run_slot_{slot_id}_{vid_index}_long")],
            [InlineKeyboardButton("📱 শর্টস ভিডিও (9:16 Vertical)", callback_data=f"run_slot_{slot_id}_{vid_index}_shorts")],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data=f"start_slot_flow_{slot_id}")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("run_slot_"):
        parts = data.split("_")
        slot_id = f"{parts[2]}_{parts[3]}"
        vid_index = int(parts[4])
        mode = parts[5]

        video = get_video_by_index(vid_index)
        if not video:
            await query.edit_message_text("❌ ভিডিও পাওয়া যায়নি।")
            return

        slot = get_slot(slot_id)
        stream_key = slot.get("stream_key", "")

        await query.edit_message_text(f"⏳ [{slot.get('name')}] লাইভ শুরু হচ্ছে...")
        success, msg = stream_manager.start_stream(video["path"], mode=mode, stream_key=stream_key, slot_id=slot_id)

        if success:
            api_note = ""
            if is_youtube_api_authenticated():
                title = slot.get("title", "")
                desc = slot.get("description", "")
                thumb = slot.get("thumbnail", "")
                if title:
                    update_live_broadcast_metadata(title, desc)
                if thumb and Path(thumb).exists():
                    update_live_broadcast_thumbnail(thumb)
                api_note = "\n🌐 *ইউটিউব স্টুডিওতেও টাইটেল ও থাম্বনেইল সিঙ্ক করা হয়েছে।*\n"

            await query.edit_message_text(
                f"{msg}\n{api_note}\n📊 স্ট্যাটাস দেখতে নিচের বাটনে চাপুন:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 লাইভ ড্যাশবোর্ড", callback_data="refresh_dashboard")],
                    [InlineKeyboardButton("⚙️ স্লট ম্যানেজার", callback_data="show_slot_manager")]
                ]),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"❌ লাইভ শুরু ব্যর্থ: {msg}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 পুনরায় চেষ্টা করুন", callback_data=f"start_slot_flow_{slot_id}")]
                ])
            )

    elif data.startswith("quick_stop_"):
        slot_id = data.replace("quick_stop_", "")
        success, msg = stream_manager.stop_stream(slot_id)
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 ড্যাশবোর্ড দেখুন", callback_data="refresh_dashboard")]
        ]))

    elif data == "confirm_stop_all":
        keyboard = [
            [
                InlineKeyboardButton("✅ হ্যাঁ, সব লাইভ বন্ধ করুন", callback_data="do_stop_all"),
                InlineKeyboardButton("❌ বাতিল", callback_data="refresh_dashboard")
            ]
        ]
        await query.edit_message_text("⚠️ **আপনি কি চলমান সবকটি লাইভ স্ট্রিম একসাথে বন্ধ করতে চান?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "do_stop_all":
        results = stream_manager.stop_all_streams()
        count = len(results)
        await query.edit_message_text(
            f"⏹️ **মোট {count}টি লাইভ স্ট্রিম সফলভাবে বন্ধ করা হয়েছে।**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 ড্যাশবোর্ড", callback_data="refresh_dashboard")]
            ]),
            parse_mode="Markdown"
        )

    elif data.startswith("edit_key_"):
        slot_id = data.replace("edit_key_", "")
        context.user_data["waiting_for"] = f"key_{slot_id}"
        slot = get_slot(slot_id)
        text = (
            f"🔑 **[{slot.get('name')}]-এর জন্য YouTube Stream Key লিখুন:**\n\n"
            "ইউটিউব স্টুডিও থেকে কপি করা গোপন স্ট্রিম কি-টি এখানে সেন্ড করুন।"
        )
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data=f"manage_slot_{slot_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("edit_title_"):
        slot_id = data.replace("edit_title_", "")
        context.user_data["waiting_for"] = f"title_{slot_id}"
        slot = get_slot(slot_id)
        text = f"📝 **[{slot.get('name')}]-এর জন্য লাইভ টাইটেল (Title) লিখে পাঠান:**"
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data=f"manage_slot_{slot_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("edit_desc_"):
        slot_id = data.replace("edit_desc_", "")
        context.user_data["waiting_for"] = f"desc_{slot_id}"
        slot = get_slot(slot_id)
        text = f"📄 **[{slot.get('name')}]-এর জন্য লাইভ ডেসক্রিপশন (Description) লিখে পাঠান:**"
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data=f"manage_slot_{slot_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("edit_thumb_"):
        slot_id = data.replace("edit_thumb_", "")
        context.user_data["waiting_for"] = f"thumb_{slot_id}"
        slot = get_slot(slot_id)
        text = (
            f"🖼️ **[{slot.get('name')}]-এর জন্য থাম্বনেইল ছবি পাঠান:**\n\n"
            "যেকোনো JPG/PNG থাম্বনেইল ছবি সরাসরি এই চ্যাটে সেন্ড করুন।"
        )
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data=f"manage_slot_{slot_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("edit_slotname_"):
        slot_id = data.replace("edit_slotname_", "")
        context.user_data["waiting_for"] = f"slotname_{slot_id}"
        text = "✏️ **স্লটের নতুন নাম লিখে পাঠান:** (যেমন: Gaming Live, Channel 2 Music)"
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data=f"manage_slot_{slot_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("delete_slot_"):
        slot_id = data.replace("delete_slot_", "")
        ok = delete_slot(slot_id)
        if ok:
            await query.edit_message_text("🗑️ স্লটটি সফলভাবে মুছে ফেলা হয়েছে।", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 স্লট তালিকা", callback_data="show_slot_manager")]
            ]))
        else:
            await query.edit_message_text("⚠️ শেষ স্লটটি মোছা সম্ভব নয় (কমপক্ষে ১টি স্লট থাকতে হবে)।", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 স্লট তালিকা", callback_data="show_slot_manager")]
            ]))

    elif data == "prompt_set_node_name":
        context.user_data["waiting_for"] = "set_node_name"
        text = (
            "🖥️ **এই RDP / সার্ভারের নোড নাম দিন:**\n\n"
            "উদাহরণ: `RDP-1 (Main Server)` অথবা `VPS-USA-1`"
        )
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data="show_slot_manager")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("delete_stock_vid_"):
        idx = int(data.replace("delete_stock_vid_", ""))
        delete_video_by_index(idx)
        await show_stock_videos(update, context, is_callback=True)

    elif data.startswith("view_thumb_"):
        index = int(data.split("_")[2])
        thumbs = list_stock_thumbnails()
        if 0 <= index < len(thumbs):
            th = thumbs[index]
            active_id = get_active_slot_id()
            update_slot_field(active_id, "thumbnail", th["path"])
            await query.message.reply_photo(
                photo=open(th["path"], "rb"),
                caption=f"📸 **থাম্বনেইল:** `{th['name']}`\n\n✅ এটি সক্রিয় স্লটে থাম্বনেইল হিসেবে সেট করা হয়েছে!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 লাইভ শুরু করুন", callback_data="select_live_slot_menu")],
                    [InlineKeyboardButton("🔙 থাম্বনেইল তালিকা", callback_data="show_thumb_gallery")]
                ]),
                parse_mode="Markdown"
            )

async def prompt_drive_download(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False):
    """Prompts user to send a Google Drive link."""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["waiting_for"] = "drive_url"
    text = (
        "🚗 **গুগল ড্রাইভ থেকে .mp4 ভিডিও ডাউনলোড ও ২৪/৭ লাইভ**\n\n"
        "📥 আপনার গুগল ড্রাইভের **ফোল্ডার বা ফাইলের লিংকটি** এখানে লিখে পাঠান।\n\n"
        "📌 **ফিচার ও সুবিধা:**\n"
        "• ফোল্ডারে থাকা ৫০-৬০+ যতগুলো .mp4 ভিডিও থাকবে সব স্বয়ংক্রিয়ভাবে ডাউনলোড হয়ে লোকাল ভিডিও স্টকে জমা হবে।\n"
        "• অন্য কোনো এক্সটেনশন (.txt, .jpg, .zip ইত্যাদি) বাদ দিয়ে শুধু .mp4 ভিডিওগুলোই সংরক্ষণ করা হবে।\n"
        "• ডাউনলোড শেষ হওয়া মাত্রই এক ক্লিকে সবগুলো ভিডিও **২৪/৭ লুপ প্লেলিস্ট (24/7 Loop Playlist)** হিসেবে লাইভ চালাতে পারবেন!\n"
        "• একটি ভিডিও শেষ হলে পরেরটি চলবে এবং সব শেষ হলে স্বয়ংক্রিয়ভাবে আবার ১ম ভিডিও থেকে চলতে থাকবে লুপে।\n\n"
        "⚠️ **জরুরি বিষয়:** নিশ্চিত করুন ড্রাইভ ফোল্ডারের শেয়ার পারমিশন **'Anyone with the link can view'** করা আছে।"
    )
    keyboard = [[InlineKeyboardButton("🔙 ড্যাশবোর্ড", callback_data="back_to_dashboard")]]
    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_drive_download(update: Update, url: str):
    """Downloads .mp4 video files from Google Drive link asynchronously."""
    clean_url = extract_drive_url(url) or url
    progress_msg = await update.message.reply_text(
        f"📥 **গুগল ড্রাইভ লিংক শনাক্ত হয়েছে!**\n"
        f"🔗 `{clean_url}`\n\n"
        f"⏳ **ড্রাইভ থেকে .mp4 ভিডিওগুলো ডাউনলোড ও প্রসেসিং হচ্ছে...**\n"
        f"_(ফাইল সংখ্যা ও ইন্টারনেটের গতির ওপর নির্ভর করে কিছুটা সময় লাগতে পারে)_",
        parse_mode="Markdown"
    )

    loop = asyncio.get_running_loop()
    success, res = await loop.run_in_executor(None, download_from_google_drive, clean_url)

    if success:
        count = res["count"]
        size_str = res["total_size_str"]
        files = res["files"]

        file_preview = ""
        for i, f in enumerate(files[:6]):
            file_preview += f"• `{f['name']}` ({format_size(f['size'])})\n"
        if count > 6:
            file_preview += f"• _...আরও {count - 6}টি .mp4 ফাইল_\n"

        keyboard = [
            [InlineKeyboardButton("🔄 সব ভিডিও লুপে লাইভে চালান (24/7 Loop)", callback_data="select_live_slot_menu")],
            [InlineKeyboardButton("📁 ভিডিও স্টক দেখুন", callback_data="list_stock_action")],
            [InlineKeyboardButton("📊 লাইভ ড্যাশবোর্ড", callback_data="refresh_dashboard")]
        ]

        await progress_msg.edit_text(
            f"✅ **ড্রাইভ থেকে সফলভাবে মোট {count}টি .mp4 ভিডিও ডাউনলোড ও সেভ হয়েছে!**\n\n"
            f"📦 **মোট সাইজ:** `{size_str}`\n"
            f"🎬 **ডাউনলোডকৃত ভিডিও তালিকা:**\n{file_preview}\n"
            f"👉 আপনি এখন সরাসরি যেকোনো স্লটে এই ভিডিওগুলো ২৪/৭ লুপে লাইভ চালাতে পারেন।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await progress_msg.edit_text(
            f"❌ **ড্রাইভ ডাউনলোড ব্যর্থ হয়েছে!**\n\n"
            f"কারণ: {res.get('error', 'অজানা ত্রুটি')}\n\n"
            f"💡 নিশ্চিত করুন ফোল্ডার বা ফাইলের লিংকটির শেয়ার পারমিশন 'Anyone with the link can view' সেট করা আছে এবং এতে .mp4 ভিডিও আছে।",
            parse_mode="Markdown"
        )

async def handle_url_download(update: Update, url: str):
    """Downloads video via yt-dlp asynchronously and offers instant live stream action."""
    progress_msg = await update.message.reply_text(
        f"📥 **ভিডিও লিংক শনাক্ত হয়েছে!**\n"
        f"🔗 `{url}`\n\n"
        f"⏳ **yt-dlp দিয়ে সর্বোচ্চ কোয়ালিটিতে ভিডিও ডাউনলোড শুরু হচ্ছে...**\n"
        f"_(ভিডিও সাইজের ওপর নির্ভর করে ২০-৬০ সেকেন্ড সময় লাগতে পারে)_",
        parse_mode="Markdown"
    )

    loop = asyncio.get_running_loop()
    success, res = await loop.run_in_executor(None, download_video_from_url, url)

    if success:
        file_name = res["file_name"]
        keyboard = [
            [InlineKeyboardButton("🚀 সরাসরি লাইভে চালান", callback_data="select_live_slot_menu")],
            [InlineKeyboardButton("📁 ভিডিও স্টক দেখুন", callback_data="list_stock_action")],
            [InlineKeyboardButton("📊 লাইভ ড্যাশবোর্ড", callback_data="refresh_dashboard")]
        ]
        await progress_msg.edit_text(
            f"✅ **ভিডিও সফলভাবে ডাউনলোড ও সেভ হয়েছে!**\n\n"
            f"🎬 **টাইটেল:** `{res['title']}`\n"
            f"📂 **ফাইল:** `{file_name}`\n"
            f"⏳ **দৈর্ঘ্য:** `{res['duration_str']}` | 📦 **সাইজ:** `{res['size_str']}`\n\n"
            "👉 এখন আপনি যেকোনো স্লটে এই ভিডিওটি ২৪/৭ লাইভ চালাতে পারেন।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await progress_msg.edit_text(
            f"❌ **ভিডিও ডাউনলোড ব্যর্থ হয়েছে!**\n\n"
            f"কারণ: {res.get('error', 'অজানা ত্রুটি')}\n\n"
            f"💡 লিংকটি সঠিক ও ভিডিওটি পাবলিক কিনা চেক করুন।",
            parse_mode="Markdown"
        )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages, interactive settings, and auto URL download."""
    text = update.message.text.strip()
    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text("⛔ আপনি অনুমোদিত নন।")
        return

    # Check if user sent a Google Drive URL
    if is_drive_url(text):
        url = extract_drive_url(text) or text
        await handle_drive_download(update, url)
        return

    # Check if user sent a video URL (YouTube, Shorts, etc.)
    if is_video_url(text) and not context.user_data.get("waiting_for"):
        url = extract_url(text)
        await handle_url_download(update, url)
        return

    waiting_state = context.user_data.get("waiting_for")

    if waiting_state:
        context.user_data.pop("waiting_for", None)

        if waiting_state == "drive_url":
            if is_drive_url(text):
                url = extract_drive_url(text) or text
                await handle_drive_download(update, url)
            else:
                await update.message.reply_text("❌ এটি গুগল ড্রাইভের লিংক নয়। অনুগ্রহ করে একটি সঠিক গুগল ড্রাইভ ফোল্ডার বা ফাইলের লিংক পাঠান।")
            return

        if waiting_state == "set_node_name":
            set_node_id(text)
            await update.message.reply_text(f"✅ **নোড নাম আপডেট হয়েছে:** `{text}`", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎛️ স্লট ম্যানেজার", callback_data="show_slot_manager")]
            ]), parse_mode="Markdown")
            return

        if waiting_state.startswith("key_"):
            slot_id = waiting_state.replace("key_", "")
            update_slot_field(slot_id, "stream_key", text)
            masked = f"{text[:4]}****{text[-4:]}" if len(text) > 8 else text
            slot = get_slot(slot_id)
            await update.message.reply_text(
                f"✅ **[{slot.get('name')}] স্ট্রিম কি সংরক্ষিত হয়েছে!**\n🔑 `{masked}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 লাইভ চালু করুন", callback_data=f"start_slot_flow_{slot_id}")],
                    [InlineKeyboardButton("⚙️ স্লট সেটিংস", callback_data=f"manage_slot_{slot_id}")]
                ]),
                parse_mode="Markdown"
            )
            return

        if waiting_state.startswith("title_"):
            slot_id = waiting_state.replace("title_", "")
            update_slot_field(slot_id, "title", text)
            slot = get_slot(slot_id)
            
            api_res = ""
            if is_youtube_api_authenticated():
                ok, msg = update_live_broadcast_metadata(text, slot.get("description", ""))
                api_res = f"\n🌐 {msg}"

            await update.message.reply_text(
                f"✅ **[{slot.get('name')}] টাইটেল আপডেট হয়েছে!**\n📝 `{text}`{api_res}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚙️ স্লট সেটিংস", callback_data=f"manage_slot_{slot_id}")]
                ]),
                parse_mode="Markdown"
            )
            return

        if waiting_state.startswith("desc_"):
            slot_id = waiting_state.replace("desc_", "")
            update_slot_field(slot_id, "description", text)
            slot = get_slot(slot_id)
            
            api_res = ""
            if is_youtube_api_authenticated():
                ok, msg = update_live_broadcast_metadata(slot.get("title", ""), text)
                api_res = f"\n🌐 {msg}"

            await update.message.reply_text(
                f"✅ **[{slot.get('name')}] ডেসক্রিপশন আপডেট হয়েছে!**{api_res}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚙️ স্লট সেটিংস", callback_data=f"manage_slot_{slot_id}")]
                ]),
                parse_mode="Markdown"
            )
            return

        if waiting_state.startswith("slotname_"):
            slot_id = waiting_state.replace("slotname_", "")
            update_slot_field(slot_id, "name", text)
            await update.message.reply_text(
                f"✅ **স্লটের নাম পরিবর্তন হয়েছে:** `{text}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚙️ স্লট সেটিংস", callback_data=f"manage_slot_{slot_id}")]
                ]),
                parse_mode="Markdown"
            )
            return

    # Reply Keyboard Actions
    if text == "📊 মাল্টি-লাইভ ড্যাশবোর্ড":
        await send_dashboard(update, context)

    elif text == "🚀 লাইভ শুরু করুন":
        await show_start_live_slot_selection(update, context)

    elif text == "🎛️ স্লট ম্যানেজার":
        await show_slot_manager(update, context)

    elif text == "📁 ভিডিও স্টক":
        await show_stock_videos(update, context)

    elif text == "🚗 ড্রাইভ থেকে ডাউনলোড":
        await prompt_drive_download(update, context)

    elif text == "⚙️ ইউটিউব ও স্লট সেটআপ":
        active_id = get_active_slot_id()
        await show_slot_detail(update, context, active_id, is_callback=False)

    elif text == "🖼️ থাম্বনেইল গ্যালারি":
        await show_thumbnail_gallery(update, context)

    elif text == "⏹️ লাইভ বন্ধ করুন":
        all_st = stream_manager.get_all_status()
        if all_st["active_streams_count"] > 0:
            await send_dashboard(update, context)
        else:
            await update.message.reply_text("⚪ বর্তমানে কোনো লাইভ স্ট্রিম চলছে না।")

    elif text == "📜 হিস্ট্রি":
        history = stream_manager.get_history()
        if not history:
            await update.message.reply_text("📜 কোনো পূর্ববর্তী লাইভ হিস্ট্রি পাওয়া যায়নি।")
            return

        msg = "📜 **সর্বশেষ লাইভ স্ট্রিম হিস্ট্রি:**\n\n"
        for i, h in enumerate(history[:10]):
            msg += (
                f"**{i+1}.** 🎬 `{h.get('video_name')}`\n"
                f"   └ 🏷️ স্লট: `{h.get('slot_name', 'Slot')}` ({h.get('mode')})\n"
                f"   └ ⏳ সময়কাল: `{h.get('duration')}` | 📅 `{h.get('start_time')}`\n\n"
            )
        await update.message.reply_text(msg, parse_mode="Markdown")

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /download <url> handler."""
    user = update.effective_user
    if not is_admin(user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "❌ অনুগ্রহ করে ভিডিও লিংক দিন।\n"
            "উদাহরণ: `/download https://www.youtube.com/watch?v=...`",
            parse_mode="Markdown"
        )
        return

    url = context.args[0].strip()
    await handle_url_download(update, url)

async def handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles image/thumbnail uploads sent via Telegram."""
    user = update.effective_user
    if not is_admin(user.id):
        return

    message = update.message
    file_obj = None
    file_name = f"thumb_{int(datetime.now().timestamp())}.jpg"

    if message.photo:
        file_obj = await message.photo[-1].get_file()
    elif message.document:
        ext = Path(message.document.file_name or "").suffix.lower()
        if ext in SUPPORTED_IMAGE_EXTENSIONS:
            file_obj = await message.document.get_file()
            file_name = message.document.file_name or f"thumb_{int(datetime.now().timestamp())}{ext}"

    if not file_obj:
        return

    clean_name = "".join(c for c in file_name if c.isalnum() or c in "._- ")
    target_path = THUMBNAILS_DIR / clean_name

    progress_msg = await message.reply_text("⏳ **থাম্বনেইল আপলোড ও সংরক্ষণ হচ্ছে...**", parse_mode="Markdown")

    try:
        await file_obj.download_to_drive(str(target_path))
        active_id = get_active_slot_id()
        update_slot_field(active_id, "thumbnail", str(target_path))

        api_note = ""
        if is_youtube_api_authenticated():
            ok, msg = update_live_broadcast_thumbnail(str(target_path))
            api_note = f"\n🌐 {msg}"

        slots = get_all_slots()
        buttons = []
        for slot_id, slot in slots.items():
            buttons.append([InlineKeyboardButton(f"🖼️ [{slot.get('name')}]-এ সেট করুন", callback_data=f"assign_thumb_{slot_id}_{clean_name}")])

        buttons.append([InlineKeyboardButton("📊 ড্যাশবোর্ড", callback_data="refresh_dashboard")])

        await progress_msg.edit_text(
            f"✅ **থাম্বনেইল সফলভাবে সংরক্ষিত হয়েছে!**\n\n"
            f"📸 **ফাইল:** `{clean_name}`\n"
            f"📦 **সাইজ:** `{format_size(target_path.stat().st_size)}`{api_note}\n\n"
            "👉 আপনি এটি কোন স্লটের থাম্বনেইল হিসেবে সেট করতে চান?",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
    except Exception as e:
        await progress_msg.edit_text(f"❌ থাম্বনেইল সেভ এরর: {str(e)}")

async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and downloads video files sent via Telegram."""
    user = update.effective_user
    if not is_admin(user.id):
        return

    message = update.message
    file_obj = None
    file_name = "uploaded_video.mp4"

    if message.video:
        file_obj = await message.video.get_file()
        file_name = message.video.file_name or f"video_{message.video.file_unique_id}.mp4"
    elif message.document:
        ext = Path(message.document.file_name or "").suffix.lower()
        if ext in SUPPORTED_EXTENSIONS:
            file_obj = await message.document.get_file()
            file_name = message.document.file_name or f"video_{message.document.file_unique_id}.mp4"
        elif ext in SUPPORTED_IMAGE_EXTENSIONS:
            await handle_photo_upload(update, context)
            return
        elif message.document.file_name and "cookies" in message.document.file_name.lower():
            file_obj = await message.document.get_file()
            cookies_dest = config.BASE_DIR / "cookies.txt"
            await file_obj.download_to_drive(str(cookies_dest))
            await message.reply_text("✅ **cookies.txt সফলভাবে সংরক্ষিত হয়েছে!**\nএখন ইউটিউব ডাউনলোড সর্বোচ্চ গতি ও স্থিতিশীলতায় কাজ করবে।", parse_mode="Markdown")
            return
        else:
            await message.reply_text(f"❌ সমর্থিত নয় এমন ফাইল ফরম্যাট।")
            return

    if not file_obj:
        return

    clean_name = "".join(c for c in file_name if c.isalnum() or c in "._- ")
    target_path = VIDEOS_DIR / clean_name

    progress_msg = await message.reply_text(f"⏳ **ভিডিওটি ডাউনলোড হচ্ছে...**\n📂 ফাইল: `{clean_name}`", parse_mode="Markdown")

    try:
        await file_obj.download_to_drive(str(target_path))
        file_size = format_size(target_path.stat().st_size)

        keyboard = [
            [InlineKeyboardButton("🚀 সরাসরি লাইভে চালান", callback_data="select_live_slot_menu")],
            [InlineKeyboardButton("📁 ভিডিও স্টক দেখুন", callback_data="list_stock_action")]
        ]

        await progress_msg.edit_text(
            f"✅ **ভিডিও সফলভাবে সংরক্ষিত হয়েছে!**\n\n"
            f"🎬 **ফাইল:** `{clean_name}`\n"
            f"📦 **সাইজ:** `{file_size}`\n\n"
            "👉 এখন আপনি যেকোনো স্লটে এই ভিডিওটি লাইভ চালাতে পারেন।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        await progress_msg.edit_text(f"❌ ভিডিও সেভ এরর: {str(e)}")

def setup_telegram_bot() -> Application:
    """Configures the telegram bot application."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing in config!")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CommandHandler("dashboard", send_dashboard))
    app.add_handler(CommandHandler("slots", show_slot_manager))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("drive", prompt_drive_download))

    app.add_handler(CallbackQueryHandler(handle_callback))

    # Media & Message Handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_upload))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    return app
