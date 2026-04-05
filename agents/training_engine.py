"""
NEXUS NOW — Agent Self-Training Engine
========================================
5-layer self-training system.
NOTE: Unsloth/LoRA imports removed — those only run in Google Colab offline.
This file handles the online training layers that run in GitHub Actions.
"""
import os, json, datetime, hashlib
from pathlib import Path
from agents.free_ai_provider import ai_generate

try:
    from agents.storage_manager import log_to_sheets
except Exception:
    def log_to_sheets(*a, **k): pass

TRAINING_DIR = Path("agent_memory/training")
WISDOM_POOL  = Path("agent_memory/wisdom_pool.json")
DATASET_DIR  = Path("agent_memory/datasets")
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
DATASET_DIR.mkdir(parents=True, exist_ok=True)


def _extract_json(text: str) -> str:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    for i, c in enumerate(text):
        if c in "{[":
            return text[i:]
    return text

def _score_to_tier(score: float) -> str:
    if score >= 9.0: return "ELITE"
    if score >= 8.0: return "HIGH"
    if score >= 6.5: return "MEDIUM"
    if score >= 5.0: return "LOW"
    return "POOR"

def build_training_record(agent_id, topic, content, quality_score, prompt_used):
    return {
        "id":            hashlib.md5(f"{agent_id}{topic}{datetime.datetime.utcnow().isoformat()}".encode()).hexdigest()[:12],
        "agent_id":      agent_id,
        "timestamp":     datetime.datetime.utcnow().isoformat(),
        "topic":         topic,
        "category":      content.get("category", ""),
        "quality_score": quality_score,
        "tier":          _score_to_tier(quality_score),
        "prompt_used":   prompt_used[:1000],
        "headline":      content.get("headline", ""),
        "summary":       content.get("summary", ""),
        "key_facts":     content.get("key_facts", []),
        "video_script":  content.get("video_script", "")[:300],
        "youtube_title": content.get("youtube_title", ""),
        "tweet_1":       (content.get("tweet_thread") or [""])[0][:280],
        "strengths":     content.get("_strengths", []),
        "weaknesses":    content.get("_weaknesses", []),
    }


class TrainingDataStore:
    def __init__(self, agent_id: str):
        self.agent_id  = agent_id
        self.data_file = TRAINING_DIR / f"{agent_id}.jsonl"
        self.records   = self._load()

    def _load(self):
        if not self.data_file.exists():
            return []
        records = []
        for line in self.data_file.read_text().strip().split("\n"):
            if line.strip():
                try: records.append(json.loads(line))
                except: pass
        return records

    def add(self, record: dict):
        with open(self.data_file, "a") as f:
            f.write(json.dumps(record) + "\n")
        self.records.append(record)
        if len(self.records) > 500:
            self.records = self.records[-500:]
            self.data_file.write_text("\n".join(json.dumps(r) for r in self.records) + "\n")

    def get_best(self, n=5, min_score=8.0):
        high = [r for r in self.records if r.get("quality_score", 0) >= min_score]
        return sorted(high, key=lambda x: x.get("quality_score", 0), reverse=True)[:n]

    def get_worst(self, n=3, max_score=5.5):
        low = [r for r in self.records if r.get("quality_score", 10) <= max_score]
        return sorted(low, key=lambda x: x.get("quality_score", 10))[:n]

    def build_few_shot_block(self) -> str:
        best = self.get_best(n=3, min_score=8.0)
        if not best:
            return ""
        block = "\n=== YOUR BEST PAST OUTPUTS (learn from these) ===\n"
        for i, r in enumerate(best, 1):
            block += f"\nEXAMPLE {i} — Score: {r['quality_score']}/10\n"
            block += f"Topic: {r['topic']}\nHeadline: {r['headline']}\n"
            block += f"Summary: {r.get('summary','')[:200]}\n---"
        block += "\n=== END TRAINING EXAMPLES ===\n"
        return block

    def stats(self):
        scores = [r.get("quality_score", 0) for r in self.records]
        if not scores:
            return {"total": 0, "avg": 0, "best": 0, "worst": 0, "elite_count": 0, "high_count": 0}
        return {
            "total": len(scores), "avg": round(sum(scores)/len(scores), 2),
            "best": max(scores), "worst": min(scores),
            "elite_count": sum(1 for s in scores if s >= 9.0),
            "high_count":  sum(1 for s in scores if 8.0 <= s < 9.0),
        }


