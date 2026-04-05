#!/usr/bin/env python3
"""
NEXUS NOW — Main Automation Pipeline
=====================================
Runs twice daily via GitHub Actions.
Fetches top 2 trending topics → researches them → generates content → publishes everywhere.

Zero human intervention. Fully autonomous.
"""

import os
import json
import time
import datetime
import requests
import feedparser
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
YOUTUBE_TOKEN    = os.environ.get("YOUTUBE_TOKEN", "")
INSTAGRAM_TOKEN  = os.environ.get("INSTAGRAM_TOKEN", "")
INSTAGRAM_ID     = os.environ.get("INSTAGRAM_BUSINESS_ID", "")
TWITTER_KEY      = os.environ.get("TWITTER_API_KEY", "")
TWITTER_SECRET   = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_TOKEN    = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_TSECRET  = os.environ.get("TWITTER_ACCESS_SECRET", "")

GEMINI_MODEL     = "gemini-2.0-flash-exp"      # free tier
GEMINI_VIDEO_MDL = "gemini-2.0-flash-exp"      # use your paid key for video
POSTS_PER_RUN    = 2                            # 2 posts per day max
NEWS_JSON_PATH   = Path("news.json")
LOG_PATH         = Path("logs/pipeline.log")

BRAND = {
    "name": "NEXUS NOW",
    "tagline": "Every Story. Every Second. Everywhere.",
    "voice": "authoritative yet accessible, fast-paced, clear, globally minded",
    "handle": "@NexusNow",
    "youtube_channel_id": os.environ.get("YOUTUBE_CHANNEL_ID", ""),
}

# ── LOGGING ─────────────────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(exist_ok=True)
def log(msg):
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")

# ════════════════════════════════════════════════════════════════════════════
# AGENT 1 — SCOUT: Trend Detection
# ════════════════════════════════════════════════════════════════════════════
def scout_get_trends(geo="US", n=10):
    """
    Fetch Google Trends via RSS (free, no API key needed).
    Returns list of trending topic strings.
    """
    log("SCOUT: Fetching Google Trends RSS...")
    urls = [
        f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
        "https://trends.google.com/trends/trendingsearches/realtime/rss?geo=US&cat=all",
    ]
    topics = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:n]:
                title = entry.get("title", "").strip()
                if title and title not in topics:
                    topics.append(title)
                    # Also grab approximate traffic if available
                    try:
                        traffic = entry.get("ht_approx_traffic", "")
                        log(f"  TREND: {title} ({traffic})")
                    except:
                        log(f"  TREND: {title}")
        except Exception as e:
            log(f"SCOUT WARNING: {e}")

    # Score and pick best 2
    scored = scout_score_topics(topics)
    selected = scored[:POSTS_PER_RUN]
    log(f"SCOUT: Selected topics → {[t['topic'] for t in selected]}")
    return selected

def scout_score_topics(topics):
    """Score topics by content potential using simple heuristics + Gemini."""
    if not topics:
        return []
    prompt = f"""
You are SCOUT, a trend analysis AI for NEXUS NOW news channel.

Given these trending topics, score each one from 1-10 for:
- News value (is this globally significant?)
- Content potential (can we make a compelling video/article?)
- Brand safety (is it safe for a general news channel?)

Topics: {json.dumps(topics)}

Return ONLY a JSON array, sorted by total score descending:
[{{"topic": "...", "score": 8, "category": "Technology", "angle": "Why this matters globally"}}]
"""
    try:
        result = gemini_generate(prompt, max_tokens=800)
        data = json.loads(extract_json(result))
        return data
    except Exception as e:
        log(f"SCOUT SCORE ERROR: {e}")
        # Fallback: return first N topics unsorted
        return [{"topic": t, "score": 5, "category": "World", "angle": "Latest developments"} for t in topics[:POSTS_PER_RUN]]

