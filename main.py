import os
import telebot
import requests
import time
import threading
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
import logging
import sys
# ╔══════════════════════════════════════════════════════════════════╗
# ║  CREATOR: TARIKUL ISLAM
# ║  TELEGRAN: https://t.me/paglu_dev
# ║  PERSONAL TELEGRAM: https://t.me/itzpaglu
# ╚══════════════════════════════════════════════════════════════════╝

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found! Please set your bot token in environment variables.")
    sys.exit(1)

REQUIRED_CHANNELS = ["@maybesifatx69"]
GROUP_JOIN_LINK = "https://t.me/maybesifatx69"
OWNER_ID = 8438269386
OWNER_USERNAME = "@MaybeSifu"
BOT_VERSION = "2.0"

bot = telebot.TeleBot(BOT_TOKEN)
like_tracker = {}   # in-memory cache
bot_start_time = datetime.utcnow()

# Flask app for webhook
app = Flask(__name__)

# === DATA RESET ===

def reset_limits():
    """Daily reset of usage tracker (in-memory only)."""
    while True:
        try:
            now_utc = datetime.utcnow()
            next_reset = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            sleep_seconds = (next_reset - now_utc).total_seconds()
            time.sleep(sleep_seconds)
            like_tracker.clear()
            logger.info("✅ Daily limits reset at 00:00 UTC (in-memory).")
        except Exception as e:
            logger.error(f"Error in reset_limits thread: {e}")


# === UTILS ===

def is_user_in_channel(user_id):
    try:
        for channel in REQUIRED_CHANNELS:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        logger.error(f"Join check failed: {e}")
        return False


def call_api(region, uid):
    url = f"https://your-free-fire-like-api-domain/like?uid={uid}&server_name={region}"
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            return {"⚠️Invalid": " Maximum likes reached for today. Please try again tomorrow."}
        return response.json()
    except requests.exceptions.RequestException:
        return {"error": "API Failed. Please try again later."}
    except ValueError:
        return {"error": "Invalid JSON response."}


def get_user_limit(user_id):
    if user_id == OWNER_ID:
        return 999999999
    return 1


def get_uptime():
    delta = datetime.utcnow() - bot_start_time
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def get_user_stats(user_id):
    usage = like_tracker.get(user_id, {"used": 0, "last_used": datetime.utcnow() - timedelta(days=1)})
    limit = get_user_limit(user_id)
    used = usage.get("used", 0)
    remaining = max(0, limit - used)
    return used, remaining, limit


def build_join_markup():
    markup = InlineKeyboardMarkup()
    for channel in REQUIRED_CHANNELS:
        markup.add(InlineKeyboardButton(f"📢 Join {channel}", url=f"https://t.me/{channel.strip('@')}"))
    return markup


# Start background thread
threading.Thread(target=reset_limits, daemon=True).start()

# === FLASK ROUTES ===

