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
# ║  CREATOR: SIFAT 💀
# ║  TELEGRAM: https://t.me/MaybeSifu
# ╚══════════════════════════════════════════════════════════════════╝

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found!")
    sys.exit(1)

REQUIRED_CHANNELS = ["@maybesifatx69"]
GROUP_JOIN_LINK    = "https://t.me/maybesifatx69"
OWNER_ID           = 8438269386
OWNER_USERNAME     = "@MaybeSifu"
BOT_NAME           = "FF LIKES BOT"
BOT_VERSION        = "3.0"
AUTHOR             = "SIFAT 💀"

# External API base (same domain used for all FF endpoints)
API_BASE = "https://your-free-fire-like-api-domain"

bot            = telebot.TeleBot(BOT_TOKEN)
like_tracker   = {}        # { user_id: {used, last_used} }
banned_users   = set()     # banned user IDs
extra_limits   = {}        # { user_id: extra_int }
broadcast_log  = set()     # user IDs who have ever talked to bot
bot_start_time = datetime.utcnow()

app = Flask(__name__)

# ─── RESET THREAD ───────────────────────────────────────────────────────────

def reset_limits():
    while True:
        try:
            now = datetime.utcnow()
            nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            time.sleep((nxt - now).total_seconds())
            like_tracker.clear()
            extra_limits.clear()
            logger.info("✅ Daily limits reset at 00:00 UTC")
        except Exception as e:
            logger.error(f"reset_limits error: {e}")

threading.Thread(target=reset_limits, daemon=True).start()

# ─── UTILITIES ───────────────────────────────────────────────────────────────

def is_member(user_id):
    try:
        for ch in REQUIRED_CHANNELS:
            m = bot.get_chat_member(ch, user_id)
            if m.status not in ('member', 'administrator', 'creator'):
                return False
        return True
    except Exception as e:
        logger.error(f"is_member: {e}")
        return False

def get_daily_limit(user_id):
    if user_id == OWNER_ID:
        return 999_999_999
    base  = 1
    extra = extra_limits.get(user_id, 0)
    return base + extra

def get_usage(user_id):
    now   = datetime.utcnow()
    data  = like_tracker.get(user_id, {"used": 0, "last_used": now - timedelta(days=1)})
    if now.date() > data["last_used"].date():
        data["used"] = 0
    limit     = get_daily_limit(user_id)
    used      = data["used"]
    remaining = max(0, limit - used)
    return used, remaining, limit

def get_uptime():
    d = datetime.utcnow() - bot_start_time
    h, rem = divmod(int(d.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

def reset_countdown():
    now = datetime.utcnow()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    d   = nxt - now
    h, rem = divmod(int(d.total_seconds()), 3600)
    m, _   = divmod(rem, 60)
    return f"{h}h {m}m"

def join_markup():
    mu = InlineKeyboardMarkup()
    for ch in REQUIRED_CHANNELS:
        mu.add(InlineKeyboardButton(f"📢 Join {ch}", url=f"https://t.me/{ch.strip('@')}"))
    return mu

def limit_display(limit, remaining):
    if limit > 1_000_000:
        return "♾️ Unlimited", "♾️ Unlimited"
    return str(limit), str(remaining)

def usage_bar(used, limit, size=10):
    if limit > 1_000_000:
        return "🟩" * size
    filled = max(0, size - round((used / limit) * size)) if limit else size
    return "🟩" * filled + "🟥" * (size - filled)

def api_get(endpoint, params):
    try:
        r = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=20)
        if r.status_code != 200:
            return {"error": f"Server returned {r.status_code}"}
        return r.json()
    except requests.exceptions.RequestException as e:
        return {"error": "API connection failed. Try again later."}
    except ValueError:
        return {"error": "Invalid API response."}

# ─── BOX / UI HELPERS ────────────────────────────────────────────────────────

def box(title, body, footer=None):
    """Build a nicely formatted Telegram message block."""
    lines = [f"╭─「 {title} 」", "│"]
    for line in body:
        lines.append(f"│  {line}")
    lines.append("│")
    if footer:
        lines.append(f"╰─ {footer}")
    else:
        lines.append("╰──────────────────────")
    return "\n".join(lines)

def section(title, cmds):
    """Command grid section for help menu."""
    pairs  = [cmds[i:i+2] for i in range(0, len(cmds), 2)]
    lines  = [f"\n`╭─「 {title} 」`"]
    for pair in pairs:
        row = "  ".join(f"`├⊙` `{c}`" for c in pair)
        lines.append(row)
    lines.append("`╰──────────────────────`")
    return "\n".join(lines)

# ─── FLASK ───────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return {"status": "running", "bot": BOT_NAME, "version": BOT_VERSION,
            "uptime": get_uptime(), "author": AUTHOR}

