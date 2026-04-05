"""
NEXUS NOW — 8 Category Specialist Agents
Each agent is a domain expert with its own training loop.
"""
import json, datetime
from agents.base_agent import NexusAgent, gemini_raw, extract_json
from agents.free_ai_provider import ai_generate


def _now(): return datetime.datetime.utcnow().strftime('%B %d, %Y')

def _build_prompt(agent_name, category, role_desc, output_schema, topic, trend_context, training_ctx=""):
    return f"""You are {agent_name}, the {category} correspondent for NEXUS NOW AI News Channel.
{role_desc}

{training_ctx}

TODAY: {_now()}
TRENDING TOPIC: {topic}
CONTEXT: {json.dumps(trend_context)}

Produce a comprehensive {category.upper()} news package.
Return ONLY valid JSON matching this schema exactly:
{output_schema}"""


# ═══════════════════════════════════════════════════════════════════════════
# SHARED OUTPUT SCHEMA BUILDER
# ═══════════════════════════════════════════════════════════════════════════
def standard_schema(agent_name, category, extra_fields=""):
    return f'''{{
  "agent": "{agent_name}",
  "category": "{category}",
  "headline": "Compelling headline max 12 words",
  "subheadline": "Supporting detail max 20 words",
  "summary": "3 sentences: what happened, why it matters, what comes next",
  "key_facts": ["fact 1 with specific data", "fact 2", "fact 3", "fact 4", "fact 5"],
  "deep_analysis": "4 paragraphs: (1) what happened, (2) why it happened, (3) ripple effects, (4) outlook",
  {extra_fields}
  "video_script": "75-second anchor script 190-210 words. Strong hook, clear story, forward-looking close.",
  "youtube_title": "SEO title max 70 chars including year 2026",
  "youtube_description": "200-word YouTube description with context and key points",
  "youtube_tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "instagram_caption": "Caption with hook, 3 bullet points, call to action, 15 relevant hashtags",
  "tweet_thread": ["Tweet 1/5 hook max 280 chars", "Tweet 2/5", "Tweet 3/5", "Tweet 4/5", "Tweet 5/5 with CTA"],
  "thumbnail_prompt": "Detailed AI image prompt: dark background, bold red/white text, dramatic visual",
  "tags": ["{category.lower()}", "nexusnow", "news", "breaking"],
  "quality_notes": "Self-assessment of this article quality"
}}'''