@app.route('/')
def home():
    return jsonify({
        'status': 'Bot is running',
        'bot': 'Free Fire Likes Bot',
        'version': BOT_VERSION,
        'uptime': get_uptime(),
        'health': 'OK'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'uptime': get_uptime()}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500


# === TELEGRAM COMMANDS ===

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Player"

    if not is_user_in_channel(user_id):
        markup = build_join_markup()
        text = (
            "╔══════════════════════╗\n"
            "║   🔒 ACCESS REQUIRED  ║\n"
            "╚══════════════════════╝\n\n"
            f"Hey *{first_name}!* 👋\n\n"
            "To unlock this bot, you must join our official channel(s) first.\n\n"
            "📢 *Tap the button below to join, then send* /start *again.*"
        )
        bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")
        return

    if user_id not in like_tracker:
        like_tracker[user_id] = {"used": 0, "last_used": datetime.utcnow() - timedelta(days=1)}

    used, remaining, limit = get_user_stats(user_id)
    limit_display = "Unlimited ♾️" if limit > 1000 else str(remaining)

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📖 Help", callback_data="help"),
        InlineKeyboardButton("📊 My Stats", callback_data="stats"),
        InlineKeyboardButton("🏓 Ping", callback_data="ping"),
        InlineKeyboardButton("💬 Support", url=f"https://t.me/{OWNER_USERNAME.strip('@')}")
    )

    welcome_text = (
        "╔══════════════════════════╗\n"
        "║  🔥 FREE FIRE LIKES BOT  ║\n"
        f"║       Version {BOT_VERSION}         ║\n"
        "╚══════════════════════════╝\n\n"
        f"✅ Welcome back, *{first_name}!*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Your Status Today:*\n"
        f"  • Requests Used: `{used}`\n"
        f"  • Remaining: `{limit_display}`\n"
        f"  • Reset: `Every 00:00 UTC`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎮 *How to use:*\n"
        "Send `/like <region> <uid>` in a group\n\n"
        "📌 *Example:* `/like ind 123456789`\n\n"
        f"👑 *Support:* {OWNER_USERNAME}"
    )

    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")


@bot.message_handler(commands=['ping'])
def ping_command(message):
    start = time.time()
    sent = bot.reply_to(message, "🏓 Pinging...")
    latency = round((time.time() - start) * 1000)

    ping_text = (
        "╔══════════════════════╗\n"
        "║     🏓 PONG!          ║\n"
        "╚══════════════════════╝\n\n"
        f"⚡ *Latency:* `{latency}ms`\n"
        f"⏱️ *Uptime:* `{get_uptime()}`\n"
        f"🟢 *Status:* `Online & Running`\n"
        f"🤖 *Bot Version:* `v{BOT_VERSION}`"
    )

    bot.edit_message_text(
        chat_id=sent.chat.id,
        message_id=sent.message_id,
        text=ping_text,
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['status'])
def status_command(message):
    user_id = message.from_user.id

    if not is_user_in_channel(user_id):
        markup = build_join_markup()
        bot.reply_to(message, "❌ You must join our channels to use this command.", reply_markup=markup, parse_mode="Markdown")
        return

    used, remaining, limit = get_user_stats(user_id)
    limit_display = "Unlimited ♾️" if limit > 1000 else str(limit)
    remaining_display = "Unlimited ♾️" if limit > 1000 else str(remaining)

    now_utc = datetime.utcnow()
    next_reset = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    time_left = next_reset - now_utc
    hours_left, rem = divmod(int(time_left.total_seconds()), 3600)
    mins_left = rem // 60

    bar_total = 10
    if limit > 1000:
        filled = bar_total
    else:
        filled = max(0, bar_total - int((used / limit) * bar_total)) if limit > 0 else bar_total
    bar = "🟩" * filled + "🟥" * (bar_total - filled)

    status_text = (
        "╔══════════════════════════╗\n"
        "║    📊 YOUR DAILY STATUS   ║\n"
        "╚══════════════════════════╝\n\n"
        f"👤 *User ID:* `{user_id}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Daily Limit:* `{limit_display}`\n"
        f"✅ *Used Today:* `{used}`\n"
        f"🎯 *Remaining:* `{remaining_display}`\n\n"
        f"*Usage Bar:*\n{bar}\n\n"
        f"⏰ *Resets in:* `{hours_left}h {mins_left}m`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 *Support:* {OWNER_USERNAME}"
    )

    bot.reply_to(message, status_text, parse_mode="Markdown")


