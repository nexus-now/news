"""
NEXUS NOW — Free Google Workspace Storage Manager
===================================================
Uses ONLY free resources that come with any Gmail account:

  Google Drive     — 15 GB free (shared across Gmail, Drive, Photos)
  Google Sheets    — Unlimited free (used as database + logs)
  Google Docs      — Unlimited free (article archive)
  Gmail            — 15 GB included in the 15 GB above

STRATEGY:
  - Agent memories      → Google Sheets (structured, searchable)
  - Published articles  → Google Sheets (master database)
  - Video files         → Google Drive (auto-delete after 30 days)
  - Audio files         → Google Drive (auto-delete after 14 days)
  - Thumbnails          → Google Drive (auto-delete after 30 days)
  - Pipeline logs       → Google Sheets (last 500 rows only)
  - GitHub repo         → Only JSON files (tiny, < 1MB total)

AUTO-CLEANUP RULES:
  - Media files older than 30 days → deleted automatically
  - Log entries beyond 500 → oldest trimmed
  - Agent memories → only last 50 performance entries kept
  - Google Drive → never exceeds 10 GB (alert at 12 GB)
  - GitHub repo  → never stores binary files

FREE QUOTA SUMMARY:
  Google Drive API    : 1 billion requests/day (free)
  Google Sheets API   : 300 requests/min/project (free)
  Google Docs API     : 300 requests/min/project (free)
  All require OAuth2  : one-time setup
"""

import os
import json
import datetime
from pathlib import Path


# ── SHEET IDs (set these after creating sheets in your Google account) ─────
SHEET_IDS = {
    "articles":    os.environ.get("SHEET_ID_ARTICLES",    ""),
    "agent_memory":os.environ.get("SHEET_ID_AGENT_MEMORY",""),
    "pipeline_log":os.environ.get("SHEET_ID_PIPELINE_LOG",""),
    "provider_quotas": os.environ.get("SHEET_ID_QUOTAS", ""),
    "storage_audit": os.environ.get("SHEET_ID_STORAGE",  ""),
}
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")  # Main NEXUS NOW folder


