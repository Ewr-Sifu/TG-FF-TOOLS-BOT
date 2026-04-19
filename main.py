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

# ═══════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found!")
    sys.exit(1)

REQUIRED_CHANNELS = ["@sifat69backup"]
GROUP_JOIN_LINK    = "https://t.me/maybesifatx69"
OWNER_ID           = 8438269386
OWNER_USERNAME     = "@MaybeSifu"
YT_CHANNEL         = "https://youtube.com/@maybes1fu"
BOT_NAME           = "S1FAT LIKE BOT"
BOT_VERSION        = "1.0"
AUTHOR             = "SIFAT 💀"
API_BASE           = "" # your API url example:= https://ff-like-by-sifu.vercel.app

# Cost & rewards
LIKE_COST          = 20   # points per like
VISIT_COST         = 10   # points per visit
DAILY_REWARD       = 20   # daily points reward
VERIFY_REWARD      = 10   # daily verify bonus

# ═══════════════════════════════════════════════════
# IN-MEMORY STORES
# ═══════════════════════════════════════════════════
bot              = telebot.TeleBot(BOT_TOKEN)
banned_users     = set()
broadcast_log    = set()
bot_start_time   = datetime.utcnow()

# Points economy
points_balance   = {}   # {uid: int}
daily_last       = {}   # {uid: date}  — last /daily claim date
verify_last      = {}   # {uid: date}  — last /verify claim date

# Stats
likes_sent_total  = {}   # {uid: int}  — all-time likes sent
visits_sent_total = {}   # {uid: int}
monthly_likes     = {}   # {uid: int}  — resets 1st of each month
monthly_reset_on  = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

app = Flask(__name__)

# ═══════════════════════════════════════════════════
# BACKGROUND THREADS
# ═══════════════════════════════════════════════════

def background_tasks():
    global monthly_reset_on
    while True:
        try:
            now = datetime.utcnow()
            # Monthly leaderboard reset
            nxt_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now >= nxt_month and monthly_reset_on < nxt_month:
                monthly_likes.clear()
                monthly_reset_on = nxt_month
                logger.info("✅ Monthly leaderboard reset.")
            time.sleep(3600)  # check every hour
        except Exception as e:
            logger.error(f"background_tasks error: {e}")
            time.sleep(60)

threading.Thread(target=background_tasks, daemon=True).start()

# ═══════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════

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

def get_points(uid):
    if uid == OWNER_ID:
        return 999_999_999
    return points_balance.get(uid, 0)

def add_points(uid, amount):
    if uid == OWNER_ID:
        return
    points_balance[uid] = points_balance.get(uid, 0) + amount

def spend_points(uid, amount):
    if uid == OWNER_ID:
        return True
    bal = points_balance.get(uid, 0)
    if bal < amount:
        return False
    points_balance[uid] = bal - amount
    return True

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

def cooldown_left(last_date):
    """Returns hours:minutes until next claim, or None if ready."""
    if last_date is None:
        return None
    now  = datetime.utcnow()
    nxt  = datetime.combine(last_date, datetime.min.time()) + timedelta(days=1)
    if now >= nxt:
        return None
    diff = nxt - now
    h, rem = divmod(int(diff.total_seconds()), 3600)
    m, _   = divmod(rem, 60)
    return f"{h}h {m}m"

def api_get(endpoint, params):
    try:
        r = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=20)
        if r.status_code != 200:
            return {"error": f"Server returned {r.status_code}"}
        return r.json()
    except requests.exceptions.RequestException:
        return {"error": "API connection failed. Try again later."}
    except ValueError:
        return {"error": "Invalid API response."}

def _edit(msg, text, markup=None):
    try:
        bot.edit_message_text(text, chat_id=msg.chat.id, message_id=msg.message_id,
                              reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.send_message(msg.chat.id, text, reply_markup=markup, parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# BUTTON BUILDERS
# ═══════════════════════════════════════════════════

def join_markup():
    """Clean full-width buttons for unverified users."""
    mu = InlineKeyboardMarkup(row_width=1)
    for ch in REQUIRED_CHANNELS:
        mu.add(InlineKeyboardButton(f"📢  Join Telegram Channel", url=f"https://t.me/{ch.strip('@')}"))
    mu.add(InlineKeyboardButton("🔴  Subscribe on YouTube", url=YT_CHANNEL))
    return mu

def main_menu_markup():
    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("📖  Help",        callback_data="help"),
        InlineKeyboardButton("💰  Balance",      callback_data="balance"),
    )
    mu.add(
        InlineKeyboardButton("🏓  Ping",         callback_data="ping"),
        InlineKeyboardButton("🏆  Leaderboard",  callback_data="leaderboard"),
    )
    mu.add(
        InlineKeyboardButton("💬  Official Group", url=GROUP_JOIN_LINK),
    )
    mu.add(
        InlineKeyboardButton("📢  Channel",      url=f"https://t.me/{REQUIRED_CHANNELS[0].strip('@')}"),
        InlineKeyboardButton("🔴  YouTube",      url=YT_CHANNEL),
    )
    return mu

def help_markup():
    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("💰  Balance",       callback_data="balance"),
        InlineKeyboardButton("🏆  Leaderboard",   callback_data="leaderboard"),
    )
    mu.add(
        InlineKeyboardButton("💬  Support",        url=f"https://t.me/{OWNER_USERNAME.strip('@')}"),
    )
    return mu