class PatternExtractor:
    def __init__(self, agent_id: str, category: str):
        self.agent_id    = agent_id
        self.category    = category
        self.wisdom_file = TRAINING_DIR / f"{agent_id}_wisdom.json"
        self.wisdom      = self._load()

    def _load(self):
        if self.wisdom_file.exists():
            try: return json.loads(self.wisdom_file.read_text())
            except: pass
        return {"agent_id": self.agent_id, "category": self.category,
                "generation": 0, "rules": [], "anti_rules": [],
                "style_notes": [], "topic_insights": {}, "last_extracted": None}

    def _save(self):
        self.wisdom["rules"]       = list(set(self.wisdom["rules"]))[-40:]
        self.wisdom["anti_rules"]  = list(set(self.wisdom["anti_rules"]))[-20:]
        self.wisdom["style_notes"] = list(set(self.wisdom["style_notes"]))[-20:]
        self.wisdom_file.write_text(json.dumps(self.wisdom, indent=2))

    def extract_patterns(self, store: TrainingDataStore):
        best  = store.get_best(n=5, min_score=8.0)
        worst = store.get_worst(n=3, max_score=6.0)
        if len(best) < 2:
            return self.wisdom
        prompt = f"""Analyse these {self.category} news outputs and extract rules.
BEST (scores 8-10): {json.dumps([{"headline":r["headline"],"score":r["quality_score"]} for r in best])}
WORST (scores 1-6): {json.dumps([{"headline":r["headline"],"score":r["quality_score"]} for r in worst])}
Return ONLY JSON:
{{"new_rules":["rule1","rule2"],"new_anti_rules":["avoid1"],"style_discoveries":["insight1"]}}"""
        try:
            raw  = ai_generate(prompt, max_tokens=500)
            data = json.loads(_extract_json(raw))
            self.wisdom["rules"].extend(data.get("new_rules", []))
            self.wisdom["anti_rules"].extend(data.get("new_anti_rules", []))
            self.wisdom["style_notes"].extend(data.get("style_discoveries", []))
            self.wisdom["generation"] += 1
            self.wisdom["last_extracted"] = datetime.datetime.utcnow().isoformat()
            self._save()
        except Exception as e:
            print(f"    [TRAIN] Pattern extraction error: {e}")
        return self.wisdom

    def build_wisdom_block(self) -> str:
        rules = self.wisdom.get("rules", [])
        anti  = self.wisdom.get("anti_rules", [])
        if not rules and not anti:
            return ""
        block = f"\n=== LEARNED WISDOM (Gen {self.wisdom['generation']}) ===\n"
        if rules:
            block += "ALWAYS DO:\n" + "\n".join(f"  ✓ {r}" for r in rules[-6:]) + "\n"
        if anti:
            block += "NEVER DO:\n" + "\n".join(f"  ✗ {r}" for r in anti[-4:]) + "\n"
        block += "=== END WISDOM ===\n"
        return block


class CrossAgentLearning:
    def __init__(self):
        self.pool = self._load()

    def _load(self):
        if WISDOM_POOL.exists():
            try: return json.loads(WISDOM_POOL.read_text())
            except: pass
        return {"top_outputs": [], "structural_insights": [], "last_updated": None}

    def _save(self):
        self.pool["last_updated"] = datetime.datetime.utcnow().isoformat()
        self.pool["top_outputs"]  = sorted(
            self.pool["top_outputs"], key=lambda x: x.get("score", 0), reverse=True)[:20]
        WISDOM_POOL.write_text(json.dumps(self.pool, indent=2))

    def deposit(self, agent_id: str, record: dict):
        if record.get("quality_score", 0) < 8.5:
            return
        entry = {"from_agent": agent_id, "score": record.get("quality_score", 0),
                 "category": record.get("category", ""),
                 "headline": record.get("headline", ""),
                 "strengths": record.get("strengths", []),
                 "timestamp": datetime.datetime.utcnow().isoformat()}
        self.pool["top_outputs"].append(entry)
        self._save()

    def get_cross_insights(self, requesting_agent: str) -> str:
        others = [o for o in self.pool["top_outputs"]
                  if o.get("from_agent") != requesting_agent][:3]
        if not others:
            return ""
        block = "\n=== CROSS-AGENT LEARNING ===\n"
        for o in others:
            block += f"[{o['from_agent']} — {o['score']}/10] {o['headline']}\n"
        block += "=== END CROSS-AGENT ===\n"
        return block


