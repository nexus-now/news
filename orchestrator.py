"""
NEXUS NOW — Master Orchestrator
=================================
Called by GitHub Actions twice daily.
Coordinates: SCOUT → Specialist → AEGIS → HERALD

Error handling: one agent failing never stops the whole pipeline.
The website ALWAYS updates even if social posting fails.
"""
import os
import json
import time
import datetime
from pathlib import Path

from agents.scout_agent    import ScoutAgent
from agents.category_agents import get_agent
from agents.aegis_agent    import AegisAgent
from agents.herald_agent   import HeraldAgent

# ── CONFIG ────────────────────────────────────────────────────────────────
POSTS_PER_RUN   = int(os.environ.get("POSTS_PER_RUN", "2"))
LOG_DIR         = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE        = LOG_DIR / "pipeline.log"
RESULTS_FILE    = Path("pipeline_results.json")


def log(msg: str):
    ts   = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run():
    start = datetime.datetime.utcnow()
    log("=" * 60)
    log("NEXUS NOW PIPELINE STARTING")
    log(f"Posts per run: {POSTS_PER_RUN}")
    log(f"AI Key present: {'Yes' if os.environ.get('GEMINI_API_KEY') else 'NO — pipeline will fail'}")
    log(f"Groq Key:  {'Yes' if os.environ.get('GROQ_API_KEY') else 'No (optional)'}")
    log(f"Twitter:   {'Yes' if os.environ.get('TWITTER_API_KEY') else 'No'}")
    log(f"Instagram: {'Yes' if os.environ.get('INSTAGRAM_TOKEN') else 'No'}")
    log(f"YouTube:   {'Yes' if os.environ.get('YOUTUBE_CREDENTIALS_JSON') else 'No'}")
    log("=" * 60)

    # Clean up old assets to keep repo lean
    cleanup_old_assets(max_age_days=7)

    # Ensure directories exist
    for d in ["agent_memory", "agent_memory/training",
              "assets/images", "assets/audio", "logs"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # ── STEP 1: SCOUT ─────────────────────────────────────────────────────
    log("\n[STEP 1] SCOUT — Trend Detection")
    try:
        scout  = ScoutAgent()
        trends = scout.run(n=POSTS_PER_RUN)
        log(f"Scout found {len(trends)} topics")
    except Exception as e:
        log(f"SCOUT FAILED: {e}")
        # Emergency fallback topics
        trends = [
            {"topic": "artificial intelligence latest developments 2026",
             "category": "technology", "agent": "VOLT",
             "angle": "AI industry news", "why": "Constant global interest"},
            {"topic": "global economy market update",
             "category": "business", "agent": "TITAN",
             "angle": "Market movements", "why": "Daily financial news"}
        ]
        log("Using emergency fallback topics")

    # ── STEP 2-4: PER STORY ───────────────────────────────────────────────
    aegis   = AegisAgent()
    herald  = HeraldAgent()
    results = []

    for i, trend in enumerate(trends[:POSTS_PER_RUN], 1):
        topic    = trend.get("topic", "")
        category = trend.get("category", "politics")
        log(f"\n[STORY {i}/{POSTS_PER_RUN}] {category.upper()}: {topic[:60]}")

        # STEP 2: Specialist agent writes the content
        try:
            specialist = get_agent(category)
            log(f"  Agent: {specialist.agent_id} | "
                f"Gen:{specialist.memory.get('generation',0)} | "
                f"AvgQ:{specialist.memory.get('avg_quality',0):.1f}/10")
            content = specialist.research_and_write(topic, trend)
            if not content or not content.get("headline"):
                raise ValueError("Empty content returned")
            log(f"  Written: '{content['headline'][:55]}' "
                f"Q={content.get('quality_score',0):.1f}/10")
        except Exception as e:
            log(f"  SPECIALIST FAILED: {e} — using emergency content")
            content = {
                "agent":    trend.get("agent", "NEXUS"),
                "category": category,
                "headline": f"NEXUS NOW: {topic[:60]}",
                "subheadline": "Latest developments",
                "summary":  f"NEXUS NOW is tracking {topic}. Our AI agents are compiling the full story.",
                "key_facts": [f"Topic: {topic}", "Story developing"],
                "deep_analysis": f"This developing story covers {topic}.",
                "video_script": f"Welcome to NEXUS NOW. We're following {topic}.",
                "youtube_title": f"{topic[:55]} | NEXUS NOW 2026",
                "youtube_description": f"NEXUS NOW covers {topic}.",
                "youtube_tags": ["nexusnow","news","breaking","2026"],
                "instagram_caption": f"Breaking: {topic[:100]}\n\nFollow @nexusnow\n#NexusNow #News",
                "tweet_thread": [
                    f"🔴 NEXUS NOW is tracking: {topic[:220]} 1/3",
                    f"Our AI journalists are on this story now. 2/3",
                    f"Follow @NexusNow for updates. #NexusNow #News 3/3"
                ],
                "thumbnail_prompt": f"Breaking news thumbnail: {topic[:40]}",
                "tags": [category, "news"],
                "quality_score": 4.0,
            }

        # STEP 3: AEGIS stamps verification + copyright
        try:
            content = aegis.stamp(content)
            log(f"  AEGIS: {content.get('verification_badge','?')} | "
                f"ID: {content.get('copyright_id','?')}")
        except Exception as e:
            log(f"  AEGIS error (non-fatal): {e}")
            content["copyright_id"]      = f"NN-ERROR-{i}"
            content["verification_badge"] = "🔍 UNVERIFIED"

        # STEP 4: HERALD publishes everywhere
        try:
            pub = herald.publish_all(content, video_path=None)
            content["publish_result"] = pub
            statuses = {k: v.get("status")
                        for k, v in pub.get("platforms", {}).items()}
            log(f"  Published: {statuses}")
        except Exception as e:
            log(f"  HERALD error: {e}")
            # At minimum, write to news.json directly
            try:
                herald.update_website([content])
                log("  Website updated (fallback)")
            except Exception as e2:
                log(f"  Website update also failed: {e2}")

        results.append(content)

        # Rate limit pause between stories
        if i < len(trends[:POSTS_PER_RUN]):
            log("  Pausing 10s...")
            time.sleep(10)

    # ── SAVE RUN SUMMARY ──────────────────────────────────────────────────
    duration = int((datetime.datetime.utcnow() - start).total_seconds())
    summary  = {
        "timestamp":      start.isoformat(),
        "duration_secs":  duration,
        "posts_target":   POSTS_PER_RUN,
        "posts_published":len(results),
        "stories": [
            {
                "headline":    r.get("headline",""),
                "category":    r.get("category",""),
                "agent":       r.get("agent",""),
                "quality":     r.get("quality_score",0),
                "copyright_id":r.get("copyright_id",""),
                "verified":    r.get("verification_status",""),
            }
            for r in results
        ]
    }

    # Load existing results and prepend
    existing = []
    if RESULTS_FILE.exists():
        try:
            existing = json.loads(RESULTS_FILE.read_text())
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    RESULTS_FILE.write_text(
        json.dumps([summary] + existing[:49], indent=2, ensure_ascii=False)
    )

    log("\n" + "=" * 60)
    log(f"PIPELINE COMPLETE")
    log(f"Stories published: {len(results)}/{POSTS_PER_RUN}")
    log(f"Duration: {duration}s")
    if results:
        avg_q = sum(r.get("quality_score",0) for r in results) / len(results)
        log(f"Avg quality: {avg_q:.1f}/10")
    log("=" * 60)
    return results


if __name__ == "__main__":
    run()


def cleanup_old_assets(max_age_days: int = 7):
    """
    Delete media files older than max_age_days.
    Keeps the repo lean — GitHub has a 1GB soft limit.
    news.json and agent memories are kept forever.
    """
    import time as _time
    now = _time.time()
    cutoff = now - (max_age_days * 86400)
    removed = 0
    for folder in ["assets/images", "assets/audio"]:
        p = Path(folder)
        if not p.exists():
            continue
        for f in p.iterdir():
            if f.is_file() and f.suffix not in ('.gitkeep',) and f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
    if removed:
        log(f"Cleanup: removed {removed} old media files (>{max_age_days} days old)")
