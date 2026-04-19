# 🚀 Render Bot Deploy 

## ✅ Step 1 — Render Account বানাও

1. যাও [https://render.com](https://render.com)
2. **Sign Up** করো (GitHub দিয়ে Sign Up করলে সহজ হবে)

---

## ✅ Step 2 — GitHub এ Code Push করো

1. [https://github.com](https://github.com) এ যাও
2. নতুন **Repository** বানাও (Private রাখো)
3. এই project এর সব file গুলো push করো:

```bash
git init
git add .
git commit -m "FF LIKES BOT"
git remote add origin https://github.com/তোমার-username/repository-name.git
git push -u origin main
```

---

## ✅ Step 3 — Render এ New Web Service বানাও

1. Render Dashboard এ যাও → **New +** → **Web Service**
2. GitHub repository connect করো
3. নিচের settings দাও:

| Setting | Value |
|---|---|
| **Name** | ff-likes-bot |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |
| **Plan** | Free |

---

## ✅ Step 4 — Environment Variable যোগ করো

Render Dashboard এ **Environment** tab এ যাও:

| Key | Value |
|---|---|
| `BOT_TOKEN` | তোমার Telegram Bot Token |

> ⚠️ Token কোনো file এ লেখো না, শুধু Environment Variable এ দাও!

---

## ✅ Step 5 — Deploy করো

1. **Create Web Service** বাটনে চাপো
2. Deploy হতে ২-৩ মিনিট লাগবে
3. লগ দেখো — `🏠 Starting in polling mode` দেখলে বুঝবে সফল হয়েছে ✅

---

## ⚠️ Free Plan এ সমস্যা

Render Free Plan এ service **15 মিনিট inactivity** তে ঘুমিয়ে যায়।  
Bot কে জাগিয়ে রাখতে:

**Option A** — [https://uptimerobot.com](https://uptimerobot.com) এ free account বানাও:
1. **New Monitor** → **HTTP(S)**
2. URL দাও: `https://তোমার-render-url.onrender.com/health`
3. Interval: **5 minutes**

**Option B** — Render এর Paid Plan নাও ($7/মাস) — সবচেয়ে ভালো।

---

## 🔄 Bot Update করতে

GitHub এ নতুন commit push করলে Render **automatically** redeploy করবে।

```bash
git add .
git commit -m "update"
git push
```

---

## 📌 Important Files

| File | কাজ |
|---|---|
| `main.py` | Bot এর মূল code |
| `requirements.txt` | Python packages |
| `render.yaml` | Render configuration (optional) |

---

## 💬 সাহায্য দরকার?

Telegram: [@MaybeSifu](https://t.me/MaybeSifu)