def get_sheets_service():
    """Get authenticated Google Sheets service."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds_json = os.environ.get("GOOGLE_WORKSPACE_CREDENTIALS", "{}")
        creds_data = json.loads(creds_json)
        creds = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )
        return build("sheets", "v4", credentials=creds)
    except Exception as e:
        print(f"[STORAGE] Sheets auth failed: {e}")
        return None

def get_drive_service():
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds_json = os.environ.get("GOOGLE_WORKSPACE_CREDENTIALS", "{}")
        creds_data = json.loads(creds_json)
        creds = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"[STORAGE] Drive auth failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# ARTICLE DATABASE (Google Sheets)
# ═══════════════════════════════════════════════════════════════════════════
def save_article_to_sheets(article: dict) -> bool:
    """Append one article row to the Articles master sheet."""
    svc = get_sheets_service()
    if not svc or not SHEET_IDS["articles"]:
        return False
    try:
        row = [
            article.get("headline", ""),
            article.get("category", ""),
            article.get("agent", ""),
            article.get("summary", "")[:500],
            article.get("quality_score", 0),
            str(article.get("youtube_url", "")),
            str(article.get("twitter_url", "")),
            str(article.get("instagram_url", "")),
            datetime.datetime.utcnow().isoformat(),
            json.dumps(article.get("key_facts", [])),
            article.get("copyright_id", ""),
        ]
        svc.spreadsheets().values().append(
            spreadsheetId=SHEET_IDS["articles"],
            range="Articles!A:K",
            valueInputOption="RAW",
            body={"values": [row]}
        ).execute()
        return True
    except Exception as e:
        print(f"[STORAGE] Sheets article save failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE LOG (Google Sheets — capped at 500 rows)
# ═══════════════════════════════════════════════════════════════════════════
def log_to_sheets(agent: str, message: str, status: str = "info"):
    """Append log line to pipeline log sheet. Auto-trims to 500 rows."""
    svc = get_sheets_service()
    if not svc or not SHEET_IDS["pipeline_log"]:
        return
    try:
        row = [
            datetime.datetime.utcnow().isoformat(),
            agent, message, status
        ]
        sheet_id = SHEET_IDS["pipeline_log"]
        svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Log!A:D",
            valueInputOption="RAW",
            body={"values": [row]}
        ).execute()

        # Trim if over 500 rows (keep rows 1 header + last 499)
        result = svc.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="Log!A:A"
        ).execute()
        n_rows = len(result.get("values", []))
        if n_rows > 501:
            # Delete oldest rows
            to_delete = n_rows - 500
            svc.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={
                "requests": [{
                    "deleteDimension": {
                        "range": {"sheetId":0, "dimension":"ROWS",
                                  "startIndex":1, "endIndex": 1 + to_delete}
                    }
                }]
            }).execute()
    except Exception as e:
        print(f"[STORAGE] Sheets log failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# GOOGLE DRIVE MEDIA STORAGE
# Auto-uploads and auto-deletes old files
# ═══════════════════════════════════════════════════════════════════════════
def upload_to_drive(local_path: str, filename: str, mime_type: str,
                    days_to_keep: int = 30) -> str | None:
    """
    Upload a media file to Google Drive.
    Stores expiry date in file description for auto-cleanup.
    Returns the public URL.
    """
    drive = get_drive_service()
    if not drive or not DRIVE_FOLDER_ID:
        return None
    try:
        from googleapiclient.http import MediaFileUpload
        expiry = (datetime.datetime.utcnow() +
                  datetime.timedelta(days=days_to_keep)).isoformat()
        meta = {
            "name":        filename,
            "parents":     [DRIVE_FOLDER_ID],
            "description": f"NEXUS NOW | expires:{expiry}"
        }
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
        file  = drive.files().create(
            body=meta, media_body=media,
            fields="id, webViewLink, webContentLink"
        ).execute()
        file_id = file.get("id")

        # Make publicly viewable
        drive.permissions().create(
            fileId=file_id,
            body={"role":"reader","type":"anyone"}
        ).execute()

        url = f"https://drive.google.com/uc?id={file_id}"
        print(f"[STORAGE] Drive upload: {filename} → {url}")
        return url
    except Exception as e:
        print(f"[STORAGE] Drive upload failed: {e}")
        return None

def cleanup_expired_drive_files():
    """
    Delete Drive files whose expiry date has passed.
    Run this at the start of every pipeline run.
    """
    drive = get_drive_service()
    if not drive or not DRIVE_FOLDER_ID:
        return
    try:
        results = drive.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name, description, size)",
            pageSize=200
        ).execute()

        now     = datetime.datetime.utcnow()
        deleted = 0
        freed_mb= 0
        for f in results.get("files", []):
            desc = f.get("description", "")
            if "expires:" in desc:
                expiry_str = desc.split("expires:")[1].strip()[:26]
                try:
                    expiry = datetime.datetime.fromisoformat(expiry_str)
                    if now > expiry:
                        size = int(f.get("size", 0))
                        drive.files().delete(fileId=f["id"]).execute()
                        deleted  += 1
                        freed_mb += size / (1024*1024)
                        print(f"[STORAGE] Deleted expired: {f['name']} ({size//1024}KB)")
                except:
                    pass
        if deleted:
            print(f"[STORAGE] Cleanup complete: {deleted} files deleted, {freed_mb:.1f} MB freed")
    except Exception as e:
        print(f"[STORAGE] Cleanup error: {e}")

def get_drive_usage_mb() -> float:
    """Return current Drive usage in MB."""
    drive = get_drive_service()
    if not drive:
        return 0.0
    try:
        info = drive.about().get(fields="storageQuota").execute()
        used = int(info["storageQuota"].get("usage", 0))
        return used / (1024 * 1024)
    except:
        return 0.0

def check_storage_health() -> dict:
    """
    Check all storage systems are healthy.
    Returns warnings if approaching limits.
    """
    health = {"status": "ok", "warnings": [], "usage_mb": 0}

    # Drive check
    drive_mb = get_drive_usage_mb()
    drive_gb = drive_mb / 1024
    health["drive_gb"] = round(drive_gb, 2)
    health["usage_mb"] = drive_mb

    if drive_gb > 13:
        health["warnings"].append(f"⚠️ Drive {drive_gb:.1f}GB/15GB — CRITICAL, cleanup now")
        health["status"] = "critical"
    elif drive_gb > 10:
        health["warnings"].append(f"⚠️ Drive {drive_gb:.1f}GB/15GB — running low")
        health["status"] = "warning"

    # GitHub repo check — count files in assets/
    assets = Path("assets")
    if assets.exists():
        total_size = sum(f.stat().st_size for f in assets.rglob("*") if f.is_file())
        health["repo_assets_mb"] = round(total_size / (1024*1024), 2)

    return health


# ═══════════════════════════════════════════════════════════════════════════
# LOCAL REPO CLEANUP
# Keeps GitHub repo tiny — only stores essential JSON, deletes old media
# ═══════════════════════════════════════════════════════════════════════════
def cleanup_local_assets(max_age_days_images: int = 7,
                          max_age_days_audio: int = 3):
    """
    Delete local media files older than N days.
    These should already be uploaded to Drive or published.
    Keeps the GitHub repo small.
    """
    now    = datetime.datetime.utcnow()
    deleted = 0

    for folder, max_age in [("assets/images", max_age_days_images),
                              ("assets/audio",  max_age_days_audio)]:
        p = Path(folder)
        if not p.exists():
            continue
        for f in p.iterdir():
            if f.is_file():
                age = (now - datetime.datetime.fromtimestamp(f.stat().st_mtime)).days
                if age >= max_age:
                    f.unlink()
                    deleted += 1

    if deleted:
        print(f"[STORAGE] Local cleanup: {deleted} old media files removed from repo")
    return deleted

def trim_news_json(max_articles: int = 100):
    """Keep news.json lean — max 100 articles."""
    path = Path("news.json")
    if not path.exists():
        return
    try:
        articles = json.loads(path.read_text())
        if len(articles) > max_articles:
            articles = articles[:max_articles]
            path.write_text(json.dumps(articles, indent=2))
            print(f"[STORAGE] news.json trimmed to {max_articles} articles")
    except:
        pass

def trim_agent_memories():
    """
    Keep agent memory files lean.
    Trim performance_log to last 50, prompt_history to last 10.
    """
    mem_dir = Path("agent_memory")
    if not mem_dir.exists():
        return
    for mem_file in mem_dir.glob("*.json"):
        try:
            mem = json.loads(mem_file.read_text())
            mem["performance_log"] = mem.get("performance_log", [])[-50:]
            mem["prompt_history"]  = mem.get("prompt_history",  [])[-10:]
            top = mem.get("top_performing", [])
            mem["top_performing"]  = sorted(top, key=lambda x:x.get("score",0), reverse=True)[:10]
            expertise = mem.get("category_expertise", {})
            if len(expertise) > 30:
                keys = sorted(expertise.keys())[-30:]
                mem["category_expertise"] = {k: expertise[k] for k in keys}
            mem_file.write_text(json.dumps(mem, indent=2))
        except:
            pass
    print("[STORAGE] Agent memories trimmed")


# ═══════════════════════════════════════════════════════════════════════════
# MASTER STORAGE RUN — call this at start of every pipeline
# ═══════════════════════════════════════════════════════════════════════════
def run_storage_maintenance():
    """Full storage maintenance. Run at pipeline start."""
    print("[STORAGE] Running maintenance...")
    cleanup_expired_drive_files()
    cleanup_local_assets()
    trim_news_json()
    trim_agent_memories()
    health = check_storage_health()
    print(f"[STORAGE] Health: {health['status']} | Drive: {health.get('drive_gb',0):.1f}GB/15GB")
    if health["warnings"]:
        for w in health["warnings"]:
            print(f"[STORAGE] {w}")
    return health