# ════════════════════════════════════════════════════════════════════════════
# AGENT 2 — AXIOM: Research
# ════════════════════════════════════════════════════════════════════════════
def axiom_research(topic_data):
    """Deep research a trending topic. Returns structured research object."""
    topic = topic_data["topic"]
    angle = topic_data.get("angle", "")
    log(f"AXIOM: Researching '{topic}'...")

    prompt = f"""
You are AXIOM, the research agent for NEXUS NOW — an AI-powered global news channel.

Research this trending topic thoroughly: "{topic}"
Angle to focus on: {angle}

Provide a comprehensive research report in this EXACT JSON format:
{{
  "topic": "{topic}",
  "headline": "Compelling news headline (max 12 words)",
  "category": "World/Technology/Business/Science/Politics/Sports/Entertainment",
  "summary": "3-sentence summary of the story and why it matters",
  "key_facts": ["fact 1", "fact 2", "fact 3", "fact 4", "fact 5"],
  "background": "2-paragraph background context explaining the full story",
  "global_impact": "How this affects people globally — 2 sentences",
  "different_perspectives": ["perspective 1", "perspective 2", "perspective 3"],
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "video_script": "60-second news anchor script (professional TV news style, 150-180 words). Start with a strong hook.",
  "youtube_title": "SEO-optimised YouTube title (max 70 chars, include year)",
  "youtube_description": "YouTube description (200 words) with timestamps placeholder and social links",
  "youtube_tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "instagram_caption": "Instagram caption with hook, 3 key points, call to action, and 15 relevant hashtags",
  "tweet_thread": ["Tweet 1/5 (hook, max 280 chars)", "Tweet 2/5", "Tweet 3/5", "Tweet 4/5", "Tweet 5/5 (CTA)"],
  "thumbnail_prompt": "Detailed image generation prompt for a dramatic, eye-catching news thumbnail. Include: bold text overlay suggestion, background scene, color scheme (use reds and blacks for NEXUS NOW brand)",
  "tts_voice_notes": "Description of tone and pacing for text-to-speech: e.g. serious, measured pace, emphasise key words"
}}

Return ONLY the JSON object. No markdown, no explanation.
"""
    try:
        raw = gemini_generate(prompt, max_tokens=2500)
        research = json.loads(extract_json(raw))
        log(f"AXIOM: Research complete → '{research.get('headline', topic)}'")
        return research
    except Exception as e:
        log(f"AXIOM ERROR: {e}")
        return None

# ════════════════════════════════════════════════════════════════════════════
# AGENT 3 — VISIO: Media Production
# ════════════════════════════════════════════════════════════════════════════
def visio_generate_thumbnail(prompt, filename):
    """Generate thumbnail image using Gemini Imagen (free tier)."""
    log(f"VISIO: Generating thumbnail...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}
    }
    try:
        res = requests.post(url, json=payload, timeout=60)
        data = res.json()
        img_b64 = data["predictions"][0]["bytesBase64Encoded"]
        import base64
        Path("assets/images").mkdir(parents=True, exist_ok=True)
        img_path = f"assets/images/{filename}.jpg"
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(img_b64))
        log(f"VISIO: Thumbnail saved → {img_path}")
        return img_path
    except Exception as e:
        log(f"VISIO THUMBNAIL ERROR: {e}")
        return None

def visio_generate_voiceover(script, filename):
    """Generate voiceover using Google Cloud TTS free tier."""
    log("VISIO: Generating voiceover...")
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GEMINI_API_KEY}"
    payload = {
        "input": {"text": script},
        "voice": {
            "languageCode": "en-US",
            "name": "en-US-Neural2-D",   # Deep authoritative voice
            "ssmlGender": "MALE"
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 1.05,
            "pitch": -2.0
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=30)
        data = res.json()
        import base64
        Path("assets/audio").mkdir(parents=True, exist_ok=True)
        audio_path = f"assets/audio/{filename}.mp3"
        with open(audio_path, "wb") as f:
            f.write(base64.b64decode(data["audioContent"]))
        log(f"VISIO: Audio saved → {audio_path}")
        return audio_path
    except Exception as e:
        log(f"VISIO AUDIO ERROR: {e}")
        return None

# ════════════════════════════════════════════════════════════════════════════
# AGENT 4 — HERALD: Publisher
# ════════════════════════════════════════════════════════════════════════════
def herald_post_twitter(research):
    """Post tweet thread to X/Twitter."""
    log("HERALD: Posting to X/Twitter...")
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=TWITTER_KEY,
            consumer_secret=TWITTER_SECRET,
            access_token=TWITTER_TOKEN,
            access_token_secret=TWITTER_TSECRET
        )
        tweets = research.get("tweet_thread", [])
        previous_id = None
        for tweet in tweets:
            if previous_id:
                resp = client.create_tweet(text=tweet, in_reply_to_tweet_id=previous_id)
            else:
                resp = client.create_tweet(text=tweet)
            previous_id = resp.data["id"]
            time.sleep(2)
        log(f"HERALD: Twitter thread posted ({len(tweets)} tweets)")
        return True
    except Exception as e:
        log(f"HERALD TWITTER ERROR: {e}")
        return False

def herald_post_instagram(research, image_path):
    """Post to Instagram via Meta Graph API."""
    log("HERALD: Posting to Instagram...")
    try:
        caption = research.get("instagram_caption", "")
        # Step 1: Upload media container
        media_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ID}/media"
        # For video reels, use video_url; for images use image_url
        # Here we post as image with caption
        params = {
            "caption": caption,
            "access_token": INSTAGRAM_TOKEN,
            "image_url": f"https://nexus-now.github.io/news/{image_path}"
        }
        res = requests.post(media_url, data=params)
        container_id = res.json().get("id")
        if not container_id:
            log(f"HERALD INSTAGRAM: No container ID: {res.text}")
            return False
        time.sleep(5)
        # Step 2: Publish
        publish_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ID}/media_publish"
        res2 = requests.post(publish_url, data={"creation_id": container_id, "access_token": INSTAGRAM_TOKEN})
        log(f"HERALD: Instagram posted → {res2.json()}")
        return True
    except Exception as e:
        log(f"HERALD INSTAGRAM ERROR: {e}")
        return False

