# 📡 NEXUS NOW — Autonomous AI News Channel

> *Every Story. Every Second. Everywhere.*

**NEXUS NOW** is a fully autonomous AI-powered news channel. Zero humans. Five AI agents. Two stories published per day across YouTube, Instagram, X/Twitter, and a GitHub Pages website — all triggered automatically.

---

## 🤖 The Five AI Agents

| Agent | Role | What It Does |
|-------|------|-------------|
| **SCOUT** | Trend Monitor | Scans Google Trends RSS every run. Picks top 2 stories. |
| **AXIOM** | Researcher | Deep-dives each story. Outputs full research + scripts. |
| **VERBA** | Writer | Writes video script, article, tweets, Instagram caption. |
| **VISIO** | Producer | Generates thumbnail image + voiceover audio. |
| **HERALD** | Publisher | Posts to all platforms + updates the website. |

---

## 🗂️ Repository Structure

```
nexus-now/
├── index.html              ← GitHub Pages website (auto-updated)
├── news.json               ← Auto-updated article feed
├── pipeline.py             ← Main automation brain
├── requirements.txt        ← Python dependencies
├── assets/
│   ├── images/             ← AI-generated thumbnails
│   └── audio/              ← AI-generated voiceovers
├── logs/
│   └── pipeline.log        ← Run history
└── .github/
    └── workflows/
        └── pipeline.yml    ← GitHub Actions (runs 2x daily)
```

---

## ⚡ One-Time Setup (30 minutes total)

### STEP 1 — Fork / Clone This Repository
```bash
# On GitHub: click "Fork" on this repo
# Then clone your fork:
git clone https://github.com/nexus-now/news.git
cd nexus-now
```

### STEP 2 — Enable GitHub Pages
1. Go to your repo → **Settings** → **Pages**
2. Source: **Deploy from branch** → `main` → `/ (root)`
3. Your site will be live at: `https://nexus-now.github.io/news/`

### STEP 3 — Get Your API Keys

#### 🔑 Gemini API Key (FREE)
1. Go to https://aistudio.google.com/app/apikey
2. Click **Create API Key**
3. Copy the key

#### 🔑 Twitter/X API (FREE basic tier)
1. Go to https://developer.twitter.com
2. Create a new app → generate all 4 keys:
   - API Key & Secret
   - Access Token & Secret
3. Make sure app has **Read + Write** permissions

#### 🔑 Instagram (Meta Graph API) (FREE)
1. Go to https://developers.facebook.com
2. Create an App → Add **Instagram Graph API** product
3. Connect your Instagram Business account
4. Generate a long-lived Page Access Token
5. Get your Instagram Business Account ID

#### 🔑 YouTube Data API v3 (FREE — 10,000 units/day)
1. Go to https://console.cloud.google.com
2. Create a project → Enable **YouTube Data API v3**
3. Create **OAuth 2.0 credentials** (Desktop App type)
4. Run the auth script once locally:
   ```bash
   python setup/youtube_auth.py
   ```
5. Copy the generated `credentials.json` content

### STEP 4 — Add GitHub Secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets one by one:

| Secret Name | Value |
|-------------|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `YOUTUBE_CREDENTIALS_JSON` | Full JSON string from OAuth credentials |
| `YOUTUBE_CHANNEL_ID` | Your YouTube channel ID (found in YouTube Studio) |
| `INSTAGRAM_TOKEN` | Your Meta long-lived access token |
| `INSTAGRAM_BUSINESS_ID` | Your Instagram Business Account ID |
| `TWITTER_API_KEY` | Twitter API Key |
| `TWITTER_API_SECRET` | Twitter API Secret |
| `TWITTER_ACCESS_TOKEN` | Twitter Access Token |
| `TWITTER_ACCESS_SECRET` | Twitter Access Token Secret |

### STEP 5 — Update Your GitHub Pages URL in pipeline.py
Open `pipeline.py` and find this line:
```python
"image_url": f"https://nexus-now.github.io/news/{image_path}"
```
Replace `nexus-now` with your actual GitHub username.

### STEP 6 — Push and Activate
```bash
git add .
git commit -m "🚀 NEXUS NOW going live"
git push origin main
```

**That's it.** The pipeline will now run automatically at **8:00 AM UTC** and **6:00 PM UTC** every day.

---

## ▶️ Manual Run (Test It Now)
Go to your repo → **Actions** → **NEXUS NOW — Autonomous Pipeline** → **Run workflow**

Watch the logs in real-time to see all 5 agents working.

---

## 📊 Pipeline Schedule

```
08:00 UTC daily   →  Morning trending story
18:00 UTC daily   →  Evening trending story
```

Each run:
1. Scans Google Trends for top stories
2. Picks best 2 by AI score
3. Researches both fully
4. Generates thumbnail + voiceover
5. Posts to Twitter, Instagram, updates website
6. Logs everything to `logs/pipeline.log`

---

## 💰 Monetization Path

| Platform | How to Monetize |
|----------|----------------|
| **YouTube** | YouTube Partner Program (1K subs + 4K watch hours) |
| **Instagram** | Creator marketplace, affiliate links in bio |
| **X/Twitter** | X Premium creator revenue sharing |
| **Website** | Google AdSense (apply once site has traffic) |

---

## 🆓 Cost Breakdown (Monthly)

| Service | Cost |
|---------|------|
| Gemini API (free tier) | $0 |
| Google TTS (free tier: 1M chars/month) | $0 |
| GitHub Actions (free tier: 2,000 min/month) | $0 |
| GitHub Pages | $0 |
| Twitter API (Basic) | $0 (with limits) |
| Instagram API | $0 |
| YouTube API | $0 |
| **Total** | **$0/month** |

Only cost: Your existing **Google Gemini paid plan** for video generation.

---

## 🔧 Customization

Edit `pipeline.py` top section:
```python
POSTS_PER_RUN = 2          # Change to 1 or 3
GEMINI_MODEL  = "gemini-2.0-flash-exp"   # Upgrade model here
```

Edit your brand voice in the `BRAND` dict:
```python
BRAND = {
    "name": "NEXUS NOW",
    "tagline": "Every Story. Every Second. Everywhere.",
    "voice": "authoritative yet accessible, fast-paced, globally minded",
}
```

---

## ❓ Troubleshooting

**Pipeline runs but nothing posts?**
→ Check GitHub Secrets are all set correctly. Check `logs/pipeline.log` in Actions artifacts.

**Gemini rate limit errors?**
→ Free tier allows 15 requests/min. Pipeline is throttled to stay within this.

**Twitter 403 error?**
→ Make sure your app has Read + Write permissions (not Read only).

**Instagram image not posting?**
→ Image must be publicly accessible. Make sure GitHub Pages is enabled and published.

---

*NEXUS NOW — Powered entirely by AI. No humans harmed (or hired) in the making of this news channel.*