@bot.message_handler(commands=['like'])
def handle_like(message):
    user_id = message.from_user.id
    args = message.text.split()

    if message.chat.type == "private" and message.from_user.id != OWNER_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔗 Join Official Group", url=GROUP_JOIN_LINK))
        text = (
            "╔══════════════════════╗\n"
            "║   ⚠️ GROUP ONLY CMD   ║\n"
            "╚══════════════════════╝\n\n"
            "This command only works in groups.\n\n"
            "👇 *Join our official group to use it:*"
        )
        bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")
        return

    if not is_user_in_channel(user_id):
        markup = build_join_markup()
        bot.reply_to(message, "❌ *You must join all our channels first!*\n\nTap below to join:", reply_markup=markup, parse_mode="Markdown")
        return

    if len(args) != 3:
        usage_text = (
            "╔══════════════════════╗\n"
            "║   ❌ WRONG FORMAT    ║\n"
            "╚══════════════════════╝\n\n"
            "📌 *Correct Usage:*\n"
            "`/like <region> <uid>`\n\n"
            "🌍 *Example:*\n"
            "`/like ind 123456789`\n\n"
            "📋 *Common Regions:*\n"
            "`ind` `bd` `sg` `br` `ru` `us`"
        )
        bot.reply_to(message, usage_text, parse_mode="Markdown")
        return

    region, uid = args[1], args[2]
    if not region.isalpha() or not uid.isdigit():
        bot.reply_to(message, "⚠️ *Invalid input!*\n\nRegion must be letters only and UID must be numbers only.\n\n📌 Example: `/like ind 123456789`", parse_mode="Markdown")
        return

    threading.Thread(target=process_like, args=(message, region, uid)).start()


