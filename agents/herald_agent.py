"""
NEXUS NOW — HERALD Publisher Agent
Generates media assets, posts to all platforms, updates website.
All third-party imports are inside methods with try/except.
"""
import json
import time
import os
import datetime
from pathlib import Path
from agents.base_agent import NexusAgent
from agents.ai_client  import ai_image, ai_tts


class HeraldAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are HERALD, NEXUS NOW's publishing agent. "
        "Optimise content for maximum reach on every platform."
    )

    def __init__(self):
        super().__init__("herald_publisher", "publishing")
        self.gh_user    = os.environ.get("NEXUS_GITHUB_USERNAME", "nexus-now")
        self.tw_key     = os.environ.get("TWITTER_API_KEY",      "")
        self.tw_secret  = os.environ.get("TWITTER_API_SECRET",   "")
        self.tw_token   = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        self.tw_tsecret = os.environ.get("TWITTER_ACCESS_SECRET","")
        self.ig_token   = os.environ.get("INSTAGRAM_TOKEN",       "")
        self.ig_id      = os.environ.get("INSTAGRAM_BUSINESS_ID", "")
        self.yt_creds   = os.environ.get("YOUTUBE_CREDENTIALS_JSON","")
        self.news_json  = Path("news.json")

    # ── HELPERS ───────────────────────────────────────────────────────────
    def _slug(self, content: dict) -> str:
        text = content.get("copyright_id",
               content.get("headline", "article"))[:40]
        return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")

    # ── MEDIA GENERATION ──────────────────────────────────────────────────
    def make_thumbnail(self, content: dict, slug: str) -> str | None:
        prompt = content.get(
            "thumbnail_prompt",
            f"Professional breaking news thumbnail: dark dramatic background, "
            f"bold white text '{content.get('headline','')}', red NEXUS NOW "
            f"branding, broadcast TV aesthetic, high contrast"
        )
        path = ai_image(prompt, slug)
        if path:
            self.log(f"Thumbnail: {path}")
        return path

    def make_voiceover(self, content: dict, slug: str) -> str | None:
        script = content.get("video_script", "")
        if not script:
            return None
        path = ai_tts(script, slug)
        if path:
            self.log(f"Voiceover: {path}")
        return path

    # ── TWITTER ───────────────────────────────────────────────────────────
    def post_twitter(self, content: dict) -> dict:
        if not self.tw_key:
            self.log("Twitter: no credentials — skipping")
            return {"platform": "twitter", "status": "skipped"}
        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=self.tw_key,
                consumer_secret=self.tw_secret,
                access_token=self.tw_token,
                access_token_secret=self.tw_tsecret,
                wait_on_rate_limit=True
            )
            tweets  = content.get("tweet_thread", [])
            if not tweets:
                return {"platform": "twitter", "status": "skipped"}
            prev_id = None
            last_id = None
            for tweet in tweets:
                tweet = str(tweet)[:280]
                if prev_id:
                    r = client.create_tweet(
                        text=tweet, in_reply_to_tweet_id=prev_id)
                else:
                    r = client.create_tweet(text=tweet)
                prev_id = r.data["id"]
                last_id = prev_id
                time.sleep(2)
            url = f"https://twitter.com/NexusNow/status/{last_id}"
            self.log(f"Twitter: {len(tweets)} tweets → {url}")
            return {"platform": "twitter", "status": "success", "url": url}
        except Exception as e:
            self.log(f"Twitter error: {e}")
            return {"platform": "twitter", "status": "error", "error": str(e)}

    # ── INSTAGRAM ─────────────────────────────────────────────────────────
    def post_instagram(self, content: dict, thumb_path: str | None) -> dict:
        if not self.ig_token or not thumb_path:
            self.log("Instagram: no token or image — skipping")
            return {"platform": "instagram", "status": "skipped"}
        try:
            import requests as _req
            caption = content.get("instagram_caption", "")[:2200]
            img_url = (
                f"https://{self.gh_user}.github.io/news/{thumb_path}"
            )
            # Create media container
            r1 = _req.post(
                f"https://graph.facebook.com/v19.0/{self.ig_id}/media",
                data={"image_url": img_url,
                      "caption":   caption,
                      "access_token": self.ig_token},
                timeout=30
            )
            cid = r1.json().get("id")
            if not cid:
                raise ValueError(f"No container: {r1.text[:200]}")
            time.sleep(10)  # Wait for processing
            # Publish
            r2 = _req.post(
                f"https://graph.facebook.com/v19.0/{self.ig_id}/media_publish",
                data={"creation_id": cid, "access_token": self.ig_token},
                timeout=30
            )
            post_id = r2.json().get("id")
            self.log(f"Instagram: post_id={post_id}")
            return {"platform": "instagram", "status": "success",
                    "post_id": post_id}
        except Exception as e:
            self.log(f"Instagram error: {e}")
            return {"platform": "instagram", "status": "error", "error": str(e)}

    # ── YOUTUBE ───────────────────────────────────────────────────────────
    def post_youtube(self, content: dict, video_path: str,
                     thumb_path: str | None) -> dict:
        if not self.yt_creds or not video_path or not Path(video_path).exists():
            self.log("YouTube: no credentials/video — skipping")
            return {"platform": "youtube", "status": "skipped"}
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
            body = {
                "snippet": {
                    "title": content.get("youtube_title",
                             content.get("headline",""))[:100],
                    "description": content.get("youtube_description",""),
                    "tags":        content.get("youtube_tags", []),
                    "categoryId":  "25",
                },
                "status": {"privacyStatus":         "public",
                           "selfDeclaredMadeForKids": False}
            }
            media = MediaFileUpload(video_path,
                                    mimetype="video/mp4", resumable=True)
            req  = yt.videos().insert(
                part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
            vid_id = resp.get("id")
            if thumb_path and Path(thumb_path).exists():
                yt.thumbnails().set(
                    videoId=vid_id,
                    media_body=MediaFileUpload(thumb_path)
                ).execute()
            url = f"https://youtube.com/watch?v={vid_id}"
            self.log(f"YouTube: {url}")
            return {"platform": "youtube", "status": "success", "url": url}
        except Exception as e:
            self.log(f"YouTube error: {e}")
            return {"platform": "youtube", "status": "error", "error": str(e)}

    # ── WEBSITE ───────────────────────────────────────────────────────────
    def update_website(self, articles: list[dict]) -> bool:
        """Write new articles into news.json for the GitHub Pages website."""
        existing = []
        if self.news_json.exists():
            try:
                existing = json.loads(self.news_json.read_text())
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []

        new_items = []
        for r in articles:
            if not r or not r.get("headline"):
                continue
            slug = "".join(
                c if c.isalnum() else "-"
                for c in r.get("headline","")[:40].lower()
            ).strip("-")
            new_items.append({
                "title":        r.get("headline", ""),
                "subheadline":  r.get("subheadline", ""),
                "category":     r.get("category", "World"),
                "agent":        r.get("agent", "NEXUS NOW"),
                "summary":      r.get("summary", ""),
                "key_facts":    r.get("key_facts", []),
                "tags":         r.get("tags", []),
                "quality_score":r.get("quality_score", 0),
                "copyright_id": r.get("copyright_id", ""),
                "verification": r.get("verification_badge", ""),
                "slug":         slug,
                "time":         datetime.datetime.utcnow().strftime(
                                    "%b %d, %Y · %H:%M UTC"),
                "timestamp":    datetime.datetime.utcnow().isoformat(),
                "ai_generated": True,
            })

        combined = (new_items + existing)[:100]
        try:
            self.news_json.write_text(
                json.dumps(combined, indent=2, ensure_ascii=False)
            )
            self.log(f"Website: +{len(new_items)} articles "
                     f"({len(combined)} total in news.json)")
            return True
        except Exception as e:
            self.log(f"Website update error: {e}")
            return False

    # ── MASTER PUBLISH ────────────────────────────────────────────────────
    def publish_all(self, content: dict,
                    video_path: str | None = None) -> dict:
        """Publish one content package to all platforms."""
        self.increment_run()
        slug = self._slug(content)

        # Generate media assets
        thumb_path = self.make_thumbnail(content, slug)
        self.make_voiceover(content, slug)

        results: dict = {
            "headline":  content.get("headline"),
            "agent":     content.get("agent"),
            "category":  content.get("category"),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "platforms": {}
        }

        # 1. Website (always works — just writes a file)
        ok = self.update_website([content])
        results["platforms"]["website"] = {
            "status": "success" if ok else "failed"
        }

        # 2. Twitter
        results["platforms"]["twitter"] = self.post_twitter(content)
        time.sleep(3)

        # 3. Instagram
        results["platforms"]["instagram"] = self.post_instagram(
            content, thumb_path)
        time.sleep(3)

        # 4. YouTube (only if a video file was provided)
        if video_path:
            results["platforms"]["youtube"] = self.post_youtube(
                content, video_path, thumb_path)

        statuses = {k: v.get("status")
                    for k, v in results["platforms"].items()}
        self.log(f"Published: {statuses}")
        return results