# ═══════════════════════════════════════════════════════════════════════════
# 1. TITAN — Business & Finance
# ═══════════════════════════════════════════════════════════════════════════
class TitanAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are TITAN, Business & Finance expert for NEXUS NOW.
ALWAYS: Lead with specific numbers/percentages. Name companies and executives.
Connect Wall Street to Main Street impact. Include market reaction.
State what to watch next. Use strong financial verbs: surges, plummets, disrupts."""

    def __init__(self):
        super().__init__("titan_business", "business")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("TITAN", "Business & Finance",
            '"market_impact": "Specific market/stock reaction",\n  '
            '"for_everyday_people": "How this affects ordinary consumers in 2 sentences",')

        prompt = _build_prompt("TITAN","Business & Finance",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw     = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result  = json.loads(extract_json(raw))
            score   = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "business_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# 2. PULSE — Science & Health
# ═══════════════════════════════════════════════════════════════════════════
class PulseAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are PULSE, Science & Health expert for NEXUS NOW.
ALWAYS: Cite the research institution or journal. State sample size if medical.
Explain the methodology briefly. Give timeline to real-world application.
Include expert caveat or limitation. Make complex science accessible."""

    def __init__(self):
        super().__init__("pulse_science", "science")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("PULSE", "Science & Health",
            '"research_source": "Institution and journal if applicable",\n  '
            '"expert_caveat": "Important limitation or more-research-needed note",\n  '
            '"human_impact": "How this changes lives once applied — 2 sentences",')

        prompt = _build_prompt("PULSE","Science & Health",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw    = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result = json.loads(extract_json(raw))
            score  = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "science_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# 3. VOLT — Technology & AI
# ═══════════════════════════════════════════════════════════════════════════
class VoltAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are VOLT, Technology & AI expert for NEXUS NOW.
ALWAYS: Name the specific company and product. Cut through hype with facts.
Explain technical concepts using one simple analogy. Cover privacy/safety risks.
State who wins and who loses competitively. Include valuation or market context."""

    def __init__(self):
        super().__init__("volt_technology", "technology")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("VOLT", "Technology",
            '"tech_breakdown": "One analogy explaining the tech to a non-technical person",\n  '
            '"risk_assessment": "Privacy, safety, or monopoly risks in 2 sentences",')

        prompt = _build_prompt("VOLT","Technology & AI",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw    = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result = json.loads(extract_json(raw))
            score  = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "tech_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# 4. ARENA — Sports
# ═══════════════════════════════════════════════════════════════════════════
class ArenaAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are ARENA, Sports expert for NEXUS NOW.
ALWAYS: Include specific scores, stats, and player names. State historical significance.
Give fan perspective. Cover the human drama — comebacks, controversies, records.
Always say what's next — upcoming fixtures or implications for standings."""

    def __init__(self):
        super().__init__("arena_sports", "sports")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("ARENA", "Sports",
            '"historical_context": "Is this a record? How rare? Historical significance?",\n  '
            '"fan_reaction": "How fans of both sides feel — 2 emotional sentences",')

        prompt = _build_prompt("ARENA","Sports",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw    = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result = json.loads(extract_json(raw))
            score  = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "sports_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# 5. NEXUS — World Politics
# ═══════════════════════════════════════════════════════════════════════════
class NexusPoliticsAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are NEXUS, World Politics expert for NEXUS NOW.
ALWAYS: Present ALL sides without personal opinion. Cite governments and officials.
Explain geopolitical context — why this region or issue matters globally.
Note civilian/humanitarian impact. Use precise, measured language — never inflammatory."""

    def __init__(self):
        super().__init__("nexus_politics", "world politics")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("NEXUS", "World Politics",
            '"multiple_perspectives": {"side_a": "Position of party A", "side_b": "Position of party B", "international": "Broader international view"},\n  '
            '"humanitarian_note": "Civilian or humanitarian dimension — 2 sentences",')

        prompt = _build_prompt("NEXUS","World Politics",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw    = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result = json.loads(extract_json(raw))
            score  = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "politics_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# 6. PRISM — Entertainment
# ═══════════════════════════════════════════════════════════════════════════
class PrismAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are PRISM, Entertainment & Culture expert for NEXUS NOW.
ALWAYS: Reference fan reactions and social media buzz. Include box office or streaming numbers.
Connect pop culture to broader social trends. Be energetic and culturally plugged-in.
State the cultural significance — what does this moment say about society?"""

    def __init__(self):
        super().__init__("prism_entertainment", "entertainment")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("PRISM", "Entertainment",
            '"fan_reaction": "Social media mood and fan response",\n  '
            '"cultural_take": "Broader cultural significance in 2 sentences",')

        prompt = _build_prompt("PRISM","Entertainment & Culture",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw    = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result = json.loads(extract_json(raw))
            score  = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "entertainment_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# 7. TERRA — Environment & Climate
# ═══════════════════════════════════════════════════════════════════════════
class TerraAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are TERRA, Environment & Climate expert for NEXUS NOW.
ALWAYS: Cite data from NOAA, NASA, IPCC or named scientific body. Give geographic scope.
Cover solutions equally as problems. Be urgent without being alarmist.
Include one actionable piece of information for readers or governments."""

    def __init__(self):
        super().__init__("terra_environment", "environment")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("TERRA", "Environment",
            '"solutions_angle": "What solutions exist — technological, policy, individual?",\n  '
            '"action_item": "One concrete thing readers can do or be aware of",')

        prompt = _build_prompt("TERRA","Environment & Climate",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw    = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result = json.loads(extract_json(raw))
            score  = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "environment_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# 8. CIPHER — Crime & Justice
# ═══════════════════════════════════════════════════════════════════════════
class CipherAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are CIPHER, Crime & Justice expert for NEXUS NOW.
ALWAYS: Use "alleged" when charges are not proven. State the court and jurisdiction.
Explain legal process for non-lawyers. Balance victim impact AND due process.
State next legal steps or proceedings. Be legally precise, never sensationalist."""

    def __init__(self):
        super().__init__("cipher_crime", "crime")

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        training_ctx = ""
        if self.trainer:
            try: training_ctx = self.trainer.build_training_context()
            except: pass

        schema = standard_schema("CIPHER", "Crime & Justice",
            '"legal_context": "What law is at issue and why it matters",\n  '
            '"due_process_note": "Presumption of innocence reminder if charges not proven",')

        prompt = _build_prompt("CIPHER","Crime & Justice",
            self.BASE_SYSTEM_PROMPT, schema, topic, trend_context, training_ctx)
        try:
            raw    = gemini_raw(prompt, max_tokens=2500, system=self.get_evolved_prompt())
            result = json.loads(extract_json(raw))
            score  = self.self_evaluate(result)
            result["quality_score"] = score
            if self.trainer:
                result = self.trainer.post_process(topic, result, prompt[:500],
                    ai_fn=lambda p: ai_generate(p, max_tokens=2500))
            self.record_performance(result.get("headline", topic), result.get("quality_score", score), "crime_article")
            self.log(f"'{result.get('headline','')}' Q={result.get('quality_score',0):.1f}")
            return result
        except Exception as e:
            self.log(f"Error: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════
AGENT_REGISTRY = {
    "business": TitanAgent, "finance": TitanAgent, "economy": TitanAgent, "market": TitanAgent,
    "science": PulseAgent,  "health": PulseAgent,  "medical": PulseAgent, "space": PulseAgent,
    "technology": VoltAgent,"tech": VoltAgent,     "ai": VoltAgent,       "cyber": VoltAgent,
    "sports": ArenaAgent,   "football": ArenaAgent,"cricket": ArenaAgent, "basketball": ArenaAgent,
    "politics": NexusPoliticsAgent, "world": NexusPoliticsAgent,
    "geopolitics": NexusPoliticsAgent, "war": NexusPoliticsAgent,
    "entertainment": PrismAgent, "celebrity": PrismAgent,
    "film": PrismAgent, "music": PrismAgent,
    "environment": TerraAgent, "climate": TerraAgent,
    "nature": TerraAgent, "energy": TerraAgent,
    "crime": CipherAgent, "justice": CipherAgent,
    "legal": CipherAgent, "court": CipherAgent,
}

def get_agent_for_category(category: str):
    cat = category.lower().strip().split()[0]
    cls = AGENT_REGISTRY.get(cat, NexusPoliticsAgent)
    return cls()

def get_all_agents():
    seen, agents = set(), []
    for cls in AGENT_REGISTRY.values():
        if cls.__name__ not in seen:
            seen.add(cls.__name__)
            agents.append(cls())
    return agents