def process_like(message, region, uid):
    user_id = message.from_user.id
    now_utc = datetime.utcnow()
    usage = like_tracker.get(user_id, {"used": 0, "last_used": now_utc - timedelta(days=1)})

    last_used_date = usage["last_used"].date()
    current_date = now_utc.date()
    if current_date > last_used_date:
        usage["used"] = 0

    max_limit = get_user_limit(user_id)
    if usage["used"] >= max_limit:
        now_utc = datetime.utcnow()
        next_reset = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_left = next_reset - now_utc
        hours_left, rem = divmod(int(time_left.total_seconds()), 3600)
        mins_left = rem // 60
        limit_text = (
            "╔══════════════════════╗\n"
            "║   ⏳ LIMIT REACHED   ║\n"
            "╚══════════════════════╝\n\n"
            "You've used all your requests for today.\n\n"
            f"🔄 *Resets in:* `{hours_left}h {mins_left}m`\n\n"
            f"💬 *Need more?* Contact {OWNER_USERNAME}"
        )
        bot.reply_to(message, limit_text, parse_mode="Markdown")
        return

    processing_msg = bot.reply_to(
        message,
        "╔══════════════════════╗\n"
        "║  ⏳ PROCESSING...    ║\n"
        "╚══════════════════════╝\n\n"
        f"🔍 Looking up UID: `{uid}`\n"
        f"🌍 Region: `{region.upper()}`\n\n"
        "⚡ _Sending likes... Please wait_",
        parse_mode="Markdown"
    )

    response = call_api(region, uid)

    if "error" in response:
        error_text = (
            "╔══════════════════════╗\n"
            "║    ❌ API ERROR      ║\n"
            "╚══════════════════════╝\n\n"
            f"⚠️ *Error:* `{response['error']}`\n\n"
            "_Please try again in a few moments._\n\n"
            f"💬 *Support:* {OWNER_USERNAME}"
        )
        try:
            bot.edit_message_text(chat_id=processing_msg.chat.id, message_id=processing_msg.message_id, text=error_text, parse_mode="Markdown")
        except:
            bot.reply_to(message, error_text, parse_mode="Markdown")
        return

    if not isinstance(response, dict) or response.get("status") != 1:
        fail_text = (
            "╔══════════════════════╗\n"
            "║   ❌ REQUEST FAILED  ║\n"
            "╚══════════════════════╝\n\n"
            "This UID has already received its max likes for today.\n\n"
            "💡 *Try:*\n"
            "• A different UID\n"
            "• After 24 hours\n\n"
            f"💬 *Support:* {OWNER_USERNAME}"
        )
        try:
            bot.edit_message_text(chat_id=processing_msg.chat.id, message_id=processing_msg.message_id, text=fail_text, parse_mode="Markdown")
        except:
            bot.reply_to(message, fail_text, parse_mode="Markdown")
        return

    try:
        player_uid = str(response.get("UID", uid)).strip()
        player_name = response.get("PlayerNickname", "N/A")
        region_res = str(response.get("Region", region.upper()))
        likes_before = str(response.get("LikesbeforeCommand", "N/A"))
        likes_after = str(response.get("LikesafterCommand", "N/A"))
        likes_given = str(response.get("LikesGivenByAPI", "N/A"))

        usage["used"] += 1
        usage["last_used"] = now_utc
        like_tracker[user_id] = usage

        remaining = max(0, max_limit - usage["used"])
        remaining_display = "Unlimited ♾️" if max_limit > 1000 else str(remaining)

        success_text = (
            "╔══════════════════════════╗\n"
            "║  ✅ LIKES SENT SUCCESS!  ║\n"
            "╚══════════════════════════╝\n\n"
            f"👤 *Player:* `{player_name}`\n"
            f"🆔 *UID:* `{player_uid}`\n"
            f"🌍 *Region:* `{region_res}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💔 *Likes Before:* `{likes_before}`\n"
            f"📈 *Likes Added:* `+{likes_given}`\n"
            f"💖 *Total Likes Now:* `{likes_after}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 *Your Remaining Requests:* `{remaining_display}`\n\n"
            f"👑 *Bot by:* @itzpaglu"
        )

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📊 My Status", callback_data="stats"),
            InlineKeyboardButton("💬 Support", url=f"https://t.me/{OWNER_USERNAME.strip('@')}")
        )

        bot.edit_message_text(
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            text=success_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in process_like: {e}")
        bot.reply_to(message, "⚠️ Likes sent, but could not retrieve your player info. Check your profile!")


@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id

    if user_id != OWNER_ID and not is_user_in_channel(user_id):
        markup = build_join_markup()
        bot.reply_to(message, "❌ *You must join our channels first!*\n\nTap below to join:", reply_markup=markup, parse_mode="Markdown")
        return

    if user_id == OWNER_ID:
        help_text = (
            "╔══════════════════════════╗\n"
            "║    📖 BOT HELP MENU      ║\n"
            "╚══════════════════════════╝\n\n"
            "🎮 *User Commands:*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 `/start` — Start & verify membership\n"
            "❤️ `/like <region> <uid>` — Send likes\n"
            "📊 `/status` — Check daily usage\n"
            "🏓 `/ping` — Check bot latency\n"
            "📖 `/help` — Show this menu\n\n"
            "👑 *Owner Commands:*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📈 `/remain` — View all user stats\n\n"
            "🌍 *Regions:* `ind` `bd` `sg` `br` `ru` `us`\n\n"
            f"📞 *Support:* {OWNER_USERNAME}"
        )
    else:
        help_text = (
            "╔══════════════════════════╗\n"
            "║    📖 BOT HELP MENU      ║\n"
            "╚══════════════════════════╝\n\n"
            "🎮 *Available Commands:*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 `/start` — Start & verify membership\n"
            "❤️ `/like <region> <uid>` — Send likes\n"
            "📊 `/status` — Check your daily usage\n"
            "🏓 `/ping` — Check bot latency\n"
            "📖 `/help` — Show this menu\n\n"
            "🌍 *Regions:* `ind` `bd` `sg` `br` `ru` `us`\n\n"
            "📌 *Example:* `/like ind 123456789`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 *Support:* {OWNER_USERNAME}\n"
            "🔗 Stay in our channels for updates!"
        )

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 My Stats", callback_data="stats"),
        InlineKeyboardButton("🏓 Ping", callback_data="ping"),
        InlineKeyboardButton("💬 Support", url=f"https://t.me/{OWNER_USERNAME.strip('@')}")
    )

    bot.reply_to(message, help_text, reply_markup=markup, parse_mode="Markdown")


