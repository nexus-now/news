"""
NEXUS NOW - HERALD: Publisher Agent
Generates media, posts to Twitter/Instagram/YouTube, updates news.json.
All platform imports are inside try/except — nothing crashes if credentials missing.
"""
import json, time, os, datetime
from pathlib import Path
from agents.base_agent import NexusAgent
from agents.ai_client  import ai_image, ai_tts


class HeraldAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = "You are HERALD, NEXUS NOW's publishing agent."

    def __init__(self):
        super().__init__("herald_publisher", "publishing")
        self.gh_user    = os.environ.get("NEXUS_GITHUB_USERNAME", "nexus-now")
        self.tw_key     = os.environ.get("TWITTER_API_KEY",       "")
        self.tw_secret  = os.environ.get("TWITTER_API_SECRET",    "")
        self.tw_token   = os.environ.get("TWITTER_ACCESS_TOKEN",  "")
        self.tw_tsecret = os.environ.get("TWITTER_ACCESS_SECRET", "")
        self.ig_token   = os.environ.get("INSTAGRAM_TOKEN",        "")
        self.ig_id      = os.environ.get("INSTAGRAM_BUSINESS_ID",  "")
        self.yt_creds   = os.environ.get("YOUTUBE_CREDENTIALS_JSON","")
        self.news_json  = Path("news.json")

    def _slug(self, c: dict) -> str:
        t = c.get("copyright_id", c.get("headline","article"))[:40]
        return "".join(ch if ch.isalnum() else "-" for ch in t.lower()).strip("-")

    # ── MEDIA ─────────────────────────────────────────────────────────────
    def make_thumbnail(self, c: dict, slug: str) -> str | None:
        prompt = c.get("thumbnail_prompt",
            f"Professional breaking news thumbnail: dark dramatic background, "
            f"bold white headline text, red NEXUS NOW logo branding, "
            f"broadcast TV news aesthetic, story: {c.get('headline','')[:50]}")
        path = ai_image(prompt, slug)
        if path: self.log(f"Thumbnail: {path}")
        return path

    def make_audio(self, c: dict, slug: str) -> str | None:
        script = c.get("video_script","")
        if not script: return None
        path = ai_tts(script, slug)
        if path: self.log(f"Audio: {path}")
        return path

    # ── TWITTER ───────────────────────────────────────────────────────────
    def post_twitter(self, c: dict) -> dict:
        if not self.tw_key:
            self.log("Twitter: skipped (no credentials)")
            return {"platform":"twitter","status":"skipped"}
        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=self.tw_key, consumer_secret=self.tw_secret,
                access_token=self.tw_token, access_token_secret=self.tw_tsecret,
                wait_on_rate_limit=True)
            tweets = c.get("tweet_thread",[])
            if not tweets:
                return {"platform":"twitter","status":"skipped"}
            prev, last = None, None
            for tw in tweets:
                tw = str(tw)[:280]
                r  = client.create_tweet(text=tw, in_reply_to_tweet_id=prev) if prev \
                     else client.create_tweet(text=tw)
                prev = last = r.data["id"]
                time.sleep(2)
            url = f"https://twitter.com/NexusNow/status/{last}"
            self.log(f"Twitter: {len(tweets)} tweets → {url}")
            return {"platform":"twitter","status":"success","url":url}
        except Exception as e:
            self.log(f"Twitter error: {e}")
            return {"platform":"twitter","status":"error","error":str(e)}

    # ── INSTAGRAM ─────────────────────────────────────────────────────────
    def post_instagram(self, c: dict, thumb: str | None) -> dict:
        if not self.ig_token or not thumb:
            self.log("Instagram: skipped (no token or image)")
            return {"platform":"instagram","status":"skipped"}
        try:
            import requests as rq
            caption = c.get("instagram_caption","")[:2200]
            img_url = f"https://{self.gh_user}.github.io/news/{thumb}"
            r1 = rq.post(f"https://graph.facebook.com/v19.0/{self.ig_id}/media",
                         data={"image_url":img_url,"caption":caption,
                               "access_token":self.ig_token}, timeout=30)
            cid = r1.json().get("id")
            if not cid: raise ValueError(f"No container: {r1.text[:150]}")
            time.sleep(10)
            r2 = rq.post(f"https://graph.facebook.com/v19.0/{self.ig_id}/media_publish",
                         data={"creation_id":cid,"access_token":self.ig_token}, timeout=30)
            pid = r2.json().get("id")
            self.log(f"Instagram: post={pid}")
            return {"platform":"instagram","status":"success","post_id":pid}
        except Exception as e:
            self.log(f"Instagram error: {e}")
            return {"platform":"instagram","status":"error","error":str(e)}

    # ── YOUTUBE ───────────────────────────────────────────────────────────
    def post_youtube(self, c: dict, video: str, thumb: str | None) -> dict:
        if not self.yt_creds or not video or not Path(video).exists():
            self.log("YouTube: skipped (no credentials or video file)")
            return {"platform":"youtube","status":"skipped"}
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
                client_secret=creds_data.get("client_secret"))
            yt   = build("youtube","v3",credentials=creds)
            body = {
                "snippet":{"title":c.get("youtube_title",c.get("headline",""))[:100],
                           "description":c.get("youtube_description",""),
                           "tags":c.get("youtube_tags",[]),"categoryId":"25"},
                "status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
            req  = yt.videos().insert(part="snippet,status",body=body,
                       media_body=MediaFileUpload(video,mimetype="video/mp4",resumable=True))
            resp = None
            while resp is None: _, resp = req.next_chunk()
            vid  = resp.get("id")
            if thumb and Path(thumb).exists():
                yt.thumbnails().set(videoId=vid,
                    media_body=MediaFileUpload(thumb)).execute()
            url = f"https://youtube.com/watch?v={vid}"
            self.log(f"YouTube: {url}")
            return {"platform":"youtube","status":"success","url":url}
        except Exception as e:
            self.log(f"YouTube error: {e}")
            return {"platform":"youtube","status":"error","error":str(e)}

    # ── WEBSITE ───────────────────────────────────────────────────────────
    def update_website(self, articles: list) -> bool:
        existing = []
        if self.news_json.exists():
            try:
                existing = json.loads(self.news_json.read_text())
                if not isinstance(existing, list): existing = []
            except Exception: existing = []

        new_items = []
        for r in articles:
            if not r or not r.get("headline"): continue
            slug = "".join(ch if ch.isalnum() else "-"
                           for ch in r.get("headline","")[:40].lower()).strip("-")
            new_items.append({
                "title":         r.get("headline",""),
                "subheadline":   r.get("subheadline",""),
                "category":      r.get("category","World"),
                "agent":         r.get("agent","NEXUS NOW"),
                "summary":       r.get("summary",""),
                "key_facts":     r.get("key_facts",[]),
                "deep_analysis": r.get("deep_analysis",""),
                "tags":          r.get("tags",[]),
                "quality_score": r.get("quality_score",0),
                "copyright_id":  r.get("copyright_id",""),
                "verification":  r.get("verification_badge",""),
                "slug":          slug,
                "time":          datetime.datetime.utcnow().strftime("%b %d, %Y · %H:%M UTC"),
                "timestamp":     datetime.datetime.utcnow().isoformat(),
                "ai_generated":  True,
            })

        combined = (new_items + existing)[:100]
        try:
            self.news_json.write_text(
                json.dumps(combined, indent=2, ensure_ascii=False))
            self.log(f"news.json: +{len(new_items)} ({len(combined)} total)")
            return True
        except Exception as e:
            self.log(f"news.json write error: {e}")
            return False

    # ── PUBLISH ALL ───────────────────────────────────────────────────────
    def publish_all(self, c: dict, video_path: str | None = None) -> dict:
        self.increment_run()
        slug  = self._slug(c)
        thumb = self.make_thumbnail(c, slug)
        self.make_audio(c, slug)

        res = {"headline":c.get("headline"),"timestamp":
               datetime.datetime.utcnow().isoformat(),"platforms":{}}

        res["platforms"]["website"]   = {"status":"success" if self.update_website([c]) else "failed"}
        res["platforms"]["twitter"]   = self.post_twitter(c)
        time.sleep(3)
        res["platforms"]["instagram"] = self.post_instagram(c, thumb)
        time.sleep(3)
        if video_path:
            res["platforms"]["youtube"] = self.post_youtube(c, video_path, thumb)

        self.log(f"Published: { {k:v.get('status') for k,v in res['platforms'].items()} }")
        return res