def result_markup():
    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("💰  My Balance",    callback_data="balance"),
        InlineKeyboardButton("🏆  Leaderboard",   callback_data="leaderboard"),
    )
    mu.add(InlineKeyboardButton("💬  Support",    url=f"https://t.me/{OWNER_USERNAME.strip('@')}"))
    return mu

# ═══════════════════════════════════════════════════
# FLASK
# ═══════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════

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
            f"╭─「 🔒 *ACCESS REQUIRED* 」\n"
            f"│\n"
            f"│  Hey *{name}!* 👋\n"
            f"│  Join our channel & subscribe\n"
            f"│  to unlock the bot.\n"
            f"│\n"
            f"╰─ Tap below then send /start 🐣",
            reply_markup=join_markup(), parse_mode="Markdown")
        return

    pts  = get_points(uid)
    pts_display = "♾️ Unlimited" if uid == OWNER_ID else str(pts)
    total_likes = likes_sent_total.get(uid, 0)

    bot.reply_to(message,
        f"╭─「 🔥 *{BOT_NAME}* 」\n"
        f"│\n"
        f"│  😺 Welcome, *{name}!*\n"
        f"│\n"
        f"│  🗿 *Author*   : {AUTHOR}\n"
        f"│  🤖 *Version*  : v{BOT_VERSION}\n"
        f"│  ⚡ *Uptime*   : `{get_uptime()}`\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━\n"
        f"│  💰 Points    : `{pts_display}`\n"
        f"│  ❤️ Total Likes: `{total_likes}`\n"
        f"│  🔄 Daily Reset: `{reset_countdown()}`\n"
        f"│\n"
        f"│  📌 `/like bd 3195799949` (costs {LIKE_COST}pts)\n"
        f"│  🎁 `/daily` to claim free points!\n"
        f"│\n"
        f"╰─ ☠️ {AUTHOR}",
        reply_markup=main_menu_markup(), parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /help
# ═══════════════════════════════════════════════════

TOTAL_COMMANDS = 18

@bot.message_handler(commands=['help'])
def cmd_help(message):
    uid = message.from_user.id
    broadcast_log.add(uid)

    if uid != OWNER_ID and not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return

    owner_section = ""
    if uid == OWNER_ID:
        owner_section = (
            "\n`╭─「 👑 OWNER ONLY 」`\n"
            "`├⊙` `/broadcast`  `├⊙` `/remain`\n"
            "`├⊙` `/addpoints`  `├⊙` `/ban`\n"
            "`├⊙` `/unban`      `├⊙` `/users`\n"
            "`╰──────────────────────`"
        )

    text = (
        f"╭─「 🤖 *{BOT_NAME}* 」\n"
        f"│  ☠️ Author   : {AUTHOR}\n"
        f"│  📌 Version  : v{BOT_VERSION}\n"
        f"│  📦 Commands : {TOTAL_COMMANDS}+\n"
        f"╰──────────────────────\n"
        "\n`╭─「 🎮 FREE FIRE TOOLS 」`\n"
        "`├⊙` `/like`      `├⊙` `/info`\n"
        "`├⊙` `/visit`     `├⊙` `/profile`\n"
        "`├⊙` `/rank`      `├⊙` `/guild`\n"
        "`╰──────────────────────`\n"
        "\n`╭─「 💰 ECONOMY 」`\n"
        "`├⊙` `/daily`     `├⊙` `/verify`\n"
        "`├⊙` `/balance`   `├⊙` `/leaderboard`\n"
        "`╰──────────────────────`\n"
        "\n`╭─「 📊 USER TOOLS 」`\n"
        "`├⊙` `/status`    `├⊙` `/ping`\n"
        "`├⊙` `/servertime``├⊙` `/about`\n"
        "`╰──────────────────────`\n"
        f"{owner_section}\n"
        f"\n💰 Like costs `{LIKE_COST} pts` | *Visit costs* `{VISIT_COST} pts`\n"
        f"🎁 Daily reward `{DAILY_REWARD} pts` | *Verify bonus* `{VERIFY_REWARD} pts`\n\n"
        f"🌍 Regions: `bd` `ind` `sg` `br` `ru` `us` `th` `id`\n"
        f"📌 Example: `/like bd 3195799949`\n\n"
        f"💬 Support: {OWNER_USERNAME}"
    )
    bot.reply_to(message, text, reply_markup=help_markup(), parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /ping
# ═══════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════
# /daily  — claim 20 pts once per 24h
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['daily'])
def cmd_daily(message):
    uid = message.from_user.id
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return
    if not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return

    today     = datetime.utcnow().date()
    last_date = daily_last.get(uid)
    cd        = cooldown_left(last_date)

    if cd:
        bot.reply_to(message,
            f"╭─「 ⏳ DAILY COOLDOWN 」\n"
            f"│\n"
            f"│  You already claimed today!\n"
            f"│\n"
            f"│  🔄 *Next claim in* : `{cd}`\n"
            f"│  💰 *Current pts*   : `{get_points(uid)}`\n"
            f"│\n"
            f"╰─ Come back tomorrow! 🎁",
            parse_mode="Markdown")
        return

    daily_last[uid] = today
    add_points(uid, DAILY_REWARD)
    new_bal = get_points(uid)
    total_likes = likes_sent_total.get(uid, 0)

    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("💰  My Balance",   callback_data="balance"),
        InlineKeyboardButton("🏆  Leaderboard",  callback_data="leaderboard"),
    )

    bot.reply_to(message,
        f"╭─「 🎁 REWARD CLAIMED! 」\n"
        f"│\n"
        f"│  ✅ +{DAILY_REWARD} Points added!\n"
        f"│\n"
        f"│  💰 New Balance : `{new_bal} pts`\n"
        f"│  ❤️ Total Likes : `{total_likes}`\n"
        f"│\n"
        f"│  💡 Use `/like bd <uid>` to spend\n"
        f"│     your points! (costs {LIKE_COST} pts)\n"
        f"│\n"
        f"╰─ ☠️ {AUTHOR}",
        reply_markup=mu, parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /verify  — daily channel verify + bonus pts
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['verify'])
def cmd_verify(message):
    uid = message.from_user.id
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return

    today     = datetime.utcnow().date()
    last_date = verify_last.get(uid)
    cd        = cooldown_left(last_date)

    if cd:
        bot.reply_to(message,
            f"╭─「 ⏳ VERIFY COOLDOWN 」\n"
            f"│\n"
            f"│  Already verified today!\n"
            f"│\n"
            f"│  🔄 *Next verify in* : `{cd}`\n"
            f"│  💰 *Current pts*    : `{get_points(uid)}`\n"
            f"│\n"
            f"╰──────────────────────",
            parse_mode="Markdown")
        return

    if not is_member(uid):
        bot.reply_to(message,
            f"╭─「 ❌ VERIFY FAILED 」\n"
            f"│\n"
            f"│  You left our channel!\n"
            f"│  Re-join to verify and\n"
            f"│  earn your {VERIFY_REWARD} bonus points.\n"
            f"│\n"
            f"╰─ Tap below to rejoin 👇",
            reply_markup=join_markup(), parse_mode="Markdown")
        return

    verify_last[uid] = today
    add_points(uid, VERIFY_REWARD)
    new_bal = get_points(uid)

    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("🎁  Daily Reward",  callback_data="daily_remind"),
        InlineKeyboardButton("💰  My Balance",    callback_data="balance"),
    )

    bot.reply_to(message,
        f"╭─「 ✅ VERIFIED! 」\n"
        f"│\n"
        f"│  Channel membership confirmed!\n"
        f"│  ✨ +{VERIFY_REWARD} Bonus Points added!\n"
        f"│\n"
        f"│  💰 New Balance : `{new_bal} pts`\n"
        f"│\n"
        f"│  🎁 Also claim `/daily` for\n"
        f"│     +{DAILY_REWARD} more points!\n"
        f"│\n"
        f"╰─ ☠️ {AUTHOR}",
        reply_markup=mu, parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /balance  — check points & stats
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['balance'])
def cmd_balance(message):
    uid = message.from_user.id
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return
    if not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return

    pts         = get_points(uid)
    total_likes = likes_sent_total.get(uid, 0)
    m_likes     = monthly_likes.get(uid, 0)
    total_visits= visits_sent_total.get(uid, 0)
    pts_display = "♾️ Unlimited" if uid == OWNER_ID else str(pts)

    can_like    = "✅ Yes" if pts >= LIKE_COST or uid == OWNER_ID else f"❌ Need {LIKE_COST - pts} more pts"
    daily_cd    = cooldown_left(daily_last.get(uid))
    verify_cd   = cooldown_left(verify_last.get(uid))
    daily_str   = f"Ready 🎁" if not daily_cd else f"⏳ {daily_cd}"
    verify_str  = f"Ready ✅" if not verify_cd else f"⏳ {verify_cd}"

    mu = InlineKeyboardMarkup(row_width=2)
    mu.add(
        InlineKeyboardButton("🎁  Claim Daily",   callback_data="daily_remind"),
        InlineKeyboardButton("🏆  Leaderboard",   callback_data="leaderboard"),
    )

    bot.reply_to(message,
        f"╭─「 💰 YOUR BALANCE 」\n"
        f"│\n"
        f"│  👤 User ID      : `{uid}`\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━\n"
        f"│  💰 Points       : `{pts_display}`\n"
        f"│  ❤️ Can Send Like: {can_like}\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━\n"
        f"│  📊 All-Time Likes : `{total_likes}`\n"
        f"│  📅 Monthly Likes  : `{m_likes}`\n"
        f"│  👁️ Total Visits   : `{total_visits}`\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━\n"
        f"│  🎁 Daily  : {daily_str}\n"
        f"│  ✅ Verify : {verify_str}\n"
        f"│\n"
        f"╰─ ☠️ {AUTHOR}",
        reply_markup=mu, parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /leaderboard  — monthly top 10
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['leaderboard'])
def cmd_leaderboard(message):
    uid = message.from_user.id
    broadcast_log.add(uid)

    if not is_member(uid) and uid != OWNER_ID:
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup())
        return

    now       = datetime.utcnow()
    month_str = now.strftime("%B %Y")

    # Sort by monthly likes
    board = sorted(monthly_likes.items(), key=lambda x: x[1], reverse=True)[:10]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    lines = [
        f"╭─「 🏆 MONTHLY LEADERBOARD 」\n"
        f"│  📅 {month_str}\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━"
    ]

    if not board:
        lines.append("│  ❌ No data yet this month.")
    else:
        for i, (u_id, count) in enumerate(board):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            marker = " 👈 You" if u_id == uid else ""
            lines.append(f"│  {medal} `{u_id}` ➜ `{count}` likes{marker}")

    user_rank = None
    for i, (u_id, _) in enumerate(sorted(monthly_likes.items(), key=lambda x: x[1], reverse=True)):
        if u_id == uid:
            user_rank = i + 1
            break

    lines.append(f"│  ━━━━━━━━━━━━━━━━━━")
    if user_rank:
        lines.append(f"│  📍 Your Rank : `#{user_rank}` | Likes: `{monthly_likes.get(uid, 0)}`")
    lines.append(f"╰─ 🔄 Resets on 1st of each month")

    mu = InlineKeyboardMarkup()
    mu.add(InlineKeyboardButton("💰  My Balance", callback_data="balance"))

    bot.reply_to(message, "\n".join(lines), reply_markup=mu, parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /status
# ═══════════════════════════════════════════════════

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

    pts         = get_points(uid)
    pts_display = "♾️" if uid == OWNER_ID else str(pts)
    likes_can   = pts // LIKE_COST if uid != OWNER_ID else 999

    bar_size  = 10
    filled    = min(bar_size, pts // LIKE_COST) if uid != OWNER_ID else bar_size
    bar       = "🟩" * filled + "⬜" * (bar_size - filled)

    bot.reply_to(message,
        f"╭─「 📊 YOUR STATUS 」\n"
        f"│\n"
        f"│  👤 User ID     : `{uid}`\n"
        f"│\n"
        f"│  💰 Points      : `{pts_display}`\n"
        f"│  ❤️ Likes left  : `{likes_can}`\n"
        f"│\n"
        f"│  {bar}\n"
        f"│\n"
        f"│  🔄 Daily reset : `{reset_countdown()}`\n"
        f"│\n"
        f"╰─ 💬 {OWNER_USERNAME}",
        parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /servertime
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['servertime'])
def cmd_servertime(message):
    broadcast_log.add(message.from_user.id)
    now = datetime.utcnow()
    bot.reply_to(message,
        f"╭─「 🕐 SERVER TIME 」\n"
        f"│\n"
        f"│  🌐 UTC Time   : `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"│  ⏱️ Uptime     : `{get_uptime()}`\n"
        f"│  🔄 Next Reset : `{reset_countdown()}`\n"
        f"│\n"
        f"╰──────────────────────",
        parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /about
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['about'])
def cmd_about(message):
    broadcast_log.add(message.from_user.id)
    bot.reply_to(message,
        f"╭─「 ℹ️ ABOUT BOT 」\n"
        f"│\n"
        f"│  🤖 Bot      : {BOT_NAME}\n"
        f"│  ☠️ Author   : {AUTHOR}\n"
        f"│  📌 Version  : v{BOT_VERSION}\n"
        f"│  💬 Contact  : {OWNER_USERNAME}\n"
        f"│  ⏱️ Uptime   : `{get_uptime()}`\n"
        f"│\n"
        f"│  Built for Free Fire players.\n"
        f"│  Send likes, check profiles,\n"
        f"│  earn points & climb the board!\n"
        f"│\n"
        f"╰──────────────────────",
        parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /like  — costs LIKE_COST points
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['like'])
def cmd_like(message):
    uid  = message.from_user.id
    args = message.text.split()
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 *You are banned.*", parse_mode="Markdown")
        return

    if message.chat.type == "private" and uid != OWNER_ID:
        mu = InlineKeyboardMarkup()
        mu.add(InlineKeyboardButton("💬  Official Group", url=GROUP_JOIN_LINK))
        bot.reply_to(message,
            "╭─「 ⚠️ GROUP ONLY 」\n"
            "│\n"
            "│  This command only works\n"
            "│  inside a group chat.\n"
            "│\n"
            "╰─ Join the group 👇",
            reply_markup=mu, parse_mode="Markdown")
        return

    if not is_member(uid):
        bot.reply_to(message, "❌ *Join our channel first!*", reply_markup=join_markup(), parse_mode="Markdown")
        return

    if len(args) != 3:
        bot.reply_to(message,
            "╭─「 ❌ WRONG FORMAT 」\n"
            "│\n"
            "│  `/like <region> <uid>`\n"
            "│\n"
            "│  🌍 Example:\n"
            "│  `/like bd 3195799949`\n"
            "│\n"
            f"│  💰 Costs: `{LIKE_COST} points`\n"
            "╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].lower(), args[2]
    if not region.isalpha() or not target_uid.isdigit():
        bot.reply_to(message, "⚠️ Region = letters only, UID = numbers only.\nExample: `/like bd 3195799949`", parse_mode="Markdown")
        return

    threading.Thread(target=_process_like, args=(message, region, target_uid)).start()

def _process_like(message, region, target_uid):
    uid = message.from_user.id

    if not spend_points(uid, LIKE_COST):
        pts = get_points(uid)
        mu  = InlineKeyboardMarkup(row_width=2)
        mu.add(
            InlineKeyboardButton("🎁  Claim Daily",  callback_data="daily_remind"),
            InlineKeyboardButton("✅  Verify",        callback_data="verify_remind"),
        )
        bot.reply_to(message,
            f"╭─「 💸 INSUFFICIENT POINTS 」\n"
            f"│\n"
            f"│  You need `{LIKE_COST} pts` to send a like.\n"
            f"│  You have `{pts} pts`.\n"
            f"│\n"
            f"│  💡 Earn points:\n"
            f"│  🎁 `/daily`  → +{DAILY_REWARD} pts\n"
            f"│  ✅ `/verify` → +{VERIFY_REWARD} pts\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}",
            reply_markup=mu, parse_mode="Markdown")
        return

    wait_msg = bot.reply_to(message,
        f"╭─「 ⏳ PROCESSING... 」\n"
        f"│\n"
        f"│  🔍 UID    : `{target_uid}`\n"
        f"│  🌍 Region : `{region.upper()}`\n"
        f"│\n"
        f"│  ⚡ _Sending likes..._\n"
        f"╰──────────────────────",
        parse_mode="Markdown")

    resp = api_get("like", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        add_points(uid, LIKE_COST)  # refund on API error
        _edit(wait_msg,
            f"╭─「 ❌ API ERROR 」\n"
            f"│\n"
            f"│  ⚠️ `{resp['error']}`\n"
            f"│  💰 Points refunded!\n"
            f"│\n"
            f"╰─ 💬 {OWNER_USERNAME}")
        return

    if not isinstance(resp, dict) or resp.get("status") != 1:
        add_points(uid, LIKE_COST)  # refund on failed like
        _edit(wait_msg,
            f"╭─「 ❌ REQUEST FAILED 」\n"
            f"│\n"
            f"│  UID has max likes for today.\n"
            f"│  💰 Points refunded!\n"
            f"│\n"
            f"│  💡 Try a different UID or\n"
            f"│     come back after 24h.\n"
            f"│\n"
            f"╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        p_uid    = str(resp.get("UID", target_uid)).strip()
        p_name   = resp.get("PlayerNickname", "N/A")
        p_region = str(resp.get("Region", region.upper()))
        l_before = str(resp.get("LikesbeforeCommand", "N/A"))
        l_after  = str(resp.get("LikesafterCommand", "N/A"))
        l_given  = str(resp.get("LikesGivenByAPI", "N/A"))

        # Update stats
        likes_sent_total[uid]  = likes_sent_total.get(uid, 0) + 1
        monthly_likes[uid]     = monthly_likes.get(uid, 0) + 1
        new_bal = get_points(uid)

        _edit(wait_msg,
            f"╭─「 ✅ *LIKES SENT!* 」\n"
            f"│\n"
            f"│  👤 Name    : `{p_name}`\n"
            f"│  🆔 UID     : `{p_uid}`\n"
            f"│  🌍 Region  : `{p_region}`\n"
            f"│\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│  💔 Before  : `{l_before}`\n"
            f"│  📈 Added   : `+{l_given}`\n"
            f"│  💖 Total   : `{l_after}`\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│\n"
            f"│  💰 Points Left : `{new_bal}`\n"
            f"│  ❤️ Total Likes : `{likes_sent_total.get(uid, 0)}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}",
            markup=result_markup())
    except Exception as e:
        logger.error(f"_process_like: {e}")
        bot.reply_to(message, "⚠️ Likes sent but couldn't decode the response.")

# ═══════════════════════════════════════════════════
# /info
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['info'])
def cmd_info(message):
    uid  = message.from_user.id
    args = message.text.split()
    broadcast_log.add(uid)

    if uid in banned_users:
        bot.reply_to(message, "🚫 You are banned.", parse_mode="Markdown")
        return
    if not is_member(uid):
        bot.reply_to(message, "❌ Join our channel first!", reply_markup=join_markup(), parse_mode="Markdown")
        return
    if len(args) != 3 or not args[1].isalpha() or not args[2].isdigit():
        bot.reply_to(message,
            "╭─「 ❌ WRONG FORMAT 」\n│\n"
            "│  `/info <region> <uid>`\n│\n"
            "│  Example: `/info bd 3195799949`\n"
            "╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].upper(), args[2]
    wait = bot.reply_to(message, "⏳ _Fetching player info..._", parse_mode="Markdown")
    resp = api_get("info", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        _edit(wait, f"╭─「 ❌ API ERROR 」\n│\n│  ⚠️ `{resp['error']}`\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        name    = resp.get("PlayerNickname") or resp.get("nickname", "N/A")
        level   = resp.get("Level") or resp.get("level", "N/A")
        likes   = resp.get("Likes") or resp.get("likes", "N/A")
        exp     = resp.get("Exp") or resp.get("exp", "N/A")
        br_rank = resp.get("BRRank") or resp.get("brRank", "N/A")
        cs_rank = resp.get("CSRank") or resp.get("csRank", "N/A")
        guild   = resp.get("GuildName") or resp.get("guildName", "—")
        reg     = resp.get("Region") or region

        mu = InlineKeyboardMarkup(row_width=2)
        mu.add(
            InlineKeyboardButton("❤️  Send Likes",  callback_data=f"like_{region}_{target_uid}"),
            InlineKeyboardButton("💬  Support",      url=f"https://t.me/{OWNER_USERNAME.strip('@')}"),
        )

        _edit(wait,
            f"╭─「 🎮 PLAYER INFO 」\n"
            f"│\n"
            f"│  👤 Name    : `{name}`\n"
            f"│  🆔 UID     : `{target_uid}`\n"
            f"│  🌍 Region  : `{reg}`\n"
            f"│\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│  ⚔️ Level   : `{level}`\n"
            f"│  ✨ EXP     : `{exp}`\n"
            f"│  ❤️ Likes   : `{likes}`\n"
            f"│\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│  🏆 BR Rank : `{br_rank}`\n"
            f"│  🔫 CS Rank : `{cs_rank}`\n"
            f"│  🏰 Guild   : `{guild}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}",
            markup=mu)
    except Exception as e:
        logger.error(f"cmd_info: {e}")
        _edit(wait, "⚠️ Could not parse player info. Check UID and region.")

# ═══════════════════════════════════════════════════
# /visit  — costs VISIT_COST points
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['visit'])
def cmd_visit(message):
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
            "╭─「 ❌ WRONG FORMAT 」\n│\n"
            "│  `/visit <region> <uid>`\n│\n"
            f"│  💰 Costs: `{VISIT_COST} points`\n│\n"
            "│  Example: `/visit bd 3195799949`\n"
            "╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].lower(), args[2]
    threading.Thread(target=_process_visit, args=(message, region, target_uid)).start()

def _process_visit(message, region, target_uid):
    uid = message.from_user.id

    if not spend_points(uid, VISIT_COST):
        pts = get_points(uid)
        bot.reply_to(message,
            f"╭─「 💸 INSUFFICIENT POINTS 」\n"
            f"│\n"
            f"│  Need `{VISIT_COST} pts` to send a visit.\n"
            f"│  You have `{pts} pts`.\n"
            f"│\n"
            f"│  🎁 `/daily` → +{DAILY_REWARD} pts\n"
            f"│  ✅ `/verify` → +{VERIFY_REWARD} pts\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}",
            parse_mode="Markdown")
        return

    wait = bot.reply_to(message,
        f"╭─「 ⏳ SENDING VISIT... 」\n"
        f"│\n"
        f"│  🔍 UID    : `{target_uid}`\n"
        f"│  🌍 Region : `{region.upper()}`\n"
        f"│\n"
        f"╰──────────────────────",
        parse_mode="Markdown")

    resp = api_get("visit", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        add_points(uid, VISIT_COST)  # refund
        _edit(wait,
            f"╭─「 ❌ API ERROR 」\n│\n│  ⚠️ `{resp['error']}`\n│  💰 Points refunded!\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        p_name   = resp.get("PlayerNickname") or resp.get("nickname", "N/A")
        p_region = resp.get("Region") or region.upper()
        visits_sent_total[uid] = visits_sent_total.get(uid, 0) + 1

        _edit(wait,
            f"╭─「 ✅ VISIT SENT! 」\n"
            f"│\n"
            f"│  👤 Name    : `{p_name}`\n"
            f"│  🆔 UID     : `{target_uid}`\n"
            f"│  🌍 Region  : `{p_region}`\n"
            f"│\n"
            f"│  💰 Points Left    : `{get_points(uid)}`\n"
            f"│  👁️ Total Visits   : `{visits_sent_total.get(uid, 0)}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}")
    except Exception as e:
        logger.error(f"_process_visit: {e}")
        _edit(wait, "⚠️ Visit sent but couldn't decode the response.")

# ═══════════════════════════════════════════════════
# /profile
# ═══════════════════════════════════════════════════

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
            "╭─「 ❌ WRONG FORMAT 」\n│\n│  `/profile <region> <uid>`\n│\n│  Example: `/profile bd 123456789`\n╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].lower(), args[2]
    wait = bot.reply_to(message, "⏳ _Fetching profile..._", parse_mode="Markdown")
    resp = api_get("playerinfo", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        _edit(wait, f"╭─「 ❌ API ERROR 」\n│\n│  ⚠️ `{resp['error']}`\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        name   = resp.get("PlayerNickname") or resp.get("nickname", "N/A")
        level  = resp.get("Level") or resp.get("level", "N/A")
        likes  = resp.get("Likes") or resp.get("likes", "N/A")
        rank   = resp.get("Rank") or resp.get("rank", "N/A")
        guild  = resp.get("GuildName") or resp.get("guildName", "N/A")
        reg    = resp.get("Region") or region.upper()

        _edit(wait,
            f"╭─「 👤 PLAYER PROFILE 」\n"
            f"│\n"
            f"│  👤 Name   : `{name}`\n"
            f"│  🆔 UID    : `{target_uid}`\n"
            f"│  🌍 Region : `{reg}`\n"
            f"│  ⚔️ Level  : `{level}`\n"
            f"│  ❤️ Likes  : `{likes}`\n"
            f"│  🏆 Rank   : `{rank}`\n"
            f"│  🏰 Guild  : `{guild}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}")
    except Exception as e:
        logger.error(f"cmd_profile: {e}")
        _edit(wait, "⚠️ Could not parse profile data.")

# ═══════════════════════════════════════════════════
# /guild
# ═══════════════════════════════════════════════════

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
            "╭─「 ❌ WRONG FORMAT 」\n│\n│  `/guild <region> <guild_id>`\n│\n│  Example: `/guild bd 3001234567`\n╰──────────────────────",
            parse_mode="Markdown")
        return

    region, guild_id = args[1].lower(), args[2]
    wait = bot.reply_to(message, "⏳ _Fetching guild info..._", parse_mode="Markdown")
    resp = api_get("guild", {"id": guild_id, "server_name": region})

    if "error" in resp:
        _edit(wait, f"╭─「 ❌ API ERROR 」\n│\n│  ⚠️ `{resp['error']}`\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        g_name   = resp.get("GuildName") or resp.get("name", "N/A")
        g_level  = resp.get("GuildLevel") or resp.get("level", "N/A")
        g_cap    = resp.get("GuildCapacity") or resp.get("capacity", "N/A")
        g_mem    = resp.get("GuildMembers") or resp.get("members", "N/A")
        g_leader = resp.get("LeaderNickname") or resp.get("leader", "N/A")
        g_score  = resp.get("GuildScore") or resp.get("score", "N/A")

        _edit(wait,
            f"╭─「 🏰 GUILD INFO 」\n"
            f"│\n"
            f"│  🆔 Guild ID : `{guild_id}`\n"
            f"│  🏰 Name     : `{g_name}`\n"
            f"│  🌍 Region   : `{region.upper()}`\n"
            f"│  ⭐ Level    : `{g_level}`\n"
            f"│  👥 Members  : `{g_mem}/{g_cap}`\n"
            f"│  👑 Leader   : `{g_leader}`\n"
            f"│  🏆 Score    : `{g_score}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}")
    except Exception as e:
        logger.error(f"cmd_guild: {e}")
        _edit(wait, "⚠️ Could not parse guild data.")

# ═══════════════════════════════════════════════════
# /rank
# ═══════════════════════════════════════════════════

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
            "╭─「 ❌ WRONG FORMAT 」\n│\n│  `/rank <region> <uid>`\n│\n│  Example: `/rank bd 123456789`\n╰──────────────────────",
            parse_mode="Markdown")
        return

    region, target_uid = args[1].lower(), args[2]
    wait = bot.reply_to(message, "⏳ _Checking rank..._", parse_mode="Markdown")
    resp = api_get("playerinfo", {"uid": target_uid, "server_name": region})

    if "error" in resp:
        _edit(wait, f"╭─「 ❌ *API ERROR* 」\n│\n│  ⚠️ `{resp['error']}`\n╰─ 💬 {OWNER_USERNAME}")
        return

    try:
        name      = resp.get("PlayerNickname") or resp.get("nickname", "N/A")
        br_rank   = resp.get("BRRank") or resp.get("brRank", "N/A")
        cs_rank   = resp.get("CSRank") or resp.get("csRank", "N/A")
        br_points = resp.get("BRRankPoints") or resp.get("brPoints", "N/A")
        cs_points = resp.get("CSRankPoints") or resp.get("csPoints", "N/A")

        _edit(wait,
            f"╭─「 🏆 RANK INFO 」\n"
            f"│\n"
            f"│  👤 Name      : `{name}`\n"
            f"│  🆔 UID       : `{target_uid}`\n"
            f"│  🌍 Region    : `{region.upper()}`\n"
            f"│\n"
            f"│  ━━━━━━━━━━━━━━━━━━\n"
            f"│  🎯 BR Rank   : `{br_rank}`\n"
            f"│  📊 BR Points : `{br_points}`\n"
            f"│  🔫 CS Rank   : `{cs_rank}`\n"
            f"│  📊 CS Points : `{cs_points}`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}")
    except Exception as e:
        logger.error(f"cmd_rank: {e}")
        _edit(wait, "⚠️ Could not parse rank data.")

# ═══════════════════════════════════════════════════
# OWNER COMMANDS
# ═══════════════════════════════════════════════════

@bot.message_handler(commands=['remain'])
def cmd_remain(message):
    if message.from_user.id != OWNER_ID:
        return
    total = len(points_balance)
    lines = [
        f"╭─「 📊 USAGE STATS 」\n"
        f"│  👥 Users with points: `{total}`\n"
        f"│  ⏱️ Uptime           : `{get_uptime()}`\n"
        f"│\n"
        f"│  ━━━━━━━━━━━━━━━━━━"
    ]
    if not points_balance:
        lines.append("│  ❌ No data yet.")
    else:
        for u_id, pts in sorted(points_balance.items(), key=lambda x: x[1], reverse=True):
            sent = likes_sent_total.get(u_id, 0)
            lines.append(f"│  👤 `{u_id}` ➜ `{pts} pts` | ❤️ `{sent} likes`")
    lines.append("╰──────────────────────")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=['users'])
def cmd_users(message):
    if message.from_user.id != OWNER_ID:
        return
    bot.reply_to(message,
        f"╭─「 👥 USER STATS 」\n"
        f"│\n"
        f"│  🗂️ Known users   : `{len(broadcast_log)}`\n"
        f"│  💰 Have points   : `{len(points_balance)}`\n"
        f"│  🚫 Banned        : `{len(banned_users)}`\n"
        f"│  🏆 On leaderboard: `{len(monthly_likes)}`\n"
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


@bot.message_handler(commands=['addpoints'])
def cmd_addpoints(message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split()
    if len(args) != 3 or not args[1].isdigit() or not args[2].isdigit():
        bot.reply_to(message, "Usage: `/addpoints <user_id> <amount>`", parse_mode="Markdown")
        return
    target, amount = int(args[1]), int(args[2])
    add_points(target, amount)
    new_bal = get_points(target)
    bot.reply_to(message,
        f"╭─「 ✅ POINTS ADDED 」\n"
        f"│\n"
        f"│  👤 User   : `{target}`\n"
        f"│  ➕ Added  : `{amount} pts`\n"
        f"│  💰 Balance: `{new_bal} pts`\n"
        f"│\n"
        f"╰──────────────────────",
        parse_mode="Markdown")
    try:
        bot.send_message(target,
            f"╭─「 🎁 POINTS RECEIVED! 」\n"
            f"│\n"
            f"│  👑 Admin sent you `{amount}` pts!\n"
            f"│  💰 New Balance : `{new_bal} pts`\n"
            f"│\n"
            f"╰─ ☠️ {AUTHOR}",
            parse_mode="Markdown")
    except Exception:
        pass


@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        bot.reply_to(message, "Usage: `/broadcast <message>`", parse_mode="Markdown")
        return

    text     = args[1].strip()
    full_msg = (
        f"📢 ANNOUNCEMENT\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"☠️ — {AUTHOR}"
    )

    sent_ok = sent_fail = 0
    targets = list(broadcast_log)
    status  = bot.reply_to(message, f"📡 Broadcasting to {len(targets)} users...")

    for user_id in targets:
        try:
            bot.send_message(user_id, full_msg, parse_mode="Markdown")
            sent_ok += 1
        except Exception:
            sent_fail += 1
        time.sleep(0.05)

    bot.edit_message_text(
        f"╭─「 📡 BROADCAST DONE 」\n"
        f"│\n"
        f"│  ✅ Sent   : `{sent_ok}`\n"
        f"│  ❌ Failed : `{sent_fail}`\n"
        f"│  👥 Total  : `{len(targets)}`\n"
        f"│\n"
        f"╰──────────────────────",
        chat_id=status.chat.id, message_id=status.message_id, parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# CALLBACK QUERIES
# ═══════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)

    if call.data == "ping":
        t0 = time.time()
        ms = round((time.time() - t0) * 1000 + 12)
        bot.send_message(call.message.chat.id,
            f"╭─「 🏓 PONG! 」\n│\n│  ⚡ `{ms}ms` | ⏱️ `{get_uptime()}`\n│  🟢 Online | 🤖 v{BOT_VERSION}\n╰──────────────────────",
            parse_mode="Markdown")

    elif call.data == "balance":
        pts = get_points(uid)
        pts_display = "♾️ Unlimited" if uid == OWNER_ID else str(pts)
        total_likes = likes_sent_total.get(uid, 0)
        m_likes     = monthly_likes.get(uid, 0)
        bot.send_message(call.message.chat.id,
            f"╭─「 💰 YOUR BALANCE 」\n"
            f"│\n"
            f"│  💰 Points       : `{pts_display}`\n"
            f"│  ❤️ Total Likes  : `{total_likes}`\n"
            f"│  📅 Monthly Likes: `{m_likes}`\n"
            f"│  🔄 Reset in     : `{reset_countdown()}`\n"
            f"│\n"
            f"╰─ 🎁 `/daily` to earn more!",
            parse_mode="Markdown")

    elif call.data == "leaderboard":
        board = sorted(monthly_likes.items(), key=lambda x: x[1], reverse=True)[:5]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        now    = datetime.utcnow()
        lines  = [f"╭─「 🏆 TOP 5 — {now.strftime('%B')} 」\n│"]
        if not board:
            lines.append("│  ❌ No entries yet.")
        else:
            for i, (u_id, count) in enumerate(board):
                marker = " 👈" if u_id == uid else ""
                lines.append(f"│  {medals[i]} `{u_id}` ➜ `{count}` ❤️{marker}")
        lines.append("╰──────────────────────")
        bot.send_message(call.message.chat.id, "\n".join(lines), parse_mode="Markdown")

    elif call.data == "help":
        cmd_help(call.message)

    elif call.data == "daily_remind":
        bot.send_message(call.message.chat.id,
            f"🎁 Use `/daily` to claim your `{DAILY_REWARD}` free points!", parse_mode="Markdown")

    elif call.data == "verify_remind":
        bot.send_message(call.message.chat.id,
            f"✅ Use `/verify` to get `{VERIFY_REWARD}` bonus points!", parse_mode="Markdown")

    elif call.data.startswith("like_"):
        parts = call.data.split("_", 2)
        if len(parts) == 3:
            _, region, target_uid = parts
            if uid in banned_users:
                bot.answer_callback_query(call.id, "🚫 You are banned.", show_alert=True)
                return
            if not is_member(uid):
                bot.answer_callback_query(call.id, "❌ Join our channel first!", show_alert=True)
                return
            pts = get_points(uid)
            if pts < LIKE_COST and uid != OWNER_ID:
                bot.answer_callback_query(call.id, f"❌ Need {LIKE_COST} pts. Use /daily first!", show_alert=True)
                return
            bot.answer_callback_query(call.id, "⏳ Sending likes...")
            threading.Thread(target=_process_like, args=(call.message, region.lower(), target_uid)).start()

# ═══════════════════════════════════════════════════
# UNKNOWN COMMANDS
# ═══════════════════════════════════════════════════

KNOWN_CMDS = {
    '/start', '/like', '/info', '/visit', '/help', '/remain', '/ping',
    '/status', '/profile', '/guild', '/rank', '/servertime', '/about',
    '/daily', '/verify', '/balance', '/leaderboard',
    '/broadcast', '/ban', '/unban', '/addpoints', '/users'
}

@bot.message_handler(func=lambda m: True, content_types=['text'])
def fallback(message):
    broadcast_log.add(message.from_user.id)
    if message.text.startswith('/'):
        cmd = message.text.split()[0].lower().split('@')[0]
        if cmd not in KNOWN_CMDS:
            bot.reply_to(message,
                f"❓ Unknown command: `{cmd}`\n\nType /help to see all commands.",
                parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# EDIT HELPER
# ═══════════════════════════════════════════════════

def _edit(msg, text, markup=None):
    try:
        bot.edit_message_text(text, chat_id=msg.chat.id, message_id=msg.message_id,
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