@app.route('/health')
def health():
    return {"status": "healthy", "uptime": get_uptime()}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode())])
        return '', 200
    except Exception as e:
        logger.error(f"webhook: {e}")
        return '', 500

# ─── /start ──────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "Player"
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 *You have been banned from using this bot.*", parse_mode="Markdown")
        return

    if not is_member(uid):
        bot.reply_to(message,
            "╭─「 🔒 *ACCESS REQUIRED* 」\n"
            "│\n"
            f"│  Hey *{name}!* 👋\n"
            "│  You must join our channel first\n"
            "│  to unlock this bot.\n"
            "│\n"
            "╰─ Tap below, then send /start again",
            reply_markup=join_markup(), parse_mode="Markdown")
        return

    if uid not in like_tracker:
        like_tracker[uid] = {"used": 0, "last_used": datetime.utcnow() - timedelta(days=1)}

    used, remaining, limit = get_usage(uid)
    lim_str, rem_str = limit_display(limit, remaining)

    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("📖 Help",     callback_data="help"),
        InlineKeyboardButton("📊 My Stats", callback_data="stats"),
        InlineKeyboardButton("🏓 Ping",     callback_data="ping"),
        InlineKeyboardButton("💬 Support",  url=f"https://t.me/{OWNER_USERNAME.strip('@')}")
    )

    bot.reply_to(message,
        f"╭─「 🔥 *{BOT_NAME}* 」\n"
        f"│\n"
        f"│  ✅ Welcome, *{name}!*\n"
        f"│\n"
        f"│  🌺 *Author*   : {AUTHOR}\n"
        f"│  🌺 *Version*  : v{BOT_VERSION}\n"
        f"│  🌺 *Uptime*   : `{get_uptime()}`\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━\n"
        f"│  📦 *Used Today* : `{used}`\n"
        f"│  🎯 *Remaining*  : `{rem_str}`\n"
        f"│  🔄 *Resets in*  : `{reset_countdown()}`\n"
        f"│\n"
        f"│  📌 Use `/like <region> <uid>`\n"
        f"│     in the group to send likes\n"
        f"│\n"
        f"╰─ 💬 Support: {OWNER_USERNAME}",
        reply_markup=mu, parse_mode="Markdown")

# ─── /help ───────────────────────────────────────────────────────────────────

TOTAL_COMMANDS = 14  # update if you add more

@bot.message_handler(commands=['help'])
def cmd_help(message):
    uid = message.from_user.id
    broadcast_log.add(uid)

    if uid != OWNER_ID and not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return

    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("📊 My Stats", callback_data="stats"),
        InlineKeyboardButton("🏓 Ping",     callback_data="ping"),
        InlineKeyboardButton("💬 Support",  url=f"https://t.me/{OWNER_USERNAME.strip('@')}")
    )

    owner_section = ""
    if uid == OWNER_ID:
        owner_section = (
            "\n`╭─「 👑 OWNER ONLY 」`\n"
            "`├⊙` `/broadcast`  `├⊙` `/remain`\n"
            "`├⊙` `/addlimit`   `├⊙` `/ban`\n"
            "`├⊙` `/unban`      `├⊙` `/users`\n"
            "`╰──────────────────────`"
        )

    text = (
        f"╭─「 🤖 *{BOT_NAME}* 」\n"
        f"│  ☠️ *Author*   : {AUTHOR}\n"
        f"│  📌 *Version*  : v{BOT_VERSION}\n"
        f"│  📦 *Commands* : {TOTAL_COMMANDS}+\n"
        f"╰──────────────────────\n"
        "\n`╭─「 🎮 FREE FIRE TOOLS 」`\n"
        "`├⊙` `/like`      `├⊙` `/profile`\n"
        "`├⊙` `/guild`     `├⊙` `/rank`\n"
        "`╰──────────────────────`\n"
        "\n`╭─「 📊 USER TOOLS 」`\n"
        "`├⊙` `/status`    `├⊙` `/ping`\n"
        "`├⊙` `/servertime``├⊙` `/about`\n"
        "`├⊙` `/help`      `├⊙` `/start`\n"
        "`╰──────────────────────`\n"
        f"{owner_section}\n"
        f"\n🌍 *Regions:* `ind` `bd` `sg` `br` `ru` `us` `th` `id`\n"
        f"📌 *Example:* `/like ind 123456789`\n\n"
        f"💬 Support: {OWNER_USERNAME}"
    )

    bot.reply_to(message, text, reply_markup=mu, parse_mode="Markdown")