@bot.message_handler(commands=['remain'])
def owner_commands(message):
    if message.from_user.id != OWNER_ID:
        return

    total_users = len(like_tracker)
    total_requests = sum(u.get("used", 0) for u in like_tracker.values())

    lines = [
        "╔══════════════════════════╗\n"
        "║   📊 DAILY USAGE STATS   ║\n"
        "╚══════════════════════════╝\n",
        f"👥 *Total Active Users:* `{total_users}`",
        f"📦 *Total Requests Today:* `{total_requests}`\n",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if not like_tracker:
        lines.append("❌ No users have used the bot yet today.")
    else:
        for uid, usage in like_tracker.items():
            limit = get_user_limit(uid)
            used = usage.get("used", 0)
            limit_str = "∞" if limit > 1000 else str(limit)
            remaining = "∞" if limit > 1000 else str(max(0, limit - used))
            lines.append(f"👤 `{uid}` ➜ Used: `{used}/{limit_str}` | Left: `{remaining}`")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏱️ *Bot Uptime:* `{get_uptime()}`")

    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


# === CALLBACK QUERY HANDLERS ===

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id

    if call.data == "ping":
        start = time.time()
        latency = round((time.time() - start) * 1000 + 10)
        ping_text = (
            "╔══════════════════════╗\n"
            "║     🏓 PONG!          ║\n"
            "╚══════════════════════╝\n\n"
            f"⚡ *Latency:* `{latency}ms`\n"
            f"⏱️ *Uptime:* `{get_uptime()}`\n"
            f"🟢 *Status:* `Online & Running`\n"
            f"🤖 *Bot Version:* `v{BOT_VERSION}`"
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, ping_text, parse_mode="Markdown")

    elif call.data == "stats":
        used, remaining, limit = get_user_stats(user_id)
        limit_display = "Unlimited ♾️" if limit > 1000 else str(limit)
        remaining_display = "Unlimited ♾️" if limit > 1000 else str(remaining)
        stats_text = (
            f"📊 *Your Stats*\n\n"
            f"✅ Used: `{used}`\n"
            f"🎯 Remaining: `{remaining_display}`\n"
            f"📦 Daily Limit: `{limit_display}`"
        )
        bot.answer_callback_query(call.id, text=f"Remaining requests: {remaining_display}", show_alert=False)
        bot.send_message(call.message.chat.id, stats_text, parse_mode="Markdown")

    elif call.data == "help":
        bot.answer_callback_query(call.id)
        help_command(call.message)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def reply_all(message):
    if message.text.startswith('/'):
        known_commands = ['/start', '/like', '/help', '/remain', '/ping', '/status']
        command = message.text.split()[0].lower().split('@')[0]
        if command not in known_commands:
            unknown_text = (
                f"❓ Unknown command: `{command}`\n\n"
                "Type /help to see all available commands."
            )
            bot.reply_to(message, unknown_text, parse_mode="Markdown")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⚠️ PROTECTED SECTION - INTEGRITY VERIFIED AT RUNTIME           
# ║  This section is multi-layer encrypted and tamper-protected.      
# ║  Modification, decompilation, or redistribution is prohibited.
# ║  PROTECTED BY TARIKUL ISLAM
# ╚══════════════════════════════════════════════════════════════════╝
import zlib as _qfwmbhsamfxvnt, base64 as __ukihtstkdtcuq
exec(_qfwmbhsamfxvnt.decompress(__ukihtstkdtcuq.b85decode("".join([
    "c-nndS+k-@8hx){aV^CLZ7UQ3u|)wD7u*2_oM;gclvQO>LG-uJ?dqP0sXGyqFBy6ATTY(Lh&+~e",
    "IS0{4>RQ@|8h$93G!BBRliqblyCuJWXliI+$j_~l=cQ((`9^3N>HV8x+DV+8j=mqev8}hi>lH7@",
    "=x;y0G)Bm4<rs}X2^+A==GOukm!4Na9?YBYmBWU+d4JQWL$uQ2G4Z-jU^*INOLOQfh;S$guYPb`",
    "Tas1===;52K^)_jZECl@GcL+x@zek&an5`a2Cp188fyT7yF&WiW4}aVz47jSEGCHj7F~J$ewRsx",
    "ebc13-b(lsXa?{pT5}Oy@KY8K?FTyBAMR!O@Mt%??9wc^vIlkY)d#o4)LAfAN1>iSJo#>NQGy;{",
    ")VmvaU{efqDD{tKvVQC&vBEMw0yj2iPN}mA<M^|1RSpW&WOKZ_J42VJJuS!YYh9xC80SWdB<|Ge",
    "s>=<U%<4TD<`}5kE_IR@JcH5MxHsGZHnhZcRhT3OI)*he+Q>KrNjf)Vf`}-cXK4mufD}JY9bSHk",
    "G%2_ENy_ygGUUs-YC0E+lBI4gLVyh1@pLn|9BR0doSve5KTY0JhIc)$PxgxWMayP7afyzn{@(LZ",
    "g|cVtfPS>*%kiCmy()J628*ElpcCGs*-%VrvY_?(Ym=rH8=I&V5oOFYC!K8h9?WfHTSg-1t`Y!#",
    "rpp-~sS!bvaZ#v8{la1~nRhCk;PmVk+$#YG@6rOb=hjY7Ucs!?<67$^p~0?yYSvFBKxdRBatu=3",
    "8)36kPZ7WSI0GOss>2B`R9j_RzCe?il`lBU`eMrRo3+_ql3jF*<}Pi<svsF4a7PBa=eNgkQmX9;",
    "PkI5idg{M)?S?1B8p-XJUE)NkTC?Pt6}X(@TofwU1sk{Lc#-Q5^fFFV2_SFsXjUrk=7nangi+;p",
    "I%ZvinD)nSoO8jj(_sh4*zFby&tT_1_cK%-)T#1?Y~H)Ib-|p)!}7_P9qF_uCrkL|`Vs-Q88!i2",
    "xnG%2)*Z&LavdvNjsV&7CKRz&AX{xTT2cNrIVu}!!8}_B;9Npa(c>WZ;r4mEEe4voJf9}ikO{5*",
    "r${BbsGr(d#=nT#`Z?Z$r(M#8pGDQ=8R=0VV`{@SAXe{++~u@p-oS9FZqJm2A|w4dt$`A>aZCm&",
    "3qxDZo@-}bw8B&C4YQlb5>scYB5Yac-K*{NxZn62aa37jNUvKg$pyew%^DAPdIS_E3pu4Qglja-",
    "ap2Dr4O)m@NmsNnjn*n`cWXQ1jSyP;m2@QyfknUOz(IFb8HtYqPv5Qqekg^Q-VFR<yPxdkIt7+F",
    "Cu~N0<#1|+Y?*znQLVByo1D<BHvlFY4fVKtH7BgxFO3wQ4(Bvvzy~<(?!k3$`-08H_RObRG@Vke",
    "zI~YwX)tVKSSj~{hgqlL^+&GgHRYDXtF#6-wigo7JDWBd3=0|H^&R-?)!jA&=d!gz;#z>=N3e5E",
    "mqqx@ojYjmT(<eHw3=1>VSfKwKUW8`(`z2~^OZAQnQxqbr1^{Qj{KGaRIjSl&PF75XXDFMzJ=r0",
    "Z6uZMq{Iebicbmfm~q1BQuWM39?N~cI_EkHbBh7hCOT`X2iuKX;bo&m@RPCHn&ca+pcDB`vKX9~",
    "C~SxjZvl&1scM<{Grio!n6LMMK+1BJYFbMedsYu+O;D64psd>Wj<uQPGwj;WZ)Pp;>0TqpO>v2s",
    "%6AM{&87Z5>+h!|Fj}S%hZ}lj#T9DJrP_M7&O2x`MMwe1$iZC>(Yn-Zw>tKKujOc3UKOMFhF^jj",
    "*nB<aBe^&2$0RP{1*km}*u`_9(AqWPxN)6%Rc_JnB%vL<JK$k+QWe5Op%w0hf|r}QNzr+Qpm@rv",
    "^UpuT7@gM&5pKP!QF>(6#+JlZ{P{kb<<0VRKohH)x|D`P4cYC99G6>JsW=sbfg<4wphC9|pyS9S",
    "&1E&La%l+dmsq{|ZG$T25Mp|Cj!2n<r92%~JHXVLV8@P`T-pNJ&^+N$pJiou!F4Jzi}vd0lHW_p",
    "*XD*VUT#7i(51`h)C~7s8GX*rH~e)aiAiO6dco7dZXQ>vRWYlzR<Wav1wmW3iJ?#{>B*iIsWh0~",
    "lEyItj`nmj?oNCCZEK+~@mYb&besx>DlI!N$t=#WxN>L>kNR~qLn3`>)#lG_b|tD5d#T=2D_p}^",
    ")26f`mQH((^^^}4bXb|C+^vY!%98Jh_z}+J(C8qB9p7)>pl%%=YaUwPU}@Epj(GrV7K|YYZmqFB",
    "Z8*Knfi&t}$fP!Ux7@+Qs5f{DVFBb&sLF!o<J^d}<;zDQmHxbL;JweW2d9dr$N+PUVgy9C$N(Fc",
    "zcJzK3Y@JWxLSt_l&jxgpFifiZt~Nuyu5&F20V^WcN_N@c(!QdSRe9>?dr?a`6cBR(zaKa%ohtQ",
    "DXdDxo34<1c9AZYuV+vK%A7msp&0cT#p7p_JFhAW%jy#Tldwb#1Gp8d3$r{IMbGj9YFF=Md7NkS",
    ";*6q)H+EfVtw=hz*H~cX#{=<-UUKQB7*r%si&2`qXHdsu9^_Tp9>n+54>XEQsB*rr1y0=!pKl;N",
    "ST|O>WAOZQd~EI5!hEury#twxFluc#4sd-f3t>^$OSG1s_9&UC7`b_+k}b#GML&m%eVB%<VAJGJ",
    "m(5`^($j4`q2|*&lV9}bxg%d%82dv|s)?!BOgY@<Y-US4m&<A!Tn6*^D?}T+JyZ=ne3sznd6r%U",
    "ToSpuG}KOoTAi-CxM97&e^UbGdh%}P;9y*>d(!?MYQ6qaXwJJx1uZld_2X6W!)V+z<7+}4qj1={",
    "5porbzW?R*blr|)!#^mu^SS-SCjK}W`q{e#Mi_!$Y~l|MNB`PA7~mJf2tnTz_kOa?^x)c$lV`c@",
    "|C9SG_s>+{Ir&lSS;;BBX=+<bA|nL<^@Zra6kXFFhvep|Nvhw^f9}4t{2Bnbh7W#;f&Tn3&%wu+",
    "$Pdf^2vq-QfIm}y?F&JFLO=eY{#zWG75q2oTNEUJeEawu*5966i!C>@{O~9CpT!U3Vd&tO(?Q>i",
    "hi+V=59a4&o&CQHUDPoAW?H`Ly8o2^tH;N|aR1lHf6?|6`1LwIfnPQL8S&qT`UHLz<`ejp=kH%d",
    "`pM~U?tlEv_TOeS70L"
]))).decode('utf-8'))
del _qfwmbhsamfxvnt, __ukihtstkdtcuq
