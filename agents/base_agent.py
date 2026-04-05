"""
NEXUS NOW — Base Agent v3
All agents inherit from this. Contains gemini_raw and extract_json
so all other agents can import them from here.
"""
import os, json, datetime, requests
from pathlib import Path
from .free_ai_provider import ai_generate
from .training_engine  import AgentTrainer

# ── SHARED HELPERS (exported — other agents import these) ──────────────────
def extract_json(text: str) -> str:
    """Strip markdown fences and find first { or [ in text."""
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

def gemini_raw(prompt: str, max_tokens: int = 2000, system: str = "") -> str:
    """
    Direct Gemini call — used by agents that need fine-grained control.
    Falls back to ai_generate (which tries all free providers).
    """
    return ai_generate(prompt, system=system, max_tokens=max_tokens)

# ── BASE AGENT CLASS ───────────────────────────────────────────────────────
class NexusAgent:
    """Parent class for all NEXUS NOW agents."""
    BASE_SYSTEM_PROMPT = "You are a NEXUS NOW AI news agent."

    def __init__(self, agent_id: str, category: str = "general"):
        self.agent_id    = agent_id
        self.category    = category
        self.memory_dir  = Path("agent_memory")
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_path = self.memory_dir / f"{agent_id}.json"
        self.memory      = self._load_memory()
        try:
            self.trainer = AgentTrainer(agent_id, category)
        except Exception as e:
            self.trainer = None
            self.log(f"Trainer init skipped: {e}")

    def _load_memory(self) -> dict:
        if self.memory_path.exists():
            try:
                return json.loads(self.memory_path.read_text())
            except:
                pass
        return {
            "agent_id": self.agent_id, "category": self.category,
            "generation": 0, "total_runs": 0, "total_articles": 0,
            "avg_quality": 0.0, "best_score": 0.0, "evolved_prompt": "",
            "learned_patterns": [], "avoid_patterns": [],
            "top_performing": [], "performance_log": [],
            "category_expertise": {}, "prompt_history": [],
            "last_updated": None
        }

    def save_memory(self):
        self.memory["last_updated"] = datetime.datetime.utcnow().isoformat()
        try:
            self.memory_path.write_text(json.dumps(self.memory, indent=2))
        except Exception as e:
            self.log(f"Memory save failed: {e}")

    def get_evolved_prompt(self) -> str:
        evolved = self.memory.get("evolved_prompt", "")
        runs    = self.memory.get("total_runs", 0)
        if not evolved:
            self.memory["evolved_prompt"] = self.BASE_SYSTEM_PROMPT
            return self.BASE_SYSTEM_PROMPT
        if runs > 0 and runs % 5 == 0:
            evolved = self._evolve_prompt(evolved)
        return evolved

    def _evolve_prompt(self, current: str) -> str:
        avg  = self.memory.get("avg_quality", 0)
        runs = self.memory.get("total_runs", 0)
        learned = self.memory.get("learned_patterns", [])[:6]
        avoid   = self.memory.get("avoid_patterns", [])[:4]
        prompt = f"""Improve this {self.category} news agent system prompt.
Performance: avg quality {avg:.1f}/10 over {runs} runs.
What worked: {json.dumps(learned)}
What failed: {json.dumps(avoid)}
Current prompt: {current}
Return ONLY the improved system prompt text. Make it more specific and expert."""
        try:
            new = ai_generate(prompt, max_tokens=800)
            if len(new.strip()) > 50:
                gen = self.memory.get("generation", 0) + 1
                self.memory["generation"] = gen
                self.memory["evolved_prompt"] = new
                self.memory["prompt_history"] = (
                    self.memory.get("prompt_history", []) + 
                    [{"gen": gen, "ts": datetime.datetime.utcnow().isoformat(), "snippet": new[:100]}]
                )[-10:]
                self.save_memory()
                self.log(f"Prompt evolved → Gen {gen}")
                return new
        except Exception as e:
            self.log(f"Prompt evolution failed: {e}")
        return current

    def record_performance(self, title: str, score: float,
                           content_type: str, notes: str = ""):
        self.memory["total_articles"] += 1
        log = self.memory.get("performance_log", [])
        log.append({"title": title, "score": score, "type": content_type,
                    "notes": notes, "ts": datetime.datetime.utcnow().isoformat()})
        self.memory["performance_log"] = log[-50:]
        scores = [e["score"] for e in self.memory["performance_log"]]
        self.memory["avg_quality"] = round(sum(scores) / len(scores), 2)
        self.memory["best_score"]  = max(self.memory.get("best_score", 0), score)
        if score >= 8.0:
            top = self.memory.get("top_performing", [])
            top.append({"title": title, "score": score})
            self.memory["top_performing"] = sorted(
                top, key=lambda x: x["score"], reverse=True)[:10]
        self.save_memory()

    def self_evaluate(self, content: dict) -> float:
        headline = content.get("headline", "")
        summary  = content.get("summary", "")
        if not headline:
            return 5.0
        prompt = (
            f"Score this {self.category} news article 0.0-10.0.\n"
            f"HEADLINE: {headline}\nSUMMARY: {summary[:300]}\n"
            f"Return ONLY JSON: "
            f'{"{"}"score":7.5,"strengths":["s1"],"weaknesses":["w1"]{"}"}'
        )
        try:
            raw  = ai_generate(prompt, max_tokens=150)
            data = json.loads(extract_json(raw))
            score = float(data.get("score", 5.0))
            score = max(0.0, min(10.0, score))
            s = data.get("strengths", [])
            w = data.get("weaknesses", [])
            if s:
                self.memory["learned_patterns"].extend(s)
                self.memory["learned_patterns"] = list(
                    set(self.memory["learned_patterns"]))[-30:]
            if w:
                self.memory["avoid_patterns"].extend(w)
                self.memory["avoid_patterns"] = list(
                    set(self.memory["avoid_patterns"]))[-30:]
            content["_strengths"] = s
            content["_weaknesses"] = w
            return score
        except:
            return 5.0

    def increment_run(self):
        self.memory["total_runs"] += 1
        self.save_memory()

    def log(self, msg: str):
        ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
        print(f"  [{ts}][{self.agent_id.upper()}] {msg}")

    def generate_with_training(self, topic: str, base_prompt: str,
                                trend_context: dict = None) -> dict:
        """Core method: training context + generate + evaluate + record."""
        self.increment_run()
        system_prompt = self.get_evolved_prompt()

        # Build training context if trainer available
        training_ctx = ""
        if self.trainer:
            try:
                training_ctx = self.trainer.build_training_context()
            except:
                pass

        full_prompt = f"{training_ctx}\n\n{base_prompt}" if training_ctx else base_prompt

        try:
            raw     = ai_generate(full_prompt, system=system_prompt, max_tokens=3000)
            content = json.loads(extract_json(raw))
        except Exception as e:
            self.log(f"Generation failed: {e}")
            return {}

        score = self.self_evaluate(content)
        content["quality_score"] = score
        content["topic"]         = topic

        # Record to training engine
        if self.trainer:
            try:
                content = self.trainer.post_process(
                    topic=topic, content=content,
                    prompt_used=base_prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=3000)
                )
            except Exception as e:
                self.log(f"Training post-process failed (non-fatal): {e}")

        self.record_performance(
            content.get("headline", topic),
            content.get("quality_score", score),
            f"{self.category}_article"
        )
        self.log(f"Done: '{content.get('headline', '')}' "
                 f"Q={content.get('quality_score', 0):.1f} "
                 f"Run#{self.memory['total_runs']}")
        return content