class AdversarialReviewer:
    THRESHOLD = 7.0

    def __init__(self, agent_id: str, category: str):
        self.agent_id = agent_id
        self.category = category

    def challenge(self, content: dict, ai_fn=None) -> tuple:
        score = content.get("quality_score", 5.0)
        if score >= self.THRESHOLD:
            return content, score
        print(f"    [ADVERSARIAL] Score {score:.1f} below {self.THRESHOLD} — challenging...")
        prompt = (
            f"You are a harsh senior editor. Critique this {self.category} news content.\n"
            f"HEADLINE: {content.get('headline','')}\n"
            f"SUMMARY: {content.get('summary','')[:200]}\n"
            f"Give SPECIFIC fixes. Return ONLY JSON:\n"
            f'{{"headline_fix":"...","summary_fix":"...","fatal_flaws":["flaw1"]}}'
        )
        try:
            raw     = ai_generate(prompt, max_tokens=400)
            critique= json.loads(_extract_json(raw))
            if critique.get("headline_fix"):
                content["headline"] = critique["headline_fix"]
            if critique.get("summary_fix"):
                content["summary"]  = critique["summary_fix"]
            new_score = min(score + 1.5, 9.5)
            content["quality_score"]       = new_score
            content["adversarial_rewrite"] = True
            print(f"    [ADVERSARIAL] {score:.1f} → {new_score:.1f}")
            return content, new_score
        except Exception as e:
            print(f"    [ADVERSARIAL] Failed: {e}")
            return content, score


class AgentTrainer:
    def __init__(self, agent_id: str, category: str):
        self.agent_id  = agent_id
        self.category  = category
        self.store     = TrainingDataStore(agent_id)
        self.extractor = PatternExtractor(agent_id, category)
        self.cross     = CrossAgentLearning()
        self.adversary = AdversarialReviewer(agent_id, category)
        self.run_count = self._load_run_count()

    def _load_run_count(self):
        f = TRAINING_DIR / f"{self.agent_id}_runs.txt"
        if f.exists():
            try: return int(f.read_text().strip())
            except: pass
        return 0

    def _save_run_count(self):
        f = TRAINING_DIR / f"{self.agent_id}_runs.txt"
        try: f.write_text(str(self.run_count))
        except: pass

    def build_training_context(self) -> str:
        blocks = []
        few_shot = self.store.build_few_shot_block()
        if few_shot: blocks.append(few_shot)
        wisdom = self.extractor.build_wisdom_block()
        if wisdom: blocks.append(wisdom)
        cross = self.cross.get_cross_insights(self.agent_id)
        if cross: blocks.append(cross)
        stats = self.store.stats()
        header = (f"\n[TRAINING: {self.agent_id} | Run#{self.run_count} | "
                  f"Samples:{stats['total']} | AvgQ:{stats['avg']}/10]\n")
        return header + "\n".join(blocks)

    def post_process(self, topic: str, content: dict,
                     prompt_used: str, ai_fn=None) -> dict:
        self.run_count += 1
        self._save_run_count()
        score = content.get("quality_score", 5.0)

        # Adversarial challenge
        if ai_fn:
            try:
                content, score = self.adversary.challenge(content, ai_fn)
                content["quality_score"] = score
            except Exception as e:
                print(f"    [TRAIN] Adversarial failed (non-fatal): {e}")

        # Record
        record = build_training_record(self.agent_id, topic, content, score, prompt_used)
        self.store.add(record)

        # Cross-agent deposit
        try: self.cross.deposit(self.agent_id, record)
        except: pass

        # Pattern extraction every 3 runs
        if self.run_count % 3 == 0:
            try: self.extractor.extract_patterns(self.store)
            except Exception as e: print(f"    [TRAIN] Pattern extraction failed: {e}")

        # Log to Sheets
        try:
            log_to_sheets(self.agent_id,
                f"Run {self.run_count} | score={score:.1f} | samples={len(self.store.records)}", "info")
        except: pass

        return content

    def get_training_report(self) -> dict:
        stats  = self.store.stats()
        wisdom = self.extractor.wisdom
        return {
            "agent_id": self.agent_id, "category": self.category,
            "total_runs": self.run_count, "total_samples": stats["total"],
            "avg_quality": stats["avg"], "best_score": stats["best"],
            "elite_count": stats["elite_count"],
            "wisdom_generation": wisdom.get("generation", 0),
            "rules_learned": len(wisdom.get("rules", [])),
            "anti_rules": len(wisdom.get("anti_rules", [])),
        }