# ─── /ping ───────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    broadcast_log.add(message.from_user.id)
    t0   = time.time()
    sent = bot.reply_to(message, "🏓 Pinging...")
    ms   = round((time.time() - t0) * 1000)
    bot.edit_message_text(
        f"╭─「 🏓 *PONG!* 」\n"
        f"│\n"
        f"│  ⚡ *Latency* : `{ms}ms`\n"
        f"│  ⏱️ *Uptime*  : `{get_uptime()}`\n"
        f"│  🟢 *Status*  : `Online`\n"
        f"│  🤖 *Version* : `v{BOT_VERSION}`\n"
        f"│  ☠️ *Author*  : {AUTHOR}\n"
        f"│\n"
        f"╰──────────────────────",
        chat_id=sent.chat.id, message_id=sent.message_id, parse_mode="Markdown")

# ─── /status ─────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['status'])
def cmd_status(message):
    uid = message.from_user.id
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return
    if not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return

    used, remaining, limit = get_usage(uid)
    lim_str, rem_str = limit_display(limit, remaining)
    bar = usage_bar(used, limit)

    bot.reply_to(message,
        f"╭─「 📊 *YOUR STATUS* 」\n"
        f"│\n"
        f"│  👤 *User ID*    : `{uid}`\n"
        f"│\n"
        f"│  📦 *Limit*      : `{lim_str}`\n"
        f"│  ✅ *Used*       : `{used}`\n"
        f"│  🎯 *Remaining*  : `{rem_str}`\n"
        f"│\n"
        f"│  {bar}\n"
        f"│\n"
        f"│  🔄 *Resets in*  : `{reset_countdown()}`\n"
        f"│\n"
        f"╰─ 💬 {OWNER_USERNAME}",
        parse_mode="Markdown")

# ─── /servertime ─────────────────────────────────────────────────────────────

@bot.message_handler(commands=['servertime'])
def cmd_servertime(message):
    broadcast_log.add(message.from_user.id)
    now = datetime.utcnow()
    bot.reply_to(message,
        f"╭─「 🕐 *SERVER TIME* 」\n"
        f"│\n"
        f"│  🌐 *UTC Time*   : `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"│  ⏱️ *Bot Uptime* : `{get_uptime()}`\n"
        f"│  🔄 *Next Reset* : `{reset_countdown()}`\n"
        f"│\n"
        f"╰──────────────────────",
        parse_mode="Markdown")

# ─── /about ──────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['about'])
def cmd_about(message):
    broadcast_log.add(message.from_user.id)
    bot.reply_to(message,
        f"╭─「 ℹ️ *ABOUT BOT* 」\n"
        f"│\n"
        f"│  🤖 *Bot Name*  : {BOT_NAME}\n"
        f"│  ☠️ *Author*    : {AUTHOR}\n"
        f"│  📌 *Version*   : v{BOT_VERSION}\n"
        f"│  💬 *Contact*   : {OWNER_USERNAME}\n"
        f"│  ⏱️ *Uptime*    : `{get_uptime()}`\n"
        f"│\n"
        f"│  Built for Free Fire players.\n"
        f"│  Send likes to any FF profile\n"
        f"│  fast and easily via Telegram.\n"
        f"│\n"
        f"╰──────────────────────",
        parse_mode="Markdown")

