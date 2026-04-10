"""
NEXUS NOW — Master Orchestrator
Runs twice daily via GitHub Actions.
SCOUT → Specialist Agent → AEGIS → HERALD → news.json updated → website live
"""
import os
import json
import time
import datetime
from pathlib import Path

from agents.scout_agent     import ScoutAgent
from agents.category_agents import get_agent
from agents.aegis_agent     import AegisAgent
from agents.herald_agent    import HeraldAgent

POSTS_PER_RUN = int(os.environ.get("POSTS_PER_RUN", "2"))
LOG_DIR       = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE      = LOG_DIR / "pipeline.log"
RESULTS_FILE  = Path("pipeline_results.json")


def log(msg: str):
    ts   = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def cleanup_old_assets(max_age_days: int = 7):
    """Delete media files older than N days to keep the repo lean."""
    now    = time.time()
    cutoff = now - (max_age_days * 86400)
    removed = 0
    for folder in ["assets/images", "assets/audio"]:
        p = Path(folder)
        if not p.exists():
            continue
        for f in p.iterdir():
            if f.is_file() and f.suffix != ".gitkeep":
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
    if removed:
        log(f"Cleanup: removed {removed} old media files")


def run():
    start = datetime.datetime.utcnow()
    log("=" * 60)
    log("NEXUS NOW PIPELINE STARTING")
    log(f"Posts per run: {POSTS_PER_RUN}")
    log(f"Gemini key:  {'YES' if os.environ.get('GEMINI_API_KEY') else 'MISSING'}")
    log(f"Groq key:    {'YES' if os.environ.get('GROQ_API_KEY') else 'No'}")
    log(f"Twitter:     {'YES' if os.environ.get('TWITTER_API_KEY') else 'No'}")
    log(f"Instagram:   {'YES' if os.environ.get('INSTAGRAM_TOKEN') else 'No'}")
    log(f"YouTube:     {'YES' if os.environ.get('YOUTUBE_CREDENTIALS_JSON') else 'No'}")
    log("=" * 60)

    # Ensure directories exist
    for d in ["agent_memory", "agent_memory/training",
              "assets/images", "assets/audio", "logs"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Clean up old assets
    cleanup_old_assets(max_age_days=7)

    # ── STEP 1: SCOUT ─────────────────────────────────────────────────────
    log("\n[STEP 1] SCOUT — Trend Detection")
    try:
        scout  = ScoutAgent()
        trends = scout.run(n=POSTS_PER_RUN)
        log(f"Scout found {len(trends)} topics")
    except Exception as e:
        log(f"SCOUT FAILED: {e} — using fallback topics")
        trends = [
            {"topic": "artificial intelligence latest developments 2026",
             "category": "technology", "agent": "VOLT",
             "angle": "AI industry impact", "why": "Global interest"},
            {"topic": "global economy markets outlook 2026",
             "category": "business", "agent": "TITAN",
             "angle": "Market movements", "why": "Daily financial news"},
        ]

    # ── STEPS 2-4: PER STORY ──────────────────────────────────────────────
    aegis   = AegisAgent()
    herald  = HeraldAgent()
    results = []

    for i, trend in enumerate(trends[:POSTS_PER_RUN], 1):
        topic    = trend.get("topic", "")
        category = trend.get("category", "technology")
        log(f"\n[STORY {i}/{POSTS_PER_RUN}] {category.upper()}: {topic[:60]}")

        # STEP 2: Specialist writes content
        content = None
        try:
            specialist = get_agent(category)
            log(f"  Agent: {specialist.agent_id} "
                f"Gen={specialist.memory.get('generation',0)} "
                f"AvgQ={specialist.memory.get('avg_quality',0):.1f}/10")
            content = specialist.research_and_write(topic, trend)
            if not content or not content.get("headline"):
                raise ValueError("Empty content")
            log(f"  Written: '{content['headline'][:55]}' "
                f"Q={content.get('quality_score',0):.1f}/10")
        except Exception as e:
            log(f"  Specialist failed: {e} — using fallback content")
            content = {
                "agent":       trend.get("agent", "NEXUS"),
                "category":    category,
                "headline":    f"Breaking: {topic[:70]}",
                "subheadline": "Developing story — NEXUS NOW",
                "summary":     (f"NEXUS NOW is tracking this developing story about {topic}. "
                                f"Our AI agents are researching and will update shortly."),
                "key_facts":   [f"Topic: {topic}", "Story developing", "Updates coming"],
                "deep_analysis": f"This story about {topic} is being actively monitored.",
                "video_script":  f"Welcome to NEXUS NOW. Breaking coverage on {topic}.",
                "youtube_title": f"{topic[:55]} | NEXUS NOW 2026",
                "youtube_description": f"NEXUS NOW covers {topic}. Latest AI-generated news.",
                "youtube_tags": ["nexusnow", "news", "breaking", "2026", category],
                "instagram_caption": (f"🔴 BREAKING: {topic[:100]}\n\n"
                                      f"Follow @nexusnow for live updates.\n"
                                      f"#NexusNow #News #Breaking"),
                "tweet_thread": [
                    f"🔴 NEXUS NOW: Tracking '{topic[:200]}' — Thread 1/3",
                    f"Our AI agents are researching this story now. 2/3",
                    f"Follow @NexusNow for real-time updates. #NexusNow 3/3",
                ],
                "thumbnail_prompt": (f"Professional breaking news thumbnail, dark background, "
                                     f"bold white text, red NEXUS NOW branding, dramatic"),
                "tags":         [category, "news", "nexusnow"],
                "quality_score": 4.0,
            }

        # STEP 3: AEGIS verifies + stamps copyright
        try:
            content = aegis.stamp(content)
            log(f"  AEGIS: {content.get('verification_badge','?')} "
                f"ID={content.get('copyright_id','?')}")
        except Exception as e:
            log(f"  AEGIS error (non-fatal): {e}")
            content["copyright_id"]       = f"NN-FALLBACK-{i}"
            content["verification_badge"]  = "🔍 UNVERIFIED"
            content["verification_status"] = "UNVERIFIED"

        # STEP 4: HERALD publishes
        try:
            pub = herald.publish_all(content, video_path=None)
            statuses = {k: v.get("status")
                        for k, v in pub.get("platforms", {}).items()}
            log(f"  Published: {statuses}")
            content["publish_result"] = pub
        except Exception as e:
            log(f"  Herald error: {e}")
            # Fallback: at minimum update the website
            try:
                herald.update_website([content])
                log("  Website updated via fallback")
            except Exception as e2:
                log(f"  Website fallback also failed: {e2}")

        results.append(content)

        if i < len(trends[:POSTS_PER_RUN]):
            log("  Pausing 10s between stories...")
            time.sleep(10)

    # ── SAVE RESULTS ──────────────────────────────────────────────────────
    duration = int((datetime.datetime.utcnow() - start).total_seconds())
    summary  = {
        "timestamp":       start.isoformat(),
        "duration_secs":   duration,
        "posts_published": len(results),
        "stories": [
            {
                "headline":    r.get("headline", ""),
                "category":    r.get("category", ""),
                "agent":       r.get("agent", ""),
                "quality":     r.get("quality_score", 0),
                "copyright_id":r.get("copyright_id", ""),
                "verified":    r.get("verification_status", ""),
            }
            for r in results
        ],
    }

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
    log(f"PIPELINE COMPLETE: {len(results)} stories in {duration}s")
    if results:
        avg = sum(r.get("quality_score", 0) for r in results) / len(results)
        log(f"Average quality: {avg:.1f}/10")
    log("=" * 60)
    return results


if __name__ == "__main__":
    run()