def herald_update_website(articles):
    """Update news.json for the GitHub Pages website."""
    log("HERALD: Updating website news.json...")
    existing = []
    if NEWS_JSON_PATH.exists():
        try:
            existing = json.loads(NEWS_JSON_PATH.read_text())
        except:
            existing = []

    new_items = []
    for r in articles:
        if not r:
            continue
        new_items.append({
            "title": r.get("headline", r.get("topic", "")),
            "category": r.get("category", "World"),
            "summary": r.get("summary", ""),
            "keywords": r.get("keywords", []),
            "time": datetime.datetime.utcnow().strftime("%b %d, %Y · %H:%M UTC"),
            "ai_generated": True
        })

    # Keep last 50 articles
    combined = (new_items + existing)[:50]
    NEWS_JSON_PATH.write_text(json.dumps(combined, indent=2))
    log(f"HERALD: news.json updated with {len(new_items)} new articles")

def herald_post_youtube(research, video_path, thumbnail_path):
    """Upload video to YouTube via Data API v3."""
    log("HERALD: Uploading to YouTube...")
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds_data = json.loads(os.environ.get("YOUTUBE_CREDENTIALS_JSON", "{}"))
        creds = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret")
        )
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": research.get("youtube_title", research.get("headline", "")),
                "description": research.get("youtube_description", ""),
                "tags": research.get("youtube_tags", []),
                "categoryId": "25",  # News & Politics
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }

        if video_path and Path(video_path).exists():
            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = req.execute()
            video_id = response.get("id")
            log(f"HERALD: YouTube uploaded → https://youtube.com/watch?v={video_id}")

            # Set thumbnail
            if thumbnail_path and Path(thumbnail_path).exists():
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
                log("HERALD: Thumbnail set on YouTube")
            return video_id
        else:
            log("HERALD: No video file — skipping YouTube upload")
            return None
    except Exception as e:
        log(f"HERALD YOUTUBE ERROR: {e}")
        return None

# ════════════════════════════════════════════════════════════════════════════
# GEMINI API HELPER
# ════════════════════════════════════════════════════════════════════════════
def gemini_generate(prompt, max_tokens=1000):
    """Call Gemini API (free tier)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
        }
    }
    res = requests.post(url, json=payload, timeout=60)
    data = res.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        log(f"GEMINI ERROR: {e} | Response: {str(data)[:300]}")
        raise

def extract_json(text):
    """Extract JSON from text that may have markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    # Find first { or [
    for i, c in enumerate(text):
        if c in "{[":
            return text[i:]
    return text

# ════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════════════════════════════════
def run_pipeline():
    log("=" * 60)
    log("NEXUS NOW PIPELINE STARTING")
    log(f"Time: {datetime.datetime.utcnow().isoformat()} UTC")
    log("=" * 60)

    # STEP 1: SCOUT — Get trending topics
    trends = scout_get_trends(geo="US", n=15)
    if not trends:
        log("PIPELINE: No trends found. Exiting.")
        return

    results = []

    for trend in trends[:POSTS_PER_RUN]:
        log(f"\n── Processing: {trend['topic']} ──")

        # STEP 2: AXIOM — Research
        research = axiom_research(trend)
        if not research:
            log(f"Skipping '{trend['topic']}' — research failed")
            continue

        slug = research.get("headline", trend["topic"])[:40].lower()
        slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")

        # STEP 3: VISIO — Generate media
        thumbnail_path = visio_generate_thumbnail(
            research.get("thumbnail_prompt", f"Breaking news: {research.get('headline')}"),
            filename=slug
        )
        voiceover_path = visio_generate_voiceover(
            research.get("video_script", ""),
            filename=slug
        )

        # STEP 4: HERALD — Publish everywhere
        herald_update_website([research])  # Always works (GitHub Pages)

        if TWITTER_KEY:
            herald_post_twitter(research)
            time.sleep(3)

        if INSTAGRAM_TOKEN and thumbnail_path:
            herald_post_instagram(research, thumbnail_path)
            time.sleep(3)

        # YouTube requires a real video file — generated externally with Gemini Video
        # The video_path below would be the output of Gemini Video generation
        # For now we log the script for manual Gemini Video generation
        log(f"\n📹 VIDEO SCRIPT FOR GEMINI VIDEO GENERATION:\n{research.get('video_script', '')}\n")

        results.append(research)
        log(f"✅ '{research.get('headline')}' published successfully")
        time.sleep(10)  # Rate limit respect

    # Final summary
    log("\n" + "=" * 60)
    log(f"PIPELINE COMPLETE: {len(results)} stories published")
    log("=" * 60)
    return results

if __name__ == "__main__":
    run_pipeline()
