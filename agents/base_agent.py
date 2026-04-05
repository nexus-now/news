"""
NEXUS NOW — Base Agent v3 (Full Self-Training)
================================================
Every subclass gets all 5 training layers automatically.
"""
import os, json, datetime
from pathlib import Path
from agents.free_ai_provider import ai_generate
from agents.training_engine  import AgentTrainer

def _extract_json(text):
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"): text = text[4:]
    for i,c in enumerate(text):
        if c in "{[": return text[i:]
    return text

class NexusAgent:
    BASE_SYSTEM_PROMPT = "You are a NEXUS NOW AI news agent."

    def __init__(self, agent_id: str, category: str = "general"):
        self.agent_id    = agent_id
        self.category    = category
        self.memory_dir  = Path("agent_memory")
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_path = self.memory_dir / f"{agent_id}.json"
        self.memory      = self._load_memory()
        self.trainer     = AgentTrainer(agent_id, category)

    def _load_memory(self):
        if self.memory_path.exists():
            try: return json.loads(self.memory_path.read_text())
            except: pass
        return {"agent_id":self.agent_id,"category":self.category,"generation":0,
                "total_runs":0,"total_articles":0,"avg_quality":0.0,"best_score":0.0,
                "evolved_prompt":"","learned_patterns":[],"avoid_patterns":[],
                "top_performing":[],"performance_log":[],"category_expertise":{},
                "prompt_history":[],"last_updated":None}

    def save_memory(self):
        self.memory["last_updated"] = datetime.datetime.utcnow().isoformat()
        self.memory_path.write_text(json.dumps(self.memory, indent=2))

    def get_evolved_prompt(self) -> str:
        evolved = self.memory.get("evolved_prompt","")
        runs    = self.memory.get("total_runs",0)
        if not evolved:
            self.memory["evolved_prompt"] = self.BASE_SYSTEM_PROMPT
            return self.BASE_SYSTEM_PROMPT
        if runs > 0 and runs % 5 == 0:
            evolved = self._evolve_prompt(evolved)
        return evolved

    def _evolve_prompt(self, current: str) -> str:
        report = self.trainer.get_training_report()
        wisdom = self.trainer.extractor.wisdom
        prompt = f"""Improve this {self.category} news agent system prompt using performance data.
Avg quality: {report['avg_quality']}/10 | Elite outputs: {report['elite_count']} | Rules learned: {report['rules_learned']}
CURRENT PROMPT: {current}
PROVEN RULES: {json.dumps(wisdom.get('rules',[])[:6])}
ANTI-RULES: {json.dumps(wisdom.get('anti_rules',[])[:4])}
Return ONLY the improved system prompt text."""
        try:
            new = ai_generate(prompt, max_tokens=1000)
            gen = self.memory.get("generation",0)+1
            self.memory["generation"] = gen
            self.memory["evolved_prompt"] = new
            self.memory["prompt_history"].append({"gen":gen,"ts":datetime.datetime.utcnow().isoformat(),"snippet":new[:120]})
            self.memory["prompt_history"] = self.memory["prompt_history"][-10:]
            self.save_memory()
            self.log(f"Prompt evolved → Gen {gen}")
            return new
        except Exception as e:
            self.log(f"Prompt evolution failed: {e}"); return current

    def record_performance(self, title, score, content_type, notes=""):
        self.memory["total_articles"] += 1
        log = self.memory.get("performance_log",[])
        log.append({"title":title,"score":score,"type":content_type,"notes":notes,"ts":datetime.datetime.utcnow().isoformat()})
        self.memory["performance_log"] = log[-50:]
        scores = [e["score"] for e in self.memory["performance_log"]]
        self.memory["avg_quality"] = round(sum(scores)/len(scores),2)
        self.memory["best_score"]  = max(self.memory.get("best_score",0),score)
        if score >= 8.0:
            top = self.memory.get("top_performing",[])
            top.append({"title":title,"score":score})
            self.memory["top_performing"] = sorted(top,key=lambda x:x["score"],reverse=True)[:10]
        self.save_memory()

    def self_evaluate(self, content: dict) -> float:
        prompt = f"""Score this {self.category} news content 0-10.
HEADLINE: {content.get('headline','')}
SUMMARY: {content.get('summary','')}
Return ONLY JSON: {{"score":7.5,"strengths":["s1"],"weaknesses":["w1"],"learned":"lesson"}}"""
        try:
            raw  = ai_generate(prompt, max_tokens=200)
            data = json.loads(_extract_json(raw))
            score = float(data.get("score",5.0))
            s = data.get("strengths",[]); w = data.get("weaknesses",[]); l = data.get("learned","")
            if s:
                self.memory["learned_patterns"].extend(s)
                self.memory["learned_patterns"] = list(set(self.memory["learned_patterns"]))[-30:]
            if w:
                self.memory["avoid_patterns"].extend(w)
                self.memory["avoid_patterns"] = list(set(self.memory["avoid_patterns"]))[-30:]
            content["_strengths"] = s; content["_weaknesses"] = w
            return score
        except: return 5.0

    def increment_run(self):
        self.memory["total_runs"] += 1
        self.save_memory()

    def log(self, msg):
        ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
        print(f"  [{ts}][{self.agent_id.upper()}] {msg}")

    def generate_with_training(self, topic: str, base_prompt: str, trend_context: dict = None) -> dict:
        """Core generation method — all 5 training layers fire here."""
        self.increment_run()
        system_prompt  = self.get_evolved_prompt()
        training_ctx   = self.trainer.build_training_context()
        full_prompt    = f"{training_ctx}\n\n{base_prompt}"
        try:
            raw     = ai_generate(full_prompt, system=system_prompt, max_tokens=3000)
            content = json.loads(_extract_json(raw))
        except Exception as e:
            self.log(f"Generation failed: {e}"); return {}
        score = self.self_evaluate(content)
        content["quality_score"] = score
        content["topic"]         = topic
        content = self.trainer.post_process(
            topic=topic, content=content,
            prompt_used=base_prompt[:500],
            ai_fn=lambda p: ai_generate(p, max_tokens=3000)
        )
        self.record_performance(content.get("headline",topic), content.get("quality_score",score), f"{self.category}_article")
        self.log(f"Done: '{content.get('headline','')}' Q={content.get('quality_score',0):.1f} Run#{self.memory['total_runs']}")
        return content
