"""
NEXUS NOW - Master Orchestrator
Runs automatically via GitHub Actions twice daily.
SCOUT → Specialist → AEGIS → HERALD → news.json → website live
Every agent self-improves after every run.
"""
import os, json, time, datetime
from pathlib import Path

from agents.scout_agent     import ScoutAgent
from agents.category_agents import get_agent
from agents.aegis_agent     import AegisAgent
from agents.herald_agent    import HeraldAgent

POSTS_PER_RUN = int(os.environ.get("POSTS_PER_RUN", "2"))
LOG_FILE      = Path("logs/pipeline.log")
RESULTS_FILE  = Path("pipeline_results.json")


def log(msg: str):
    ts   = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def cleanup(max_days: int = 7):
    """Delete media files older than max_days to keep repo lean."""
    cutoff  = time.time() - max_days * 86400
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
    log(f"Gemini: {'YES' if os.environ.get('GEMINI_API_KEY') else 'MISSING - WILL FAIL'}")
    log(f"Groq:   {'YES' if os.environ.get('GROQ_API_KEY') else 'No'}")
    log(f"Twitter:{'YES' if os.environ.get('TWITTER_API_KEY') else 'No'}")
    log("=" * 60)

    # Ensure directories
    for d in ["agent_memory","assets/images","assets/audio","logs"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Cleanup old media
    cleanup(max_days=7)

    # STEP 1: SCOUT
    log("\n[STEP 1] SCOUT — Trend Detection")
    try:
        trends = ScoutAgent().run(n=POSTS_PER_RUN)
        log(f"Scout: {len(trends)} topics selected")
    except Exception as e:
        log(f"Scout failed: {e} — using fallbacks")
        trends = [
            {"topic":"artificial intelligence latest news 2026",
             "category":"technology","agent":"VOLT","angle":"AI industry impact"},
            {"topic":"global economy stock markets update 2026",
             "category":"business","agent":"TITAN","angle":"Market movements"},
        ]

    aegis, herald, results = AegisAgent(), HeraldAgent(), []

    for i, trend in enumerate(trends[:POSTS_PER_RUN], 1):
        topic    = trend.get("topic","")
        category = trend.get("category","technology")
        log(f"\n[STORY {i}/{POSTS_PER_RUN}] {category.upper()}: {topic[:60]}")

        # STEP 2: Specialist writes content
        try:
            specialist = get_agent(category)
            log(f"  Agent={specialist.agent_id} "
                f"Gen={specialist.memory.get('generation',0)} "
                f"AvgQ={specialist.memory.get('avg_quality',0):.1f}/10 "
                f"Strategy={specialist.memory.get('strategy','default')}")
            content = specialist.research_and_write(topic, trend)
            if not content or not content.get("headline"):
                raise ValueError("Empty content")
            log(f"  Written: '{content['headline'][:55]}' "
                f"Q={content.get('quality_score',0):.1f}")
        except Exception as e:
            log(f"  Specialist error: {e} — using fallback content")
            content = {
                "agent": trend.get("agent","NEXUS"), "category": category,
                "headline": f"Breaking: {topic[:70]}",
                "subheadline": "Developing — NEXUS NOW",
                "summary": f"NEXUS NOW is tracking {topic}. Updates to follow.",
                "key_facts": [f"Topic: {topic}", "Story developing"],
                "deep_analysis": f"Monitoring {topic} for updates.",
                "video_script": f"Welcome to NEXUS NOW. Tracking {topic}.",
                "youtube_title": f"{topic[:55]} | NEXUS NOW 2026",
                "youtube_description": f"NEXUS NOW covers {topic}.",
                "youtube_tags": ["nexusnow","news","breaking","2026"],
                "instagram_caption": f"🔴 {topic[:100]}\n\nFollow @nexusnow\n#NexusNow #News",
                "tweet_thread": [
                    f"🔴 NEXUS NOW tracking: {topic[:230]} 1/3",
                    f"AI agents researching now. 2/3",
                    f"Follow @NexusNow #NexusNow 3/3"],
                "thumbnail_prompt": f"Breaking news: {topic[:40]}, dark, red NEXUS NOW brand",
                "tags": [category,"news","nexusnow"],
                "quality_score": 4.0,
            }

        # STEP 3: AEGIS — verify + copyright
        try:
            content = aegis.stamp(content)
            log(f"  AEGIS: {content.get('verification_badge')} "
                f"ID={content.get('copyright_id')}")
        except Exception as e:
            log(f"  AEGIS error (non-fatal): {e}")
            content["copyright_id"]       = f"NN-ERR-{i}"
            content["verification_badge"]  = "🔍 UNVERIFIED"
            content["verification_status"] = "UNVERIFIED"

        # STEP 4: HERALD — publish
        try:
            pub = herald.publish_all(content)
            content["publish_result"] = pub
            log(f"  Published: { {k:v.get('status') for k,v in pub.get('platforms',{}).items()} }")
        except Exception as e:
            log(f"  Herald error: {e}")
            try:
                herald.update_website([content])
                log("  Website updated (fallback)")
            except Exception as e2:
                log(f"  Website fallback failed: {e2}")

        results.append(content)
        if i < POSTS_PER_RUN:
            log("  Pausing 10s...")
            time.sleep(10)

    # Save results
    duration = int((datetime.datetime.utcnow() - start).total_seconds())
    summary = {
        "timestamp": start.isoformat(),
        "duration_secs": duration,
        "posts_published": len(results),
        "stories": [{"headline":r.get("headline",""),
                     "category":r.get("category",""),
                     "agent":r.get("agent",""),
                     "quality":r.get("quality_score",0),
                     "copyright_id":r.get("copyright_id",""),
                     "strategy":r.get("strategy","")}
                    for r in results],
    }
    existing = []
    if RESULTS_FILE.exists():
        try:
            existing = json.loads(RESULTS_FILE.read_text())
            if not isinstance(existing, list): existing = []
        except Exception: pass
    RESULTS_FILE.write_text(
        json.dumps([summary]+existing[:49], indent=2, ensure_ascii=False))

    log(f"\nPIPELINE COMPLETE: {len(results)} stories in {duration}s")
    if results:
        avg = sum(r.get("quality_score",0) for r in results)/len(results)
        log(f"Average quality: {avg:.1f}/10")
    log("=" * 60)
    return results


if __name__ == "__main__":
    run()
