"""
NEXUS NOW — HERALD Publisher Agent
=====================================
Posts finished content packages to all platforms simultaneously.
Self-improves by learning which posting strategies get best reach.
Tracks: best posting times, best caption styles, best hashtag sets.
"""

import json
import time
import os
import base64
import datetime
import requests
from pathlib import Path
from agents.base_agent import NexusAgent, gemini_raw, extract_json


class HeraldAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are HERALD, the Publishing & Distribution agent for NEXUS NOW.

You optimise content for maximum reach on each platform.
You learn which titles, captions, posting times, and hashtags
perform best and apply those learnings to every future post.

PLATFORM EXPERTISE:
- YouTube: SEO title optimisation, description with keywords, thumbnail strategy
- Instagram: Hook-first captions, hashtag placement, Reels vs feed strategy  
- Twitter/X: Thread structure, first-tweet hook, retweet-bait phrasing
- TikTok: Trending audio suggestion, caption brevity, hook in first 2 seconds
- Website: SEO article structure, internal linking, meta tags
"""

    def __init__(self):
        super().__init__("herald_publisher", "publishing")
        self.system_prompt   = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)
        self.gemini_key      = os.environ.get("GEMINI_API_KEY", "")
        self.yt_creds        = os.environ.get("YOUTUBE_CREDENTIALS_JSON", "")
        self.ig_token        = os.environ.get("INSTAGRAM_TOKEN", "")
        self.ig_id           = os.environ.get("INSTAGRAM_BUSINESS_ID", "")
        self.tw_key          = os.environ.get("TWITTER_API_KEY", "")
        self.tw_secret       = os.environ.get("TWITTER_API_SECRET", "")
        self.tw_token        = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        self.tw_tsecret      = os.environ.get("TWITTER_ACCESS_SECRET", "")
        self.github_username = os.environ.get("GITHUB_USERNAME", "your-username")
        self.news_json       = Path("news.json")

    # ── OPTIMISE BEFORE POSTING ────────────────────────────────────────────
    def optimise_for_platform(self, content: dict, platform: str) -> dict:
        """Ask Gemini to further optimise content for a specific platform."""
        expertise = self.get_expertise_context()
        prompt = f"""
{self.system_prompt}

{expertise}

ORIGINAL CONTENT:
Title: {content.get('headline')}
Category: {content.get('category')}
Agent: {content.get('agent')}

Optimise this content for {platform.upper()} for maximum engagement.
Apply any learned patterns from past performance.

