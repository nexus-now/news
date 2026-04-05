"""
NEXUS NOW — Base Agent
=======================
Parent class for all agents. Self-training built in.
gemini_raw and extract_json exported for subclasses.
"""
import os
import json
import datetime
from pathlib import Path
from agents.ai_client import ai_text, extract_json


# Re-export for subclasses that import from here
def gemini_raw(prompt: str, max_tokens: int = 2000, system: str = "") -> str:
    """Wrapper around ai_text for backward compatibility."""
    return ai_text(prompt, system=system, max_tokens=max_tokens)


class NexusAgent:
    """Base class — all specialist agents inherit from this."""
    BASE_SYSTEM_PROMPT = "You are a NEXUS NOW AI journalist."

    def __init__(self, agent_id: str, category: str = "general"):
        self.agent_id    = agent_id
        self.category    = category
        self.memory_dir  = Path("agent_memory")
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_path = self.memory_dir / f"{agent_id}.json"
        self.memory      = self._load_memory()

    # ── MEMORY ────────────────────────────────────────────────────────────
    def _load_memory(self) -> dict:
        if self.memory_path.exists():
            try:
                return json.loads(self.memory_path.read_text())
            except Exception:
                pass
        return self._blank_memory()

    def _blank_memory(self) -> dict:
        return {
            "agent_id":        self.agent_id,
            "category":        self.category,
            "generation":      0,
            "total_runs":      0,
            "total_articles":  0,
            "avg_quality":     0.0,
            "best_score":      0.0,
            "evolved_prompt":  "",
            "learned_rules":   [],
            "avoid_rules":     [],
            "top_articles":    [],
            "run_log":         [],
            "last_updated":    "",
        }

    def save_memory(self):
        try:
            self.memory["last_updated"] = (
                datetime.datetime.utcnow().isoformat()
            )
            self.memory_path.write_text(
                json.dumps(self.memory, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            self.log(f"Memory save error (non-fatal): {e}")

    # ── PROMPT EVOLUTION ──────────────────────────────────────────────────
    def get_prompt(self) -> str:
        """Return the current evolved system prompt."""
        evolved = self.memory.get("evolved_prompt", "")
        if not evolved:
            self.memory["evolved_prompt"] = self.BASE_SYSTEM_PROMPT
            self.save_memory()
            return self.BASE_SYSTEM_PROMPT
        runs = self.memory.get("total_runs", 0)
        if runs > 0 and runs % 5 == 0:
            self._evolve()
        return self.memory["evolved_prompt"]

    def _evolve(self):
        """Rewrite the system prompt using accumulated learnings."""
        current  = self.memory.get("evolved_prompt", self.BASE_SYSTEM_PROMPT)
        rules    = self.memory.get("learned_rules", [])[:6]
        avoid    = self.memory.get("avoid_rules", [])[:4]
        avg      = self.memory.get("avg_quality", 0)
        runs     = self.memory.get("total_runs", 0)
        prompt   = (
            f"Improve this {self.category} news agent system prompt.\n"
            f"Current avg quality: {avg:.1f}/10 over {runs} runs.\n"
            f"What works well: {rules}\n"
            f"What to avoid: {avoid}\n\n"
            f"Current prompt:\n{current}\n\n"
            f"Write an improved version. Return only the prompt text."
        )
        try:
            new = ai_text(prompt, max_tokens=600)
            if new and len(new.strip()) > 30:
                self.memory["evolved_prompt"] = new.strip()
                self.memory["generation"] = self.memory.get("generation", 0) + 1
                self.save_memory()
                self.log(f"Prompt evolved → Gen {self.memory['generation']}")
        except Exception as e:
            self.log(f"Prompt evolution skipped: {e}")

    # ── SELF-EVALUATION ───────────────────────────────────────────────────
    def evaluate(self, content: dict) -> float:
        """Score the output 0-10. Learn from the result."""
        headline = content.get("headline", "")
        summary  = content.get("summary", "")
        if not headline:
            return 5.0
        prompt = (
            f"Score this {self.category} news article 0.0 to 10.0.\n"
            f"Headline: {headline}\n"
            f"Summary: {summary[:250]}\n"
            f"Criteria: accuracy, headline strength, clarity, domain expertise, originality.\n"
            f'Return ONLY: {{"score":7.5,"rules":["always do this"],"avoid":["never do this"]}}'
        )
        try:
            raw  = ai_text(prompt, max_tokens=150)
            data = json.loads(extract_json(raw))
            score = float(data.get("score", 5.0))
            score = max(0.0, min(10.0, score))
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

    # ── PERFORMANCE TRACKING ──────────────────────────────────────────────
    def record(self, title: str, score: float):
        self.memory["total_articles"] += 1
        log = self.memory.get("run_log", [])
        log.append({
            "title": title[:80],
            "score": score,
            "ts":    datetime.datetime.utcnow().isoformat()
        })
        self.memory["run_log"] = log[-50:]
        scores = [e["score"] for e in self.memory["run_log"]]
        self.memory["avg_quality"] = round(sum(scores) / len(scores), 2)
        self.memory["best_score"]  = max(
            self.memory.get("best_score", 0), score
        )
        if score >= 8.0:
            top = self.memory.get("top_articles", [])
            top.append({"title": title[:80], "score": score})
            self.memory["top_articles"] = sorted(
                top, key=lambda x: x["score"], reverse=True
            )[:10]
        self.save_memory()

    def increment_run(self):
        self.memory["total_runs"] = self.memory.get("total_runs", 0) + 1
        self.save_memory()

    # ── FEW-SHOT CONTEXT ──────────────────────────────────────────────────
    def get_training_context(self) -> str:
        """Build a training context block from past best outputs."""
        top     = self.memory.get("top_articles", [])
        rules   = self.memory.get("learned_rules", [])
        avoid   = self.memory.get("avoid_rules", [])
        runs    = self.memory.get("total_runs", 0)
        avg     = self.memory.get("avg_quality", 0)
        gen     = self.memory.get("generation", 0)
        if not top and not rules:
            return ""
        lines = [
            f"\n[AGENT MEMORY: Run#{runs} | AvgQ:{avg}/10 | Gen:{gen}]"
        ]
        if rules:
            lines.append("ALWAYS: " + " | ".join(rules[:4]))
        if avoid:
            lines.append("NEVER: " + " | ".join(avoid[:3]))
        if top:
            lines.append("YOUR BEST HEADLINES:")
            for t in top[:3]:
                lines.append(f"  {t['score']}/10: {t['title']}")
        return "\n".join(lines) + "\n"

    def log(self, msg: str):
        ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
        print(f"  [{ts}][{self.agent_id.upper()}] {msg}")
