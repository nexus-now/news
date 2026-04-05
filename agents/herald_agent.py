"""
NEXUS NOW — HERALD Publisher Agent
Posts content to all platforms. Generates thumbnails and voiceovers.
"""
import json, time, os, base64, datetime, requests
from pathlib import Path
from agents.base_agent import NexusAgent, extract_json
from agents.free_ai_provider import ai_generate, img_generate, tts_generate

try:
    from agents.storage_manager import log_to_sheets
except:
    def log_to_sheets(*a, **k): pass


class HeraldAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = "You are HERALD, the Publishing Agent for NEXUS NOW. Optimise content for maximum reach on every platform."

    def __init__(self):
        super().__init__("herald_publisher", "publishing")
        self.gemini_key  = os.environ.get("GEMINI_API_KEY", "")
        self.yt_creds    = os.environ.get("YOUTUBE_CREDENTIALS_JSON", "")
        self.ig_token    = os.environ.get("INSTAGRAM_TOKEN", "")
        self.ig_id       = os.environ.get("INSTAGRAM_BUSINESS_ID", "")
        self.tw_key      = os.environ.get("TWITTER_API_KEY", "")
        self.tw_secret   = os.environ.get("TWITTER_API_SECRET", "")
        self.tw_token    = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        self.tw_tsecret  = os.environ.get("TWITTER_ACCESS_SECRET", "")
        self.gh_username = os.environ.get("GITHUB_USERNAME", "nexus-now")
        self.news_json   = Path("news.json")

    # ── THUMBNAIL ─────────────────────────────────────────────────────────
    def generate_thumbnail(self, prompt: str, filename: str) -> str | None:
        self.log("Generating thumbnail...")
        try:
            path = img_generate(prompt, filename)
            if path:
                self.log(f"Thumbnail saved: {path}")
            return path
        except Exception as e:
            self.log(f"Thumbnail failed: {e}")
            return None

    # ── VOICEOVER ─────────────────────────────────────────────────────────
    def generate_voiceover(self, script: str, filename: str) -> str | None:
        self.log("Generating voiceover...")
        try:
            path = tts_generate(script[:4500], filename)
            if path:
                self.log(f"Audio saved: {path}")
            return path
        except Exception as e:
            self.log(f"Voiceover failed: {e}")
            return None

    # ── TWITTER ───────────────────────────────────────────────────────────
    def post_twitter(self, content: dict) -> dict:
        self.log("Posting to Twitter/X...")
        result = {"platform": "twitter", "status": "skipped"}
        if not self.tw_key:
            self.log("No Twitter credentials — skipping")
            return result
        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=self.tw_key, consumer_secret=self.tw_secret,
                access_token=self.tw_token, access_token_secret=self.tw_tsecret
            )
            tweets = content.get("tweet_thread", [])
            if not tweets:
                return result
            prev_id = None
            for tweet in tweets:
                tweet = str(tweet)[:280]
                if prev_id:
                    r = client.create_tweet(text=tweet, in_reply_to_tweet_id=prev_id)
                else:
                    r = client.create_tweet(text=tweet)
                prev_id = r.data["id"]
                time.sleep(2)
            url = f"https://twitter.com/NexusNow/status/{prev_id}"
            self.log(f"Twitter: {len(tweets)}-tweet thread posted → {url}")
            return {"platform": "twitter", "status": "success", "url": url}
        except Exception as e:
            self.log(f"Twitter error: {e}")
            return {"platform": "twitter", "status": "error", "error": str(e)}

    # ── INSTAGRAM ─────────────────────────────────────────────────────────
    def post_instagram(self, content: dict, image_path: str) -> dict:
        self.log("Posting to Instagram...")
        result = {"platform": "instagram", "status": "skipped"}
        if not self.ig_token or not image_path:
            self.log("No Instagram credentials or image — skipping")
            return result
        try:
            caption  = content.get("instagram_caption", "")[:2200]
            img_url  = f"https://{self.gh_username}.github.io/news/{image_path}"
            create_r = requests.post(
                f"https://graph.facebook.com/v19.0/{self.ig_id}/media",
                data={"image_url": img_url, "caption": caption, "access_token": self.ig_token},
                timeout=30
            )
            cid = create_r.json().get("id")
            if not cid:
                raise ValueError(f"No container ID: {create_r.text}")
            time.sleep(8)
            pub_r = requests.post(
                f"https://graph.facebook.com/v19.0/{self.ig_id}/media_publish",
                data={"creation_id": cid, "access_token": self.ig_token},
                timeout=30
            )
            post_id = pub_r.json().get("id")
            self.log(f"Instagram posted: {post_id}")
            return {"platform": "instagram", "status": "success", "post_id": post_id}
        except Exception as e:
            self.log(f"Instagram error: {e}")
            return {"platform": "instagram", "status": "error", "error": str(e)}

    # ── YOUTUBE ───────────────────────────────────────────────────────────
    def post_youtube(self, content: dict, video_path: str, thumb_path: str) -> dict:
        self.log("Uploading to YouTube...")
        result = {"platform": "youtube", "status": "skipped"}
        if not self.yt_creds or not video_path or not Path(video_path).exists():
            self.log("No YouTube credentials or video file — skipping")
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
            yt   = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {
                    "title":       content.get("youtube_title", content.get("headline",""))[:100],
                    "description": content.get("youtube_description", ""),
                    "tags":        content.get("youtube_tags", []),
                    "categoryId":  "25"
                },
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
            }
            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            req   = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp  = None
            while resp is None:
                _, resp = req.next_chunk()
            vid_id = resp.get("id")
            if thumb_path and Path(thumb_path).exists():
                yt.thumbnails().set(videoId=vid_id,
                    media_body=MediaFileUpload(thumb_path)).execute()
            url = f"https://youtube.com/watch?v={vid_id}"
            self.log(f"YouTube uploaded: {url}")
            return {"platform": "youtube", "status": "success", "url": url, "video_id": vid_id}
        except Exception as e:
            self.log(f"YouTube error: {e}")
            return {"platform": "youtube", "status": "error", "error": str(e)}

    # ── WEBSITE ───────────────────────────────────────────────────────────
    def update_website(self, articles: list) -> bool:
        self.log("Updating news.json...")
        existing = []
        if self.news_json.exists():
            try: existing = json.loads(self.news_json.read_text())
            except: existing = []
        new_items = []
        for r in articles:
            if not r: continue
            slug = r.get("headline", "")[:40].lower()
            slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
            new_items.append({
                "title":          r.get("headline", ""),
                "subheadline":    r.get("subheadline", ""),
                "category":       r.get("category", "World"),
                "agent":          r.get("agent", "NEXUS NOW"),
                "summary":        r.get("summary", ""),
                "key_facts":      r.get("key_facts", []),
                "tags":           r.get("tags", []),
                "quality_score":  r.get("quality_score", 0),
                "copyright_id":   r.get("copyright_id", ""),
                "verification":   r.get("verification_badge", ""),
                "slug":           slug,
                "time":           datetime.datetime.utcnow().strftime("%b %d, %Y · %H:%M UTC"),
                "timestamp":      datetime.datetime.utcnow().isoformat(),
                "ai_generated":   True,
            })
        combined = (new_items + existing)[:100]
        self.news_json.write_text(json.dumps(combined, indent=2))
        self.log(f"news.json updated: {len(new_items)} new, {len(combined)} total")
        return True

    # ── MASTER PUBLISH ────────────────────────────────────────────────────
    def publish_all(self, content: dict, video_path: str = None) -> dict:
        self.increment_run()
        slug = content.get("copyright_id",
               content.get("headline","article"))[:40].lower()
        slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")

        # Generate media
        thumb_path = self.generate_thumbnail(
            content.get("thumbnail_prompt",
                f"Breaking news broadcast: {content.get('headline','')}. "
                "Dark dramatic background, bold red and white NEXUS NOW branding, "
                "professional news thumbnail aesthetic."),
            filename=slug
        )
        self.generate_voiceover(content.get("video_script", ""), filename=slug)

        # Publish
        results = {
            "content_title": content.get("headline"),
            "agent":         content.get("agent"),
            "category":      content.get("category"),
            "timestamp":     datetime.datetime.utcnow().isoformat(),
            "platforms":     {}
        }

        # Website always first (always works)
        results["platforms"]["website"] = {
            "status": "success" if self.update_website([content]) else "failed"
        }

        # Twitter
        results["platforms"]["twitter"] = self.post_twitter(content)
        time.sleep(3)

        # Instagram (needs image hosted on GitHub Pages)
        if thumb_path:
            results["platforms"]["instagram"] = self.post_instagram(content, thumb_path)
            time.sleep(3)

        # YouTube (only if video exists)
        if video_path:
            results["platforms"]["youtube"] = self.post_youtube(content, video_path, thumb_path)

        self.log(f"Published: {content.get('headline','')}")
        self.log(f"Platforms: { {k:v.get('status') for k,v in results['platforms'].items()} }")
        return results
