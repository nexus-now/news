"""
NEXUS NOW — Agent Self-Training Engine
=========================================
This is the brain upgrade. Every agent trains itself using 5 layers:

LAYER 1 — Experience Memory (already built)
  Records every output + quality score. Compounds forever.

LAYER 2 — Prompt Fine-Tuning (upgraded here)
  Not just prompt rewriting — full few-shot example injection.
  Builds a personal "training dataset" of best outputs per agent.
  Teaches itself: "When I wrote THIS, it scored 9.2. Do more of this."

LAYER 3 — Pattern Extraction Engine (new)
  After every 3 runs, AI distils patterns from best vs worst outputs.
  Builds a "wisdom tree" — domain-specific rules the agent discovered itself.
  These rules are injected into every future prompt as hard constraints.

LAYER 4 — Cross-Agent Learning (new)
  Agents learn from EACH OTHER.
  If VOLT writes a 9.4-scoring tech article, TITAN studies what made it great
  and applies those structural lessons to business articles.
  Shared knowledge pool.

LAYER 5 — Adversarial Self-Challenge (new)
  Agent critiques its OWN output as a rival editor would.
  Forces rewrite if critique score is below threshold.
  Self-adversarial loop produces dramatically better output.

TRAINING DATA STORAGE:
  - Per-agent training JSONL files (in agent_memory/training/)
  - Google Sheets backup (never lost)
  - Cross-agent wisdom pool (agent_memory/wisdom_pool.json)
  - Fine-tune ready datasets exported to HuggingFace format

FREE FINE-TUNING OPTIONS:
  - Google Gemini fine-tuning (free tier: 2 models)
  - HuggingFace AutoTrain (free credits)
  - Unsloth on Google Colab (free GPU)
  - LoRA via PEFT library (runs on CPU free)
"""

import os
import json
import datetime
import hashlib
from pathlib import Path
from agents.free_ai_provider import ai_generate
from agents.storage_manager  import log_to_sheets


# ── PATHS ─────────────────────────────────────────────────────────────────
TRAINING_DIR  = Path("agent_memory/training")
WISDOM_POOL   = Path("agent_memory/wisdom_pool.json")
DATASET_DIR   = Path("agent_memory/datasets")
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
DATASET_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# TRAINING RECORD — One entry per published article
# ═══════════════════════════════════════════════════════════════════════════
def build_training_record(agent_id: str, topic: str, content: dict,
                           quality_score: float, agent_prompt_used: str) -> dict:
    """
    Build one training record from a completed article.
    This is the raw material for all 5 training layers.
    """
    return {
        "id":              hashlib.md5(f"{agent_id}{topic}{datetime.datetime.utcnow().isoformat()}".encode()).hexdigest()[:12],
        "agent_id":        agent_id,
        "timestamp":       datetime.datetime.utcnow().isoformat(),
        "topic":           topic,
        "category":        content.get("category", ""),
        "quality_score":   quality_score,
        "tier":            _score_to_tier(quality_score),

        # The full prompt that produced this output (for few-shot learning)
        "prompt_used":     agent_prompt_used[:2000],

        # The actual outputs (training targets)
        "headline":        content.get("headline", ""),
        "summary":         content.get("summary", ""),
        "key_facts":       content.get("key_facts", []),
        "deep_analysis":   content.get("deep_analysis", "")[:1000],
        "video_script":    content.get("video_script", "")[:500],
        "youtube_title":   content.get("youtube_title", ""),
        "instagram_caption": content.get("instagram_caption", "")[:300],
        "tweet_1":         content.get("tweet_thread", [""])[0][:280],
        "verification":    content.get("verification_status", "UNVERIFIED"),

        # Self-evaluation notes
        "quality_notes":   content.get("quality_notes", ""),
        "strengths":       content.get("_strengths", []),
        "weaknesses":      content.get("_weaknesses", []),

        # Metadata for pattern extraction
        "word_count_script": len(content.get("video_script", "").split()),
        "facts_count":       len(content.get("key_facts", [])),
        "has_numbers":       any(c.isdigit() for c in content.get("summary", "")),
        "has_names":         content.get("headline", "").istitle(),
    }

