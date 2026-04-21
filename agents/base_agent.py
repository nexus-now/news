"""
NEXUS NOW - Base Agent
All specialist agents inherit from this.
Real self-improvement: memory, evaluation, prompt evolution, learning loops.
"""
import json, datetime
from pathlib import Path
from agents.ai_client import ai_text, extract_json


def gemini_raw(prompt: str, max_tokens: int = 2000, system: str = "") -> str:
    return ai_text(prompt, system=system, max_tokens=max_tokens)


class NexusAgent:
    BASE_SYSTEM_PROMPT = "You are a NEXUS NOW AI journalist."

    def __init__(self, agent_id: str, category: str = "general"):
        self.agent_id    = agent_id
        self.category    = category
        self.memory_dir  = Path("agent_memory")
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_path = self.memory_dir / f"{agent_id}.json"
        self.memory      = self._load()

    # ── MEMORY ────────────────────────────────────────────────────────────
    def _load(self) -> dict:
        if self.memory_path.exists():
            try:
                return json.loads(self.memory_path.read_text())
            except Exception:
                pass
        return {
            "agent_id":      self.agent_id,
            "category":      self.category,
            "generation":    0,
            "total_runs":    0,
            "total_articles":0,
            "avg_quality":   0.0,
            "best_score":    0.0,
            "evolved_prompt":"",
            "strategy":      "default",
            "learned_rules": [],
            "avoid_rules":   [],
            "top_articles":  [],
            "history":       [],
            "last_updated":  "",
        }

    def save(self):
        try:
            self.memory["last_updated"] = datetime.datetime.utcnow().isoformat()
            self.memory_path.write_text(
                json.dumps(self.memory, indent=2, ensure_ascii=False))
        except Exception as e:
            self.log(f"Memory save error: {e}")

    # ── SELF-IMPROVEMENT ──────────────────────────────────────────────────
    def get_prompt(self) -> str:
        """Return current evolved system prompt."""
        p = self.memory.get("evolved_prompt", "")
        if not p:
            self.memory["evolved_prompt"] = self.BASE_SYSTEM_PROMPT
            self.save()
            return self.BASE_SYSTEM_PROMPT
        # Evolve every 5 runs
        if self.memory.get("total_runs", 0) > 0 and self.memory["total_runs"] % 5 == 0:
            self._evolve_prompt(p)
        return self.memory["evolved_prompt"]

    def _evolve_prompt(self, current: str):
        """Ask AI to rewrite the system prompt better using what it learned."""
        rules = self.memory.get("learned_rules", [])[:6]
        avoid = self.memory.get("avoid_rules",   [])[:4]
        avg   = self.memory.get("avg_quality",   0)
        runs  = self.memory.get("total_runs",    0)
        strat = self.memory.get("strategy",      "default")
        try:
            new = ai_text(
                f"Improve this {self.category} news agent system prompt.\n"
                f"Performance: {avg:.1f}/10 avg over {runs} runs.\n"
                f"Current strategy: {strat}\n"
                f"Always do: {rules}\n"
                f"Never do: {avoid}\n\n"
                f"Current prompt:\n{current}\n\n"
                f"Write an improved version. Return prompt text only.",
                max_tokens=600)
            if new and len(new.strip()) > 30:
                self.memory["evolved_prompt"] = new.strip()
                self.memory["generation"] = self.memory.get("generation", 0) + 1
                self.save()
                self.log(f"Prompt evolved → Generation {self.memory['generation']}")
        except Exception as e:
            self.log(f"Prompt evolution skipped: {e}")

    def evaluate(self, content: dict) -> float:
        """Score output 0-10, extract rules, update strategy."""
        headline = content.get("headline", "")
        summary  = content.get("summary", "")
        if not headline:
            return 5.0
        try:
            raw = ai_text(
                f"Score this {self.category} news article 0.0 to 10.0.\n"
                f"Headline: {headline}\n"
                f"Summary: {summary[:250]}\n"
                f"Return ONLY JSON: "
                f'{"{"}"score":7.5,"rules":["what worked"],"avoid":["what failed"]{"}"}',
                max_tokens=150)
            data  = json.loads(extract_json(raw))
            score = float(max(0.0, min(10.0, data.get("score", 5.0))))

            # Learn from result
            for r in data.get("rules", []):
                if r not in self.memory["learned_rules"]:
                    self.memory["learned_rules"].append(r)
            self.memory["learned_rules"] = self.memory["learned_rules"][-25:]

            for a in data.get("avoid", []):
                if a not in self.memory["avoid_rules"]:
                    self.memory["avoid_rules"].append(a)
            self.memory["avoid_rules"] = self.memory["avoid_rules"][-15:]

            return score
        except Exception:
            return 5.0

    def update_strategy(self, score: float):
        """
        Real learning loop — updates strategy based on score.
        This drives actual behaviour change next run.
        """
        if score < 5.0:
            self.memory["strategy"] = "improve_hook_and_specificity"
        elif score < 7.0:
            self.memory["strategy"] = "add_more_data_and_context"
        else:
            self.memory["strategy"] = "reuse_format_and_structure"

    def record(self, headline: str, score: float, category: str):
        """Record performance and update all metrics."""
        self.memory["total_articles"] = self.memory.get("total_articles", 0) + 1

        # Update history
        hist = self.memory.get("history", [])
        hist.append({
            "headline": headline[:80],
            "score":    score,
            "category": category,
            "ts":       datetime.datetime.utcnow().isoformat()
        })
        self.memory["history"] = hist[-50:]

        # Update running averages
        scores = [h["score"] for h in self.memory["history"]]
        self.memory["avg_quality"] = round(sum(scores) / len(scores), 2)
        self.memory["best_score"]  = max(self.memory.get("best_score", 0), score)

        # Track top articles
        if score >= 7.5:
            top = self.memory.get("top_articles", [])
            top.append({"headline": headline[:80], "score": score})
            self.memory["top_articles"] = sorted(
                top, key=lambda x: x["score"], reverse=True)[:10]

        # Update strategy
        self.update_strategy(score)
        self.save()

    def increment_run(self):
        self.memory["total_runs"] = self.memory.get("total_runs", 0) + 1
        self.save()

    def get_training_context(self) -> str:
        """Build few-shot learning block from past performance."""
        top   = self.memory.get("top_articles", [])
        rules = self.memory.get("learned_rules", [])
        avoid = self.memory.get("avoid_rules",   [])
        runs  = self.memory.get("total_runs",    0)
        avg   = self.memory.get("avg_quality",   0)
        gen   = self.memory.get("generation",    0)
        strat = self.memory.get("strategy",      "default")

        if not top and not rules:
            return ""

        lines = [f"\n[MEMORY: Run#{runs} AvgQ:{avg}/10 Gen:{gen} Strategy:{strat}]"]
        if rules:
            lines.append("ALWAYS DO: " + " | ".join(rules[:4]))
        if avoid:
            lines.append("NEVER DO: " + " | ".join(avoid[:3]))
        if top:
            lines.append("YOUR BEST PAST HEADLINES (replicate this quality):")
            for t in top[:3]:
                lines.append(f"  [{t['score']}/10] {t['headline']}")
        return "\n".join(lines) + "\n"

    def log(self, msg: str):
        ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
        print(f"  [{ts}][{self.agent_id.upper()}] {msg}")
