"""
NEXUS NOW — Master Orchestrator v2
Includes: free AI failover, storage management, AEGIS verification
"""
import os, json, time, datetime
from pathlib import Path

from agents.scout_agent      import ScoutAgent
from agents.category_agents  import get_agent_for_category, get_all_agents
from agents.herald_agent     import HeraldAgent
from agents.aegis_agent      import AegisAgent
from agents.storage_manager  import (run_storage_maintenance, save_article_to_sheets,
                                     log_to_sheets, upload_to_drive)

POSTS_PER_RUN = int(os.environ.get("POSTS_PER_RUN", "2"))
LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline.log"
RESULTS_FILE = Path("pipeline_results.json")

def log(msg):
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")
    try: log_to_sheets("ORCHESTRATOR", msg)
    except: pass

def run_nexus_pipeline():
    start = datetime.datetime.utcnow()
    log("="*70)
    log("NEXUS NOW — PIPELINE v2 STARTING")
    log(f"Time: {start.isoformat()} UTC | Posts: {POSTS_PER_RUN}")
    log("="*70)

    # PRE-FLIGHT
    log("\n[PRE-FLIGHT] Storage Maintenance")
    health = run_storage_maintenance()
    if health["status"] == "critical":
        log("STORAGE CRITICAL — emergency cleanup ran")

    # STEP 1: SCOUT
    log("\n[STEP 1] SCOUT: Trend Detection")
    scout = ScoutAgent()
    topics = scout.run(geo="US", n=POSTS_PER_RUN)
    if not topics:
        log("ABORT: No trends detected"); return []

    herald = HeraldAgent()
    aegis  = AegisAgent()
    results = []

    for i, trend in enumerate(topics, 1):
        topic = trend["topic"]; category = trend["category"]
        log(f"\n[{i}/{len(topics)}] '{topic}' -> {category.upper()}")

        # STEP 2: Specialist writes
        specialist = get_agent_for_category(category)
        log(f"  Agent: {specialist.agent_id} Gen={specialist.memory.get('generation',0)} Avg={specialist.memory.get('avg_quality',0):.1f}")
        try:
            content = specialist.research_and_write(topic, trend)
            if not content: log("  empty content skip"); continue
            log(f"  Written: '{content.get('headline')}' Q={content.get('quality_score',0):.1f}")
        except Exception as e:
            log(f"  Specialist error: {e}"); continue

        # STEP 3: AEGIS
        log("  [AEGIS] Verifying + copyrighting...")
        content = aegis.process(content)
        if content.get("aegis_blocked"):
            log(f"  BLOCKED: {content.get('aegis_block_reason','')}"); continue
        log(f"  AEGIS: {content.get('verification_badge')} ID={content.get('copyright_id')}")

        # STEP 4: HERALD publishes
        log("  [HERALD] Publishing...")
        video_path = os.environ.get("VIDEO_PATH_OVERRIDE")
        pub = herald.publish_all(content, video_path=video_path)
        content["publish_result"] = pub
        plats = pub.get("platforms", {})
        content["youtube_url"]   = plats.get("youtube",  {}).get("url","")
        content["twitter_url"]   = plats.get("twitter",  {}).get("url","")
        content["instagram_url"] = plats.get("instagram",{}).get("url","")

        # STEP 5: Save to Sheets
        try: save_article_to_sheets(content)
        except: pass

        # STEP 6: Upload media to Drive
        slug = content.get("copyright_id", "file")
        for mf, mime, days in [(f"assets/images/{slug}.jpg","image/jpeg",30),
                                (f"assets/audio/{slug}.mp3","audio/mpeg",14)]:
            if Path(mf).exists():
                try: upload_to_drive(mf, Path(mf).name, mime, days)
                except: pass

        results.append(content)
        log(f"  DONE: '{content.get('headline')}'")
        if i < len(topics):
            log("  pause 15s..."); time.sleep(15)

    # POST-FLIGHT
    duration = (datetime.datetime.utcnow() - start).seconds
    summary = {
        "run_timestamp": start.isoformat(), "duration_secs": duration,
        "posts_published": len(results), "storage_health": health["status"],
        "stories": [{"headline":r.get("headline"), "category":r.get("category"),
                     "quality":r.get("quality_score"), "copyright_id":r.get("copyright_id"),
                     "verification":r.get("verification_badge")} for r in results]
    }
    existing = []
    if RESULTS_FILE.exists():
        try: existing = json.loads(RESULTS_FILE.read_text())
        except: pass
    RESULTS_FILE.write_text(json.dumps([summary]+existing[:99], indent=2))
    log(f"\nPIPELINE COMPLETE | {len(results)} stories | {duration}s | Storage: {health['status']}")
    return results

if __name__ == "__main__":
    run_nexus_pipeline()