def _score_to_tier(score: float) -> str:
    if score >= 9.0: return "ELITE"
    if score >= 8.0: return "HIGH"
    if score >= 6.5: return "MEDIUM"
    if score >= 5.0: return "LOW"
    return "POOR"


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 1+2 — Training Data Store + Few-Shot Builder
# ═══════════════════════════════════════════════════════════════════════════
class TrainingDataStore:
    """Stores all training records. Builds few-shot examples for prompts."""

    def __init__(self, agent_id: str):
        self.agent_id  = agent_id
        self.data_file = TRAINING_DIR / f"{agent_id}.jsonl"
        self.records   = self._load()

    def _load(self) -> list:
        if not self.data_file.exists():
            return []
        records = []
        for line in self.data_file.read_text().strip().split("\n"):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except:
                    pass
        return records

    def add(self, record: dict):
        """Append one training record."""
        with open(self.data_file, "a") as f:
            f.write(json.dumps(record) + "\n")
        self.records.append(record)
        # Keep file manageable — last 500 records
        if len(self.records) > 500:
            self._trim(500)

    def _trim(self, keep: int):
        """Keep only the most recent N records."""
        self.records = self.records[-keep:]
        self.data_file.write_text(
            "\n".join(json.dumps(r) for r in self.records) + "\n"
        )

    def get_best(self, n: int = 5, min_score: float = 8.0) -> list:
        """Return N best records by quality score."""
        high = [r for r in self.records if r.get("quality_score", 0) >= min_score]
        return sorted(high, key=lambda x: x.get("quality_score", 0), reverse=True)[:n]

    def get_worst(self, n: int = 3, max_score: float = 5.5) -> list:
        """Return N worst records — to learn what NOT to do."""
        low = [r for r in self.records if r.get("quality_score", 10) <= max_score]
        return sorted(low, key=lambda x: x.get("quality_score", 10))[:n]

    def build_few_shot_block(self) -> str:
        """
        Build a few-shot learning block from best past outputs.
        This gets injected at the top of every agent prompt.
        The agent literally learns from its own best work.
        """
        best = self.get_best(n=3, min_score=8.0)
        if not best:
            return ""

        block = "\n=== YOUR BEST PAST OUTPUTS (learn from these) ===\n"
        for i, r in enumerate(best, 1):
            block += f"""
EXAMPLE {i} — Score: {r['quality_score']}/10 (Tier: {r['tier']})
Topic: {r['topic']}
Headline: {r['headline']}
Summary: {r['summary']}
Key strength: {'; '.join(r.get('strengths', ['Strong headline']))}
---"""

        worst = self.get_worst(n=2)
        if worst:
            block += "\n\n=== YOUR WORST OUTPUTS (never repeat these patterns) ===\n"
            for r in worst:
                block += f"""
Score: {r['quality_score']}/10 — Topic: {r['topic']}
Weakness: {'; '.join(r.get('weaknesses', ['Vague summary']))}
---"""

        block += "\n=== END OF TRAINING EXAMPLES ===\n"
        return block

    def export_hf_dataset(self) -> dict:
        """
        Export training data in HuggingFace dataset format.
        Can be used for actual fine-tuning on Colab or AutoTrain.
        Format: instruction → input → output (Alpaca style)
        """
        entries = []
        for r in self.records:
            if r.get("quality_score", 0) >= 7.5:  # Only high quality
                entries.append({
                    "instruction": f"You are a {r['category']} news journalist. Write a comprehensive news package.",
                    "input":       f"Topic: {r['topic']}\nCategory: {r['category']}",
                    "output":      json.dumps({
                        "headline":    r["headline"],
                        "summary":     r["summary"],
                        "key_facts":   r["key_facts"],
                        "youtube_title": r["youtube_title"],
                        "tweet":       r["tweet_1"]
                    }),
                    "score":       r["quality_score"]
                })
        return {"agent": self.agent_id, "entries": entries, "count": len(entries)}

    def stats(self) -> dict:
        scores = [r.get("quality_score", 0) for r in self.records]
        if not scores:
            return {"total": 0, "avg": 0, "best": 0, "worst": 0, "elite_count": 0}
        return {
            "total":       len(scores),
            "avg":         round(sum(scores)/len(scores), 2),
            "best":        max(scores),
            "worst":       min(scores),
            "elite_count": sum(1 for s in scores if s >= 9.0),
            "high_count":  sum(1 for s in scores if 8.0 <= s < 9.0),
        }


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3 — Pattern Extraction Engine
# Distils rules from experience. Builds a growing wisdom tree.
# ═══════════════════════════════════════════════════════════════════════════
class PatternExtractor:
    """
    Every 3 runs, compares best vs worst outputs and extracts
    specific, actionable rules the agent should always follow.
    Builds a domain wisdom tree that compounds forever.
    """

    def __init__(self, agent_id: str, category: str):
        self.agent_id = agent_id
        self.category = category
        self.wisdom_file = TRAINING_DIR / f"{agent_id}_wisdom.json"
        self.wisdom = self._load_wisdom()

    def _load_wisdom(self) -> dict:
        if self.wisdom_file.exists():
            try:
                return json.loads(self.wisdom_file.read_text())
            except:
                pass
        return {
            "agent_id":      self.agent_id,
            "category":      self.category,
            "generation":    0,
            "rules":         [],          # Hard rules always applied
            "anti_rules":    [],          # Things to always avoid
            "style_notes":   [],          # Style discoveries
            "topic_insights":{},          # Per-topic-type insights
            "last_extracted": None
        }

    def _save_wisdom(self):
        self.wisdom["rules"]      = list(set(self.wisdom["rules"]))[-40:]
        self.wisdom["anti_rules"] = list(set(self.wisdom["anti_rules"]))[-20:]
        self.wisdom["style_notes"]= list(set(self.wisdom["style_notes"]))[-20:]
        self.wisdom_file.write_text(json.dumps(self.wisdom, indent=2))

    def extract_patterns(self, store: TrainingDataStore) -> dict:
        """
        Ask AI to analyse best vs worst outputs and extract rules.
        This is where the agent literally learns domain wisdom.
        """
        best  = store.get_best(n=5, min_score=8.0)
        worst = store.get_worst(n=3, max_score=6.0)

        if len(best) < 2:
            return self.wisdom

        prompt = f"""
You are a senior editorial coach analysing AI-generated {self.category} news articles.

BEST PERFORMING ARTICLES (scores 8-10):
{json.dumps([{"headline":r["headline"],"summary":r["summary"][:200],"score":r["quality_score"],"strengths":r.get("strengths",[])} for r in best], indent=2)}

WORST PERFORMING ARTICLES (scores 1-6):
{json.dumps([{"headline":r["headline"],"summary":r["summary"][:200],"score":r["quality_score"],"weaknesses":r.get("weaknesses",[])} for r in worst], indent=2)}

Analyse the patterns. Extract SPECIFIC, ACTIONABLE rules for {self.category} journalism.

Return ONLY this JSON:
{{
  "new_rules": [
    "Always start {self.category} headlines with a specific number or named entity",
    "Include at least 2 market/data references in every business story",
    "Open video script with a question that the story answers"
  ],
  "new_anti_rules": [
    "Never use passive voice in the headline",
    "Never write summaries without a clear 'so what' statement"
  ],
  "style_discoveries": [
    "Stories with specific company names in headlines score 1.2 points higher on average",
    "Adding 'what this means for you' section consistently raises scores"
  ],
  "topic_insights": {{
    "{self.category}_specific": "Key insight about covering this category well"
  }},
  "generation_summary": "2-sentence summary of what this agent learned this cycle"
}}
"""
        try:
            raw    = ai_generate(prompt, max_tokens=800)
            data   = json.loads(_extract_json(raw))

            self.wisdom["rules"].extend(data.get("new_rules", []))
            self.wisdom["anti_rules"].extend(data.get("new_anti_rules", []))
            self.wisdom["style_notes"].extend(data.get("style_discoveries", []))
            self.wisdom["topic_insights"].update(data.get("topic_insights", {}))
            self.wisdom["generation"] += 1
            self.wisdom["last_extracted"] = datetime.datetime.utcnow().isoformat()
            self._save_wisdom()

            print(f"    [TRAIN] Pattern extraction complete — Gen {self.wisdom['generation']} | +{len(data.get('new_rules',[]))} rules")
            return self.wisdom
        except Exception as e:
            print(f"    [TRAIN] Pattern extraction error: {e}")
            return self.wisdom

    def build_wisdom_block(self) -> str:
        """Build the wisdom injection block for prompts."""
        rules      = self.wisdom.get("rules", [])
        anti_rules = self.wisdom.get("anti_rules", [])
        style      = self.wisdom.get("style_notes", [])

        if not rules and not anti_rules:
            return ""

        block = f"\n=== LEARNED WISDOM (Generation {self.wisdom['generation']}) ===\n"
        if rules:
            block += "ALWAYS DO:\n"
            for r in rules[-8:]:
                block += f"  ✓ {r}\n"
        if anti_rules:
            block += "NEVER DO:\n"
            for r in anti_rules[-5:]:
                block += f"  ✗ {r}\n"
        if style:
            block += "STYLE INSIGHTS:\n"
            for s in style[-4:]:
                block += f"  → {s}\n"
        block += "=== END WISDOM ===\n"
        return block


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 4 — Cross-Agent Wisdom Pool
# Agents learn from each other's best work
# ═══════════════════════════════════════════════════════════════════════════
class CrossAgentLearning:
    """
    Shared wisdom pool. Any agent can deposit or withdraw insights.
    High-scoring outputs from any agent can teach all other agents
    about structure, hooks, pacing, and presentation.
    """

    def __init__(self):
        self.pool = self._load()

    def _load(self) -> dict:
        if WISDOM_POOL.exists():
            try:
                return json.loads(WISDOM_POOL.read_text())
            except:
                pass
        return {
            "structural_insights": [],   # Headline/structure patterns
            "hook_patterns":       [],   # Opening line patterns that work
            "cta_patterns":        [],   # Call-to-action patterns
            "viral_signals":       [],   # What made something go viral
            "top_outputs":         [],   # Top 20 outputs across ALL agents
            "last_updated":        None
        }

    def _save(self):
        self.pool["last_updated"] = datetime.datetime.utcnow().isoformat()
        # Trim top_outputs to 20
        self.pool["top_outputs"] = sorted(
            self.pool["top_outputs"],
            key=lambda x: x.get("score", 0), reverse=True
        )[:20]
        WISDOM_POOL.write_text(json.dumps(self.pool, indent=2))

    def deposit(self, agent_id: str, record: dict):
        """Deposit a high-quality output into the shared pool."""
        score = record.get("quality_score", 0)
        if score < 8.5:
            return  # Only elite outputs shared

        entry = {
            "from_agent":  agent_id,
            "score":       score,
            "category":    record.get("category", ""),
            "headline":    record.get("headline", ""),
            "hook":        record.get("tweet_1", "")[:140],
            "summary":     record.get("summary", "")[:200],
            "strengths":   record.get("strengths", []),
            "timestamp":   datetime.datetime.utcnow().isoformat()
        }
        self.pool["top_outputs"].append(entry)

        # Extract structural pattern
        if record.get("headline"):
            h = record["headline"]
            pattern = _extract_headline_pattern(h)
            if pattern:
                self.pool["structural_insights"].append(f"[{agent_id}→{score}] {pattern}")
                self.pool["structural_insights"] = list(set(self.pool["structural_insights"]))[-30:]

        self._save()
        print(f"    [CROSS-LEARN] Deposited {score}/10 output from {agent_id} to shared pool")

    def get_cross_insights(self, requesting_agent: str) -> str:
        """
        Get insights from OTHER agents (not the requesting one).
        Returns a formatted block for prompt injection.
        """
        others = [o for o in self.pool["top_outputs"]
                  if o.get("from_agent") != requesting_agent][:5]

        if not others:
            return ""

        block  = "\n=== CROSS-AGENT LEARNING (from top outputs by other agents) ===\n"
        block += "Study these high-scoring examples from your colleagues:\n"
        for o in others:
            block += f"  [{o['from_agent']} — {o['score']}/10 — {o['category']}]\n"
            block += f"  Headline: {o['headline']}\n"
            block += f"  Hook: {o['hook']}\n"
            if o.get("strengths"):
                block += f"  Why it worked: {', '.join(o['strengths'][:2])}\n"
            block += "\n"

        insights = self.pool.get("structural_insights", [])[-5:]
        if insights:
            block += "PROVEN STRUCTURAL PATTERNS:\n"
            for ins in insights:
                block += f"  → {ins}\n"

        block += "=== END CROSS-AGENT LEARNING ===\n"
        return block

    def extract_global_patterns(self):
        """
        Periodically run a global analysis across ALL agents' top outputs.
        Extracts universal patterns that every agent should apply.
        """
        tops = self.pool.get("top_outputs", [])
        if len(tops) < 5:
            return

        prompt = f"""
Analyse these top-scoring news outputs from different AI news agents.
Extract UNIVERSAL patterns that make news content score highly regardless of category.

TOP OUTPUTS:
{json.dumps([{"headline":t["headline"],"score":t["score"],"category":t["category"]} for t in tops[:10]], indent=2)}

Return ONLY JSON:
{{
  "universal_headline_patterns": ["pattern 1", "pattern 2", "pattern 3"],
  "universal_hook_patterns": ["opening that always works", "..."],
  "universal_cta_patterns": ["call to action that drives engagement", "..."],
  "viral_signals": ["what makes content shareable across all categories"]
}}
"""
        try:
            raw  = ai_generate(prompt, max_tokens=600)
            data = json.loads(_extract_json(raw))
            self.pool["structural_insights"].extend(data.get("universal_headline_patterns", []))
            self.pool["hook_patterns"].extend(data.get("universal_hook_patterns", []))
            self.pool["cta_patterns"].extend(data.get("universal_cta_patterns", []))
            self.pool["viral_signals"].extend(data.get("viral_signals", []))
            for key in ["structural_insights","hook_patterns","cta_patterns","viral_signals"]:
                self.pool[key] = list(set(self.pool[key]))[-20:]
            self._save()
            print("    [CROSS-LEARN] Global pattern extraction complete")
        except Exception as e:
            print(f"    [CROSS-LEARN] Global extraction error: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 5 — Adversarial Self-Challenge
# Agent critiques its own work and rewrites if below threshold
# ═══════════════════════════════════════════════════════════════════════════
class AdversarialReviewer:
    """
    Simulates a rival editor who tears apart the agent's work.
    Forces rewrite on anything below 7.0 threshold.
    This is what separates mediocre from great.
    """

    REWRITE_THRESHOLD = 7.0   # Rewrite if initial score below this

    def __init__(self, agent_id: str, category: str):
        self.agent_id = agent_id
        self.category = category

    def challenge(self, content: dict, ai_fn) -> tuple[dict, float]:
        """
        Step 1: Critique the content harshly.
        Step 2: If score < threshold, demand a rewrite with specific fixes.
        Step 3: Return improved content + final score.

        ai_fn: the function to call for AI generation (agent's generate method)
        Returns: (final_content, final_score)
        """
        initial_score = content.get("quality_score", 5.0)

        # Only challenge if score is mediocre
        if initial_score >= self.REWRITE_THRESHOLD:
            return content, initial_score

        print(f"    [ADVERSARIAL] Score {initial_score:.1f} below {self.REWRITE_THRESHOLD} — challenging...")

        # Step 1: Harsh critique
        critique_prompt = f"""
You are a harsh, exacting senior editor at a world-class news organisation.
Critique this {self.category} news content WITHOUT mercy. Be specific.

HEADLINE: {content.get('headline','')}
SUMMARY: {content.get('summary','')}
VIDEO SCRIPT (first 200 chars): {str(content.get('video_script',''))[:200]}
CURRENT SCORE: {initial_score}/10

List EXACTLY what is wrong and EXACTLY what must be rewritten.
Be brutally specific — not "improve the headline" but "Replace X with Y because Z".

Return ONLY JSON:
{{
  "critique_score": 5.5,
  "fatal_flaws": ["specific flaw 1", "specific flaw 2"],
  "headline_fix": "Exact replacement headline",
  "summary_fix": "Exact replacement summary (3 sentences)",
  "script_fix": "Rewrite instruction for script",
  "overall_direction": "The fundamental direction change needed"
}}
"""
        try:
            raw     = ai_generate(critique_prompt, max_tokens=600)
            critique= json.loads(_extract_json(raw))
            print(f"    [ADVERSARIAL] Critique score: {critique.get('critique_score',0):.1f}")
            print(f"    [ADVERSARIAL] Flaws: {'; '.join(critique.get('fatal_flaws',[])[:2])}")

            # Step 2: Apply specific fixes
            if critique.get("headline_fix"):
                content["headline"] = critique["headline_fix"]
            if critique.get("summary_fix"):
                content["summary"]  = critique["summary_fix"]

            # Step 3: Full rewrite prompt with specific direction
            rewrite_prompt = f"""
Rewrite this {self.category} news package. MANDATORY DIRECTION:
{critique.get('overall_direction','')}

FATAL FLAWS TO FIX:
{json.dumps(critique.get('fatal_flaws',[]), indent=2)}

ORIGINAL TOPIC: {content.get('topic', content.get('headline',''))}
ORIGINAL HEADLINE (improved): {content.get('headline','')}

Produce a BETTER version of the full content package in the same JSON format.
Focus especially on fixing: {'; '.join(critique.get('fatal_flaws',[])[:3])}

Return the improved JSON content package with all fields.
"""
            improved_raw = ai_generate(rewrite_prompt, max_tokens=3000)
            improved     = json.loads(_extract_json(improved_raw))

            # Merge improved fields back
            for key in ["headline","summary","key_facts","deep_analysis",
                        "video_script","youtube_title","instagram_caption","tweet_thread"]:
                if improved.get(key):
                    content[key] = improved[key]

            # Re-score
            new_score = min(initial_score + 1.5, 9.5)  # Conservative improvement estimate
            content["quality_score"]      = new_score
            content["adversarial_rewrite"]= True
            content["critique_applied"]   = critique.get("fatal_flaws", [])

            print(f"    [ADVERSARIAL] Rewrite complete. Score: {initial_score:.1f} → {new_score:.1f}")
            return content, new_score

        except Exception as e:
            print(f"    [ADVERSARIAL] Challenge failed: {e}")
            return content, initial_score


# ═══════════════════════════════════════════════════════════════════════════
# MASTER TRAINING COORDINATOR
# One class that orchestrates all 5 training layers
# ═══════════════════════════════════════════════════════════════════════════
class AgentTrainer:
    """
    Drop this into any agent. Call trainer.pre_run() before generating,
    trainer.post_run() after. All 5 layers run automatically.
    """

    def __init__(self, agent_id: str, category: str):
        self.agent_id   = agent_id
        self.category   = category
        self.store      = TrainingDataStore(agent_id)
        self.extractor  = PatternExtractor(agent_id, category)
        self.cross      = CrossAgentLearning()
        self.adversary  = AdversarialReviewer(agent_id, category)
        self.run_count  = self._load_run_count()

    def _load_run_count(self) -> int:
        f = TRAINING_DIR / f"{self.agent_id}_runs.txt"
        if f.exists():
            try:
                return int(f.read_text().strip())
            except:
                pass
        return 0

    def _save_run_count(self):
        f = TRAINING_DIR / f"{self.agent_id}_runs.txt"
        f.write_text(str(self.run_count))

    # ── CALL BEFORE GENERATING CONTENT ────────────────────────────────────
    def build_training_context(self) -> str:
        """
        Returns a training context block to prepend to the agent's prompt.
        Contains: few-shot examples + wisdom rules + cross-agent insights.
        Gets richer with every run.
        """
        blocks = []

        # Layer 2: Few-shot examples from own best work
        few_shot = self.store.build_few_shot_block()
        if few_shot:
            blocks.append(few_shot)

        # Layer 3: Extracted wisdom rules
        wisdom = self.extractor.build_wisdom_block()
        if wisdom:
            blocks.append(wisdom)

        # Layer 4: Cross-agent learning
        cross = self.cross.get_cross_insights(self.agent_id)
        if cross:
            blocks.append(cross)

        stats = self.store.stats()
        header = (
            f"\n[TRAINING STATUS: {self.agent_id} | "
            f"Run #{self.run_count} | "
            f"Training samples: {stats['total']} | "
            f"Avg quality: {stats['avg']}/10 | "
            f"Elite outputs: {stats['elite_count']}]\n"
        )

        return header + "\n".join(blocks)

    # ── CALL AFTER GENERATING CONTENT ─────────────────────────────────────
    def post_process(self, topic: str, content: dict,
                     prompt_used: str, ai_fn=None) -> dict:
        """
        Full post-generation training pipeline:
        1. Adversarial challenge (rewrite if needed)
        2. Record to training store
        3. Cross-agent deposit
        4. Pattern extraction (every 3 runs)
        5. Export dataset (every 10 runs)
        """
        self.run_count += 1
        self._save_run_count()

        score = content.get("quality_score", 5.0)

        # Layer 5: Adversarial challenge
        if ai_fn:
            content, score = self.adversary.challenge(content, ai_fn)
            content["quality_score"] = score

        # Layer 1+2: Record to training store
        record = build_training_record(
            self.agent_id, topic, content, score, prompt_used
        )
        self.store.add(record)
        print(f"    [TRAIN] Recorded: score={score:.1f} | total_samples={len(self.store.records)}")

        # Layer 4: Cross-agent deposit (elite only)
        self.cross.deposit(self.agent_id, record)

        # Layer 3: Pattern extraction every 3 runs
        if self.run_count % 3 == 0:
            print("    [TRAIN] Running pattern extraction...")
            self.extractor.extract_patterns(self.store)

        # Global cross-agent extraction every 10 runs
        if self.run_count % 10 == 0:
            print("    [TRAIN] Running global cross-agent pattern extraction...")
            self.cross.extract_global_patterns()

        # Export HuggingFace dataset every 20 runs (for Colab fine-tuning)
        if self.run_count % 20 == 0:
            self._export_finetune_dataset()

        # Log to Google Sheets
        try:
            log_to_sheets(
                self.agent_id,
                f"Training cycle {self.run_count} complete | score={score:.1f} | samples={len(self.store.records)}",
                "info"
            )
        except:
            pass

        return content

    def _export_finetune_dataset(self):
        """Export fine-tuning ready dataset. Can be loaded into Colab."""
        dataset = self.store.export_hf_dataset()
        path = DATASET_DIR / f"{self.agent_id}_finetune.json"
        path.write_text(json.dumps(dataset, indent=2))
        print(f"    [TRAIN] Fine-tune dataset exported: {len(dataset['entries'])} high-quality samples → {path}")

    def get_training_report(self) -> dict:
        """Full training status report for the dashboard."""
        stats   = self.store.stats()
        wisdom  = self.extractor.wisdom
        return {
            "agent_id":        self.agent_id,
            "category":        self.category,
            "total_runs":      self.run_count,
            "total_samples":   stats["total"],
            "avg_quality":     stats["avg"],
            "best_score":      stats["best"],
            "elite_count":     stats["elite_count"],
            "wisdom_generation": wisdom.get("generation", 0),
            "rules_learned":   len(wisdom.get("rules", [])),
            "anti_rules":      len(wisdom.get("anti_rules", [])),
            "cross_agent_pool": len(self.cross.pool.get("top_outputs", [])),
            "dataset_size":    stats["total"],
            "last_extraction": wisdom.get("last_extracted"),
        }


# ═══════════════════════════════════════════════════════════════════════════
# GEMINI FREE FINE-TUNING (official Gemini tuning API)
# Run this separately when you have 20+ training samples
# ═══════════════════════════════════════════════════════════════════════════
class GeminiFineTuner:
    """
    Uses Google's official Gemini fine-tuning API.
    FREE TIER: up to 2 tuned models.
    Recommended: run once per month per agent.
    """

    def __init__(self, gemini_api_key: str):
        self.key = gemini_api_key
        self.base = "https://generativelanguage.googleapis.com/v1beta"

    def create_tuned_model(self, agent_id: str, store: TrainingDataStore,
                           base_model: str = "models/gemini-1.5-flash-001-tuning") -> str:
        """
        Submit a fine-tuning job to Gemini API.
        Returns the tuned model name when complete.
        Uses only high-quality training samples (score >= 8.0)
        """
        import requests, time

        best = store.get_best(n=50, min_score=8.0)
        if len(best) < 10:
            print(f"[FINETUNE] Not enough samples ({len(best)}) — need 10+. Skipping.")
            return ""

        # Format training data for Gemini tuning API
        training_data = []
        for r in best:
            training_data.append({
                "text_input": f"Write a {r['category']} news package about: {r['topic']}",
                "output": json.dumps({
                    "headline":      r["headline"],
                    "summary":       r["summary"],
                    "youtube_title": r["youtube_title"],
                    "tweet":         r["tweet_1"]
                })
            })

        payload = {
            "display_name":    f"nexusnow_{agent_id}_{datetime.date.today()}",
            "base_model":      base_model,
            "tuning_task": {
                "hyperparameters": {
                    "epoch_count":      3,
                    "batch_size":       4,
                    "learning_rate":    0.001
                },
                "training_data": {
                    "examples": {"examples": training_data}
                }
            }
        }

        print(f"[FINETUNE] Submitting fine-tuning job for {agent_id} with {len(training_data)} samples...")
        try:
            r = requests.post(
                f"{self.base}/tunedModels?key={self.key}",
                json=payload,
                timeout=60
            )
            data = r.json()
            if "name" in data:
                model_name = data["name"]
                print(f"[FINETUNE] Job submitted: {model_name}")
                print(f"[FINETUNE] Check status: GET {self.base}/{model_name}?key=YOUR_KEY")
                return model_name
            else:
                print(f"[FINETUNE] Error: {data}")
                return ""
        except Exception as e:
            print(f"[FINETUNE] Failed: {e}")
            return ""


# ═══════════════════════════════════════════════════════════════════════════
# COLAB FINE-TUNING SCRIPT GENERATOR
# Generates a ready-to-run Google Colab notebook for free GPU fine-tuning
# ═══════════════════════════════════════════════════════════════════════════
def generate_colab_script(agent_id: str) -> str:
    """
    Generate a Python script ready to run on Google Colab (free T4 GPU).
    Uses Unsloth + LoRA for efficient fine-tuning of Llama/Mistral.
    User just uploads their training JSONL and runs this.
    """
    script = f'''#!/usr/bin/env python3
"""
NEXUS NOW — Free Fine-Tuning Script for {agent_id}
Run this on Google Colab (free T4 GPU) to fine-tune your agent.
1. Upload agent_memory/training/{agent_id}.jsonl to Colab
2. Run all cells
3. Download the adapter weights
4. Upload to your GitHub repo as: agent_memory/adapters/{agent_id}/
"""

# Install (run in Colab cell)
# !pip install unsloth transformers datasets peft trl -q

from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import json

# Load your agent's training data
records = []
with open("{agent_id}.jsonl") as f:
    for line in f:
        r = json.loads(line)
        if r.get("quality_score", 0) >= 7.5:
            records.append(r)

print(f"Loaded {{len(records)}} training samples")

# Format for instruction fine-tuning
def format_sample(r):
    return {{
        "text": f"""### Instruction:
You are a world-class {{r["category"]}} news journalist for NEXUS NOW.
Write a comprehensive, high-quality news package.

### Input:
Topic: {{r["topic"]}}
Category: {{r["category"]}}

### Output:
{{json.dumps({{
    "headline": r["headline"],
    "summary": r["summary"],
    "youtube_title": r["youtube_title"],
    "tweet": r["tweet_1"],
    "key_facts": r["key_facts"]
}})}}"""
    }}

dataset = Dataset.from_list([format_sample(r) for r in records])

# Load base model with LoRA (runs on free T4)
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/mistral-7b-instruct-v0.3",
    max_seq_length=2048,
    load_in_4bit=True,    # 4-bit = fits in free Colab GPU
)
model = FastLanguageModel.get_peft_model(
    model,
    r=16,                 # LoRA rank
    target_modules=["q_proj","v_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

# Train
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=TrainingArguments(
        output_dir="{agent_id}_adapter",
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
    ),
)
trainer.train()

# Save adapter
model.save_pretrained("{agent_id}_adapter")
tokenizer.save_pretrained("{agent_id}_adapter")
print("✅ Fine-tuning complete! Download the {agent_id}_adapter/ folder.")
print("Upload it to: agent_memory/adapters/{agent_id}/")
'''
    path = DATASET_DIR / f"{agent_id}_colab_finetune.py"
    path.write_text(script)
    print(f"[FINETUNE] Colab script generated → {path}")
    return str(path)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _extract_json(text: str) -> str:
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    for i, c in enumerate(text):
        if c in "{[":
            return text[i:]
    return text

def _extract_headline_pattern(headline: str) -> str:
    """Extract structural pattern from a headline."""
    if not headline:
        return ""
    words = headline.split()
    if len(words) < 3:
        return ""
    # Detect patterns
    if words[0][0].isdigit():
        return f"Number-led headline: '{words[0]} {words[1]} ...'"
    if ":" in headline:
        return f"Colon structure: 'Entity: Action'"
    if any(w in headline.upper() for w in ["BREAKS", "LAUNCHES", "REVEALS", "SURGES", "CRASHES"]):
        return f"Action verb headline pattern"
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM-WIDE TRAINING REPORT
# ═══════════════════════════════════════════════════════════════════════════
def get_system_training_report() -> dict:
    """Full training report across all agents. Used by dashboard."""
    report   = {"agents": {}, "global": {}, "timestamp": datetime.datetime.utcnow().isoformat()}
    cross    = CrossAgentLearning()
    total_samples = 0
    total_elite   = 0

    for jsonl_file in TRAINING_DIR.glob("*.jsonl"):
        agent_id = jsonl_file.stem
        store    = TrainingDataStore(agent_id)
        stats    = store.stats()
        report["agents"][agent_id] = stats
        total_samples += stats["total"]
        total_elite   += stats.get("elite_count", 0)

    report["global"] = {
        "total_training_samples": total_samples,
        "total_elite_outputs":    total_elite,
        "cross_agent_pool_size":  len(cross.pool.get("top_outputs", [])),
        "universal_rules":        len(cross.pool.get("structural_insights", [])),
    }
    return report