Return ONLY JSON with platform-specific improvements:
{{
  "optimised_title": "...",
  "optimised_caption": "...",
  "best_posting_time_utc": "HH:MM",
  "hashtags": ["tag1", "tag2"],
  "engagement_hooks": ["hook used in caption"]
}}
"""
        try:
            raw = gemini_raw(prompt, max_tokens=600)
            return json.loads(extract_json(raw))
        except:
            return {}

    # ── YOUTUBE ────────────────────────────────────────────────────────────
    def post_youtube(self, content: dict, video_path: str, thumbnail_path: str) -> dict:
        self.log("Posting to YouTube...")
        result = {"platform": "youtube", "status": "skipped", "url": None}
        if not self.yt_creds or not video_path or not Path(video_path).exists():
            self.log("YouTube: no credentials or video file — skipping")
            return result
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds_data = json.loads(self.yt_creds)
            creds = Credentials(
                token=creds_data.get("token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=creds_data.get("client_id"),
                client_secret=creds_data.get("client_secret")
            )
            yt = build("youtube", "v3", credentials=creds)

            opt = self.optimise_for_platform(content, "youtube")
            title = opt.get("optimised_title") or content.get("youtube_title") or content.get("headline", "")
            title = title[:100]  # YouTube max

            body = {
                "snippet": {
                    "title": title,
                    "description": content.get("youtube_description", ""),
                    "tags": content.get("youtube_tags", []),
                    "categoryId": "25",   # News & Politics
                    "defaultLanguage": "en",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            }
            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            req   = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp  = None
            while resp is None:
                _, resp = req.next_chunk()
            video_id = resp.get("id")

            if thumbnail_path and Path(thumbnail_path).exists():
                yt.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()

            url = f"https://youtube.com/watch?v={video_id}"
            self.log(f"YouTube: published → {url}")
            result = {"platform": "youtube", "status": "success", "url": url, "video_id": video_id}
        except Exception as e:
            self.log(f"YouTube ERROR: {e}")
            result = {"platform": "youtube", "status": "error", "error": str(e)}

        self.record_performance(content.get("headline",""), 7.0, "youtube_post")
        return result

    # ── TWITTER / X ────────────────────────────────────────────────────────
    def post_twitter(self, content: dict) -> dict:
        self.log("Posting thread to X/Twitter...")
        result = {"platform": "twitter", "status": "skipped", "url": None}
        if not self.tw_key:
            self.log("Twitter: no credentials — skipping")
            return result
        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=self.tw_key,
                consumer_secret=self.tw_secret,
                access_token=self.tw_token,
                access_token_secret=self.tw_tsecret
            )
            tweets = content.get("tweet_thread", [])
            if not tweets:
                return result

            opt = self.optimise_for_platform(content, "twitter")
            # Optionally override first tweet hook
            if opt.get("optimised_caption"):
                tweets[0] = opt["optimised_caption"][:280]

            previous_id = None
            tweet_ids   = []
            for tweet in tweets:
                tweet = tweet[:280]
                if previous_id:
                    resp = client.create_tweet(text=tweet, in_reply_to_tweet_id=previous_id)
                else:
                    resp = client.create_tweet(text=tweet)
                previous_id = resp.data["id"]
                tweet_ids.append(previous_id)
                time.sleep(2)

            url = f"https://twitter.com/NexusNow/status/{tweet_ids[0]}"
            self.log(f"Twitter: {len(tweets)}-tweet thread posted → {url}")
            result = {"platform": "twitter", "status": "success", "url": url}
        except Exception as e:
            self.log(f"Twitter ERROR: {e}")
            result = {"platform": "twitter", "status": "error", "error": str(e)}

        self.record_performance(content.get("headline",""), 7.0, "twitter_post")
        return result

    # ── INSTAGRAM ──────────────────────────────────────────────────────────
    def post_instagram(self, content: dict, image_path: str) -> dict:
        self.log("Posting to Instagram...")
        result = {"platform": "instagram", "status": "skipped", "url": None}
        if not self.ig_token or not image_path:
            self.log("Instagram: no token or image — skipping")
            return result
        try:
            opt     = self.optimise_for_platform(content, "instagram")
            caption = opt.get("optimised_caption") or content.get("instagram_caption", "")
            img_url = f"https://{self.github_username}.github.io/news/{image_path}"

            # Create container
            create_url = f"https://graph.facebook.com/v19.0/{self.ig_id}/media"
            r = requests.post(create_url, data={
                "image_url":    img_url,
                "caption":      caption[:2200],
                "access_token": self.ig_token
            })
            data = r.json()
            container_id = data.get("id")
            if not container_id:
                raise ValueError(f"No container ID: {data}")

            time.sleep(8)  # Wait for media processing

            # Publish
            pub_url = f"https://graph.facebook.com/v19.0/{self.ig_id}/media_publish"
            r2 = requests.post(pub_url, data={
                "creation_id":  container_id,
                "access_token": self.ig_token
            })
            post_id = r2.json().get("id")
            self.log(f"Instagram: published → post_id={post_id}")
            result = {"platform": "instagram", "status": "success", "post_id": post_id}
        except Exception as e:
            self.log(f"Instagram ERROR: {e}")
            result = {"platform": "instagram", "status": "error", "error": str(e)}

        self.record_performance(content.get("headline",""), 7.0, "instagram_post")
        return result

    # ── WEBSITE (GitHub Pages) ────────────────────────────────────────────
    def update_website(self, articles: list[dict]) -> bool:
        self.log("Updating website news.json...")
        existing = []
        if self.news_json.exists():
            try:
                existing = json.loads(self.news_json.read_text())
            except:
                existing = []

        new_items = []
        for r in articles:
            if not r:
                continue
            slug = r.get("headline","")[:40].lower()
            slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
            new_items.append({
                "title":       r.get("headline", ""),
                "subheadline": r.get("subheadline", ""),
                "category":    r.get("category", "World"),
                "agent":       r.get("agent", "NEXUS"),
                "summary":     r.get("summary", ""),
                "deep_analysis": r.get("deep_analysis", ""),
                "key_facts":   r.get("key_facts", []),
                "tags":        r.get("tags", []),
                "keywords":    r.get("youtube_tags", []),
                "quality_score": r.get("quality_score", 0),
                "slug":        slug,
                "time":        datetime.datetime.utcnow().strftime("%b %d, %Y · %H:%M UTC"),
                "timestamp":   datetime.datetime.utcnow().isoformat(),
                "ai_generated": True,
                "ai_agent":    r.get("agent", "NEXUS NOW")
            })

        combined = (new_items + existing)[:100]
        self.news_json.write_text(json.dumps(combined, indent=2))
        self.log(f"Website: news.json updated ({len(new_items)} new, {len(combined)} total)")
        return True

    # ── GENERATE VOICEOVER ────────────────────────────────────────────────
    def generate_voiceover(self, script: str, filename: str) -> str | None:
        """Google Cloud TTS free tier."""
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.gemini_key}"
        payload = {
            "input": {"text": script[:4500]},  # TTS limit
            "voice": {
                "languageCode": "en-US",
                "name": "en-US-Neural2-D",
                "ssmlGender": "MALE"
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": 1.08,
                "pitch": -1.5,
                "volumeGainDb": 2.0
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=30)
            data = r.json()
            audio_b64 = data.get("audioContent")
            if not audio_b64:
                raise ValueError(f"No audio content: {data}")
            path = f"assets/audio/{filename}.mp3"
            Path("assets/audio").mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(base64.b64decode(audio_b64))
            self.log(f"Voiceover: saved → {path}")
            return path
        except Exception as e:
            self.log(f"TTS ERROR: {e}")
            return None

    # ── GENERATE THUMBNAIL ────────────────────────────────────────────────
    def generate_thumbnail(self, prompt: str, filename: str) -> str | None:
        """Gemini Imagen free tier."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={self.gemini_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}
        }
        try:
            r = requests.post(url, json=payload, timeout=90)
            data = r.json()
            img_b64 = data["predictions"][0]["bytesBase64Encoded"]
            path = f"assets/images/{filename}.jpg"
            Path("assets/images").mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(base64.b64decode(img_b64))
            self.log(f"Thumbnail: saved → {path}")
            return path
        except Exception as e:
            self.log(f"Thumbnail ERROR: {e}")
            return None

    # ── MASTER PUBLISH ────────────────────────────────────────────────────
    def publish_all(self, content: dict, video_path: str = None) -> dict:
        """Publish one content package to all platforms."""
        self.increment_run()
        slug = content.get("headline","unknown")[:40].lower()
        slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")

        # Generate media assets
        thumb_path = self.generate_thumbnail(
            content.get("thumbnail_prompt", f"Breaking news: {content.get('headline')}"),
            filename=slug
        )
        voice_path = self.generate_voiceover(
            content.get("video_script", ""),
            filename=slug
        )

        # Publish everywhere
        results = {
            "content_title": content.get("headline"),
            "agent":         content.get("agent"),
            "category":      content.get("category"),
            "quality_score": content.get("quality_score"),
            "timestamp":     datetime.datetime.utcnow().isoformat(),
            "platforms":     {}
        }

        results["platforms"]["website"] = {"status": "success"} if \
            self.update_website([content]) else {"status": "failed"}

        results["platforms"]["twitter"] = self.post_twitter(content)
        time.sleep(3)

        if thumb_path:
            results["platforms"]["instagram"] = self.post_instagram(content, thumb_path)
            time.sleep(3)

        if video_path:
            results["platforms"]["youtube"] = self.post_youtube(content, video_path, thumb_path)

        self.log(f"Publish complete: {content.get('headline')}")
        self.log(f"  Results: { {k: v.get('status') for k,v in results['platforms'].items()} }")
        return results