# ─── /like ───────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['like'])
def cmd_like(message):
    uid  = message.from_user.id
    args = message.text.split()
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 *You are banned from using this bot.*", parse_mode="Markdown")
        return

    if message.chat.type == "private" and uid != OWNER_ID:
        mu = InlineKeyboardMarkup()
        mu.add(InlineKeyboardButton("🔗 Join Official Group", url=GROUP_JOIN_LINK))
        bot.reply_to(message,
            "╭─「 ⚠️ *GROUP ONLY* 」\n"
            "│\n"
            "│  This command only works\n"
            "│  inside a group chat.\n"
            "│\n"
            "╰─ Join our group below 👇",
            reply_markup=mu, parse_mode="Markdown")
        return

    if not is_member(uid):
        bot.reply_to(message, "❌ *Join our channel first!*", reply_markup=join_markup(), parse_mode="Markdown")
        return

    if len(args) != 3:
        bot.reply_to(message,
            "╭─「 ❌ *WRONG FORMAT* 」\n"
            "│\n"
            "│  📌 Usage:\n"
            "│  `/like <region> <uid>`\n"
            "│\n"
            "│  🌍 Example:\n"
            "│  `/like ind 123456789`\n"
            "│\n"
            "│  Regions: `ind bd sg br ru us`\n"
            "╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].lower(), args[2]
    if not region.isalpha() or not target_uid.isdigit():
        bot.reply_to(message, "⚠️ Region = letters only, UID = numbers only.\nExample: `/like ind 123456789`", parse_mode="Markdown")
        return

    threading.Thread(target=_process_like, args=(message, region, target_uid)).start()

def _process_like(message, region, target_uid):
    uid = message.from_user.id
    now = datetime.utcnow()

    data = like_tracker.get(uid, {"used": 0, "last_used": now - timedelta(days=1)})
    if now.date() > data["last_used"].date():
        data["used"] = 0

    limit = get_daily_limit(uid)
    if data["used"] >= limit:
        bot.reply_to(message,
            f"╭─「 ⏳ *LIMIT REACHED* 」\n"
            f"│\n"
            f"│  You've used all your requests.\n"
            f"│\n"
            f"│  🔄 *Resets in* : `{reset_countdown()}`\n"
            f"│\n"
            f"╰─ 💬 Need more? {OWNER_USERNAME}",
            parse_mode="Markdown")
        return

    wait_msg = bot.reply_to(message,
        f"╭─「 ⏳ *PROCESSING...* 」\n"
        f"│\n"
        f"│  🔍 UID    : `{target_uid}`\n"
        f"│  🌍 Region : `{region.upper()}`\n"
        f"│\n"
        f"│  ⚡ _Sending likes, please wait..._\n"
        f"╰──────────────────────",
        parse_mode="Markdown")

    resp = api_get("like", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        _edit(wait_msg,
            f"╭─「 ❌ *API ERROR* 」\n"
            f"│\n"
            f"│  ⚠️ `{resp['error']}`\n"
            f"│\n"
            f"╰─ 💬 {OWNER_USERNAME}")
        return

    if not isinstance(resp, dict) or resp.get("status") != 1:
        _edit(wait_msg,
            f"╭─「 ❌ *REQUEST FAILED* 」\n"
            f"│\n"
            f"│  This UID has reached its max\n"
            f"│  likes for today.\n"
            f"│\n"
            f"│  💡 Try a different UID or\n"
            f"│     come back after 24h.\n"
            f"│\n"
            f"╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        p_uid     = str(resp.get("UID", target_uid)).strip()
        p_name    = resp.get("PlayerNickname", "N/A")
        p_region  = str(resp.get("Region", region.upper()))
        l_before  = str(resp.get("LikesbeforeCommand", "N/A"))
        l_after   = str(resp.get("LikesafterCommand", "N/A"))
        l_given   = str(resp.get("LikesGivenByAPI", "N/A"))

        data["used"] += 1
        data["last_used"] = now
        like_tracker[uid] = data

        _, remaining, lim = get_usage(uid)
        _, rem_str = limit_display(lim, remaining)

        mu = InlineKeyboardMarkup(row_width=2)
        mu.add(
            InlineKeyboardButton("📊 My Stats", callback_data="stats"),
            InlineKeyboardButton("💬 Support",  url=f"https://t.me/{OWNER_USERNAME.strip('@')}")
        )

        _edit(wait_msg,
            f"╭─「 ✅ *LIKES SENT!* 」\n"
            f"│\n"
            f"│  👤 *Name*    : `{p_name}`\n"
            f"│  🆔 *UID*     : `{p_uid}`\n"
            f"│  🌍 *Region*  : `{p_region}`\n"
            f"│\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│  💔 *Before*  : `{l_before}`\n"
            f"│  📈 *Added*   : `+{l_given}`\n"
            f"│  💖 *Total*   : `{l_after}`\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│\n"
            f"│  🎯 *Remaining* : `{rem_str}`\n"
            f"│\n"
            f"╰─ ☠️ Bot by {AUTHOR}",
            markup=mu)
    except Exception as e:
        logger.error(f"_process_like: {e}")
        bot.reply_to(message, "⚠️ Likes sent, but couldn't decode the response.")

# ─── /profile ────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['profile'])
def cmd_profile(message):
    uid  = message.from_user.id
    args = message.text.split()
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return
    if not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return
    if len(args) != 3 or not args[1].isalpha() or not args[2].isdigit():
        bot.reply_to(message,
            "╭─「 ❌ *WRONG FORMAT* 」\n│\n│  `/profile <region> <uid>`\n│\n│  Example: `/profile ind 123456789`\n╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].lower(), args[2]
    wait = bot.reply_to(message, "⏳ _Fetching player profile..._", parse_mode="Markdown")
    resp = api_get("playerinfo", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        _edit(wait, f"╭─「 ❌ *API ERROR* 」\n│\n│  ⚠️ `{resp['error']}`\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        name   = resp.get("PlayerNickname") or resp.get("nickname", "N/A")
        level  = resp.get("Level") or resp.get("level", "N/A")
        likes  = resp.get("Likes") or resp.get("likes", "N/A")
        rank   = resp.get("Rank") or resp.get("rank", "N/A")
        guild  = resp.get("GuildName") or resp.get("guildName", "N/A")
        reg    = resp.get("Region") or region.upper()

        _edit(wait,
            f"╭─「 👤 *PLAYER PROFILE* 」\n"
            f"│\n"
            f"│  🆔 *UID*     : `{target_uid}`\n"
            f"│  👤 *Name*    : `{name}`\n"
            f"│  🌍 *Region*  : `{reg}`\n"
            f"│  ⚔️ *Level*   : `{level}`\n"
            f"│  ❤️ *Likes*   : `{likes}`\n"
            f"│  🏆 *Rank*    : `{rank}`\n"
            f"│  🏰 *Guild*   : `{guild}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}")
    except Exception as e:
        logger.error(f"cmd_profile: {e}")
        _edit(wait, "⚠️ Could not parse profile data.")

# ─── /guild ──────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['guild'])
def cmd_guild(message):
    uid  = message.from_user.id
    args = message.text.split()
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return
    if not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return
    if len(args) != 3 or not args[1].isalpha() or not args[2].isdigit():
        bot.reply_to(message,
            "╭─「 ❌ *WRONG FORMAT* 」\n│\n│  `/guild <region> <guild_id>`\n│\n│  Example: `/guild ind 3001234567`\n╰──────────────────────",
            parse_mode="Markdown")
        return

    region, guild_id = args[1].lower(), args[2]
    wait = bot.reply_to(message, "⏳ _Fetching guild info..._", parse_mode="Markdown")
    resp = api_get("guild", {"id": guild_id, "server_name": region})

    if "error" in resp:
        _edit(wait, f"╭─「 ❌ *API ERROR* 」\n│\n│  ⚠️ `{resp['error']}`\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        g_name   = resp.get("GuildName") or resp.get("name", "N/A")
        g_level  = resp.get("GuildLevel") or resp.get("level", "N/A")
        g_cap    = resp.get("GuildCapacity") or resp.get("capacity", "N/A")
        g_mem    = resp.get("GuildMembers") or resp.get("members", "N/A")
        g_leader = resp.get("LeaderNickname") or resp.get("leader", "N/A")
        g_score  = resp.get("GuildScore") or resp.get("score", "N/A")

        _edit(wait,
            f"╭─「 🏰 *GUILD INFO* 」\n"
            f"│\n"
            f"│  🆔 *Guild ID*  : `{guild_id}`\n"
            f"│  🏰 *Name*      : `{g_name}`\n"
            f"│  🌍 *Region*    : `{region.upper()}`\n"
            f"│  ⭐ *Level*     : `{g_level}`\n"
            f"│  👥 *Members*   : `{g_mem}/{g_cap}`\n"
            f"│  👑 *Leader*    : `{g_leader}`\n"
            f"│  🏆 *Score*     : `{g_score}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}")
    except Exception as e:
        logger.error(f"cmd_guild: {e}")
        _edit(wait, "⚠️ Could not parse guild data.")

# ─── /rank ───────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['rank'])
def cmd_rank(message):
    uid  = message.from_user.id
    args = message.text.split()
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return
    if not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return
    if len(args) != 3 or not args[1].isalpha() or not args[2].isdigit():
        bot.reply_to(message,
            "╭─「 ❌ *WRONG FORMAT* 」\n│\n│  `/rank <region> <uid>`\n│\n│  Example: `/rank ind 123456789`\n╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].lower(), args[2]
    wait = bot.reply_to(message, "⏳ _Checking rank..._", parse_mode="Markdown")
    resp = api_get("playerinfo", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        _edit(wait, f"╭─「 ❌ *API ERROR* 」\n│\n│  ⚠️ `{resp['error']}`\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        name       = resp.get("PlayerNickname") or resp.get("nickname", "N/A")
        br_rank    = resp.get("BRRank") or resp.get("brRank", "N/A")
        cs_rank    = resp.get("CSRank") or resp.get("csRank", "N/A")
        br_points  = resp.get("BRRankPoints") or resp.get("brPoints", "N/A")
        cs_points  = resp.get("CSRankPoints") or resp.get("csPoints", "N/A")

        _edit(wait,
            f"╭─「 🏆 *RANK INFO* 」\n"
            f"│\n"
            f"│  👤 *Name*      : `{name}`\n"
            f"│  🆔 *UID*       : `{target_uid}`\n"
            f"│  🌍 *Region*    : `{region.upper()}`\n"
            f"│\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│  🎯 *BR Rank*   : `{br_rank}`\n"
            f"│  📊 *BR Points* : `{br_points}`\n"
            f"│  🔫 *CS Rank*   : `{cs_rank}`\n"
            f"│  📊 *CS Points* : `{cs_points}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}")
    except Exception as e:
        logger.error(f"cmd_rank: {e}")
        _edit(wait, "⚠️ Could not parse rank data.")

# ─── OWNER COMMANDS ──────────────────────────────────────────────────────────

@bot.message_handler(commands=['remain'])
def cmd_remain(message):
    if message.from_user.id != OWNER_ID:
        return

    total  = len(like_tracker)
    reqs   = sum(u.get("used", 0) for u in like_tracker.values())
    lines  = [
        f"╭─「 📊 *DAILY USAGE* 」\n"
        f"│\n"
        f"│  👥 *Active Users* : `{total}`\n"
        f"│  📦 *Total Reqs*   : `{reqs}`\n"
        f"│  ⏱️ *Bot Uptime*   : `{get_uptime()}`\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━"
    ]
    if not like_tracker:
        lines.append("│  ❌ No usage yet today.")
    else:
        for u_id, data in like_tracker.items():
            lim  = get_daily_limit(u_id)
            used = data.get("used", 0)
            lstr = "∞" if lim > 1_000_000 else str(lim)
            rem  = "∞" if lim > 1_000_000 else str(max(0, lim - used))
            lines.append(f"│  👤 `{u_id}` ➜ `{used}/{lstr}` (left: `{rem}`)")
    lines.append("╰──────────────────────")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['users'])
def cmd_users(message):
    if message.from_user.id != OWNER_ID:
        return
    bot.reply_to(message,
        f"╭─「 👥 *USER STATS* 」\n"
        f"│\n"
        f"│  🗂️ *Total known* : `{len(broadcast_log)}`\n"
        f"│  📅 *Active today*: `{len(like_tracker)}`\n"
        f"│  🚫 *Banned*      : `{len(banned_users)}`\n"
        f"│\n"
        f"╰──────────────────────",
        parse_mode="Markdown")


@bot.message_handler(commands=['ban'])
def cmd_ban(message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        bot.reply_to(message, "Usage: `/ban <user_id>`", parse_mode="Markdown")
        return
    target = int(args[1])
    banned_users.add(target)
    bot.reply_to(message, f"✅ User `{target}` has been *banned*.", parse_mode="Markdown")


@bot.message_handler(commands=['unban'])
def cmd_unban(message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        bot.reply_to(message, "Usage: `/unban <user_id>`", parse_mode="Markdown")
        return
    target = int(args[1])
    banned_users.discard(target)
    bot.reply_to(message, f"✅ User `{target}` has been *unbanned*.", parse_mode="Markdown")


@bot.message_handler(commands=['addlimit'])
def cmd_addlimit(message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split()
    if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
        bot.reply_to(message, "Usage: `/addlimit <user_id> <amount>`", parse_mode="Markdown")
        return
    target, amount = int(args[1]), int(args[2])
    extra_limits[target] = extra_limits.get(target, 0) + amount
    new_total = 1 + extra_limits[target]
    bot.reply_to(message,
        f"✅ Added `{amount}` extra requests to `{target}`.\n"
        f"New daily limit: `{new_total}`",
        parse_mode="Markdown")


@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        bot.reply_to(message, "Usage: `/broadcast <your message>`", parse_mode="Markdown")
        return

    text      = args[1].strip()
    full_msg  = (
        f"📢 *BROADCAST MESSAGE*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"☠️ — {AUTHOR}"
    )

    sent_ok = sent_fail = 0
    targets = list(broadcast_log)

    status_msg = bot.reply_to(message, f"📡 Broadcasting to {len(targets)} users...")

    for user_id in targets:
        try:
            bot.send_message(user_id, full_msg, parse_mode="Markdown")
            sent_ok += 1
        except Exception:
            sent_fail += 1
        time.sleep(0.05)  # rate limit safety

    bot.edit_message_text(
        f"╭─「 📡 *BROADCAST DONE* 」\n"
        f"│\n"
        f"│  ✅ *Sent*    : `{sent_ok}`\n"
        f"│  ❌ *Failed*  : `{sent_fail}`\n"
        f"│  👥 *Total*   : `{len(targets)}`\n"
        f"│\n"
        f"╰──────────────────────",
        chat_id=status_msg.chat.id,
        message_id=status_msg.message_id,
        parse_mode="Markdown")

# ─── CALLBACKS ───────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)

    if call.data == "ping":
        t0 = time.time()
        ms = round((time.time() - t0) * 1000 + 12)
        bot.send_message(call.message.chat.id,
            f"╭─「 🏓 *PONG!* 」\n│\n│  ⚡ `{ms}ms` | ⏱️ `{get_uptime()}`\n│  🟢 Online | 🤖 v{BOT_VERSION}\n╰──────────────────────",
            parse_mode="Markdown")

    elif call.data == "stats":
        used, remaining, limit = get_usage(uid)
        _, rem_str = limit_display(limit, remaining)
        bot.send_message(call.message.chat.id,
            f"╭─「 📊 *YOUR STATS* 」\n│\n│  ✅ Used: `{used}` | 🎯 Left: `{rem_str}`\n│  🔄 Resets: `{reset_countdown()}`\n╰──────────────────────",
            parse_mode="Markdown")

    elif call.data == "help":
        cmd_help(call.message)

# ─── UNKNOWN COMMANDS ────────────────────────────────────────────────────────

KNOWN_CMDS = {'/start','/like','/help','/remain','/ping','/status',
              '/profile','/guild','/rank','/servertime','/about',
              '/broadcast','/ban','/unban','/addlimit','/users'}

@bot.message_handler(func=lambda m: True, content_types=['text'])
def fallback(message):
    broadcast_log.add(message.from_user.id)
    if message.text.startswith('/'):
        cmd = message.text.split()[0].lower().split('@')[0]
        if cmd not in KNOWN_CMDS:
            bot.reply_to(message,
                f"❓ Unknown command: `{cmd}`\n\nType /help to see all commands.",
                parse_mode="Markdown")

# ─── EDIT HELPER ─────────────────────────────────────────────────────────────

def _edit(msg, text, markup=None):
    try:
        bot.edit_message_text(
            text, chat_id=msg.chat.id, message_id=msg.message_id,
            reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(msg.chat.id, text, reply_markup=markup, parse_mode="Markdown")

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
