# Free Fire Likes Bot 🎮

A powerful Telegram bot designed to send likes to **Garena Free Fire** profiles using a UID and Server Name. Built with **Telebot (pyTelegramBotAPI)** and **Flask**, supporting both **Webhook** and **Polling** modes for high performance and reliability.

---

## 🌟 Features
- **Instant Likes**: Send likes to any Free Fire UID globally.
- **Verification System**: Ensures users are subscribed to required channels before using the bot.
- **Usage Tracking**: In-memory tracking of daily limits for users.
- **Dual Mode**: Seamlessly switches between Webhook (for production) and Polling (for development).
- **Owner Dashboard**: `/remain` command for the owner to monitor user statistics.
- **Threaded Processing**: Non-blocking API calls for a smooth user experience.

---

## 🤖 BOT Demo  

Try this bot directly on Telegram:  

[![Try on Telegram](https://img.shields.io/badge/Try%20on%20Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/paglu_like_bot) 

## 🤖 Bot Commands
- `/start` - Start the bot and verify membership.
- `/like <region> <uid>` - Send likes to the specified UID (Example: `/like bd 12345678`).
- `/help` - Show the help menu with all available commands.
- `/remain` - (Owner Only) View detailed daily usage stats.

---

## 🚀 Deployment
[![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://dashboard.render.com/web/new)
### Prerequisites
- Python 3.9+
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Environment Variables
Set the following environment variables in your hosting provider (e.g., Render, Railway, Vercel):

```bash
BOT_TOKEN=your_bot_token_here
WEBHOOK_URL=https://your-app-domain.com  # Optional: Only for Webhook mode
PORT=5000                                # Optional: Default is 5000
```

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/itz-paglu/Free-Fire-Like-Bot
   cd Free-Fire-Like-Bot
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```bash
   python main.py
   ```

---

## 🔗 How it Works
1. **API Integration**: The bot communicates with a premium Free Fire Like API to process requests.
2. **Reset Cycle**: Limits are automatically reset at **00:00 UTC** every day.


## 📊 Repository Stats

<p align="center">
  <img src="https://img.shields.io/github/stars/itz-paglu/Free-Fire-Like-Bot?style=for-the-badge&logo=github&color=yellow" />
  <img src="https://img.shields.io/github/forks/itz-paglu/Free-Fire-Like-Bot?style=for-the-badge&logo=github&color=blue" />
  <img src="https://img.shields.io/github/contributors/itz-paglu/Free-Fire-Like-Bot?style=for-the-badge&logo=github&color=green" />
  <img src="https://komarev.com/ghpvc/?username=itz-paglu&repo=Free-Fire-Like-Bot&style=for-the-badge&color=red" />
</p>

---

## 💛 Credits  

<p align="center">
  <a href="https://t.me/itzpaglu">
    <img src="https://img.shields.io/badge/Owner-🔥%20@itzpaglu-pink?style=for-the-badge&logo=telegram" />
  </a>
  <a href="https://t.me/paglu_dev">
    <img src="https://img.shields.io/badge/Channel-TARIKUL.dev-blue?style=for-the-badge&logo=telegram" />
  </a>
</p>

<p align="center">
  <a href="https://github.com/itz-paglu/Free-Fire-Like-Bot/stargazers" target="_blank">
    <img src="https://img.shields.io/badge/⭐%20Star%20This%20Repo-yellow?style=for-the-badge&logo=github" />
  </a>
</p>