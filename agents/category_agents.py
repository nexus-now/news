"""
NEXUS NOW — 8 Category Specialist Agents
Each agent is a domain expert. All inherit from NexusAgent.
"""
import json
import datetime
from agents.base_agent import NexusAgent, gemini_raw
from agents.ai_client import extract_json
from agents.ai_client  import ai_text


def _ts() -> str:
    return datetime.datetime.utcnow().strftime("%B %d, %Y")


def _run_agent(agent: NexusAgent, topic: str, angle: str,
               system_prompt: str, output_instructions: str) -> dict:
    """
    Shared generation runner for all 8 agents.
    Handles training context, generation, evaluation, and recording.
    """
    agent.increment_run()
    system   = agent.get_prompt()
    training = agent.get_training_context()

    prompt = (
        f"{training}"
        f"TODAY: {_ts()}\n"
        f"TOPIC: {topic}\n"
        f"ANGLE: {angle}\n\n"
        f"{output_instructions}"
    )

    try:
        raw    = gemini_raw(prompt, max_tokens=2500, system=system)
        result = json.loads(extract_json(raw))
    except Exception as e:
        agent.log(f"Generation error: {e}")
        # Return minimal valid content so pipeline continues
        return {
            "headline":    f"Breaking: {topic[:60]}",
            "subheadline": "Developing story",
            "summary":     f"NEXUS NOW is monitoring this developing story about {topic}.",
            "key_facts":   [f"Topic: {topic}", "Story developing", "More updates coming"],
            "deep_analysis": f"This story about {topic} is currently being monitored by our AI agents.",
            "video_script": f"Welcome to NEXUS NOW. We're tracking breaking developments on {topic}. Stay tuned for updates.",
            "youtube_title": f"{topic[:55]} | NEXUS NOW",
            "youtube_description": f"NEXUS NOW brings you the latest on {topic}.",
            "youtube_tags": ["nexusnow", "news", "breaking", topic[:20]],
            "instagram_caption": f"BREAKING: {topic}\n\nFollow @nexusnow for live updates.\n#NexusNow #BreakingNews",
            "tweet_thread": [
                f"🔴 NEXUS NOW: {topic[:200]} — More details to follow. 🧵 1/3",
                f"Our AI agents are researching this story now. 2/3",
                f"Follow @NexusNow for real-time updates. #NexusNow #News 3/3"
            ],
            "thumbnail_prompt": (
                f"Professional news thumbnail: dark background, bold red text saying "
                f"BREAKING NEWS, dramatic imagery related to {topic[:30]}, "
                f"NEXUS NOW logo, broadcast aesthetic"
            ),
            "tags":         ["news", "breaking"],
            "quality_notes": "Fallback content — AI generation failed",
            "quality_score": 4.0,
        }

    score = agent.evaluate(result)
    result["quality_score"] = score
    agent.record(result.get("headline", topic), score)
    agent.log(f"'{result.get('headline','')[:50]}' Q={score:.1f}/10")
    return result


def _schema(agent_name: str, category: str, extra: str = "") -> str:
    """Standard JSON output schema for all agents."""
    return f"""Return ONLY valid JSON with these exact fields:
{{
  "agent": "{agent_name}",
  "category": "{category}",
  "headline": "Compelling headline, max 12 words, specific names/numbers",
  "subheadline": "Supporting context, max 20 words",
  "summary": "3 sentences: what happened, why it matters, what comes next",
  "key_facts": ["Specific fact with data 1", "Fact 2", "Fact 3", "Fact 4", "Fact 5"],
  "deep_analysis": "4 paragraphs: (1) what exactly happened, (2) root causes, (3) ripple effects, (4) outlook",
  {extra}
  "video_script": "70-second TV anchor script, 175-200 words. Strong opening hook. Clear story arc. Forward-looking close.",
  "youtube_title": "SEO-optimised title max 70 chars, include 2026",
  "youtube_description": "200 words. Background, key points, context. Professional.",
  "youtube_tags": ["nexusnow", "news", "{category.lower()}", "breaking", "2026", "tag5", "tag6", "tag7"],
  "instagram_caption": "Hook first line. 3 key points as bullets. Call to action. 15 hashtags including #NexusNow",
  "tweet_thread": [
    "Tweet 1/5: Hook with key fact, max 270 chars",
    "Tweet 2/5: The details, max 270 chars",
    "Tweet 3/5: Why it matters, max 270 chars",
    "Tweet 4/5: Expert context or reaction, max 270 chars",
    "Tweet 5/5: CTA + Follow @NexusNow, max 270 chars"
  ],
  "thumbnail_prompt": "AI image prompt: dark dramatic background, bold white headline text, red NEXUS NOW brand accent, specific visual elements for this story",
  "tags": ["{category.lower()}", "nexusnow", "news"],
  "quality_notes": "Brief self-assessment of this article"
}}"""


# ═══════════════════════════════════════════════════════════════════════════
# 1. TITAN — Business & Finance
# ═══════════════════════════════════════════════════════════════════════════
class TitanAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are TITAN, NEXUS NOW's Business & Finance expert. "
        "ALWAYS lead with specific numbers. Name companies and executives. "
        "Connect market moves to everyday consumer impact. "
        "Include: market reaction, analyst view, what to watch next. "
        "Use strong financial verbs: surges, plummets, disrupts, outpaces."
    )

    def __init__(self):
        super().__init__("titan_business", "business")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"market_impact": "Specific price/percentage movement and which index/stock",'
            '\n  "consumer_impact": "How this affects ordinary people — 1-2 sentences",'
        )
        instructions = (
            f"Write a BUSINESS & FINANCE news package about: {topic}\n"
            f"Angle: {trend.get('angle','Latest market developments')}\n\n"
            + _schema("TITAN", "Business & Finance", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# 2. PULSE — Science & Health
# ═══════════════════════════════════════════════════════════════════════════
class PulseAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are PULSE, NEXUS NOW's Science & Health expert. "
        "ALWAYS cite the research institution or journal by name. "
        "State sample size for medical studies. Explain methodology briefly. "
        "Give timeline to real-world application. Include expert caveat. "
        "Make complex science accessible without dumbing it down."
    )

    def __init__(self):
        super().__init__("pulse_science", "science")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"research_source": "Institution, journal, or agency name",'
            '\n  "timeline": "When will this reach patients/consumers?",'
            '\n  "expert_caveat": "Important limitation or \'more research needed\' note",'
        )
        instructions = (
            f"Write a SCIENCE & HEALTH news package about: {topic}\n"
            f"Angle: {trend.get('angle','Scientific significance')}\n\n"
            + _schema("PULSE", "Science & Health", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# 3. VOLT — Technology & AI
# ═══════════════════════════════════════════════════════════════════════════
class VoltAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are VOLT, NEXUS NOW's Technology & AI expert. "
        "ALWAYS name the specific company and product. Cut hype with facts. "
        "Explain technical concepts with one plain-English analogy. "
        "State competitive winners and losers. Cover privacy/safety risks. "
        "Include valuation or market size for context."
    )

    def __init__(self):
        super().__init__("volt_technology", "technology")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"plain_english": "One sentence analogy explaining the tech to a non-technical person",'
            '\n  "risk": "Privacy, safety, or competitive risk in 1-2 sentences",'
        )
        instructions = (
            f"Write a TECHNOLOGY news package about: {topic}\n"
            f"Angle: {trend.get('angle','Tech industry impact')}\n\n"
            + _schema("VOLT", "Technology", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# 4. ARENA — Sports
# ═══════════════════════════════════════════════════════════════════════════
class ArenaAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are ARENA, NEXUS NOW's Sports expert. "
        "ALWAYS include specific scores, statistics, and player names. "
        "State historical significance — is this a record? "
        "Capture the fan emotion and drama. Cover rivalries and storylines. "
        "Always close with what happens next — fixtures, implications."
    )

    def __init__(self):
        super().__init__("arena_sports", "sports")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"historical_note": "Record broken? First time? Historical significance?",'
            '\n  "fan_emotion": "How supporters of both sides feel — vivid 2 sentences",'
        )
        instructions = (
            f"Write a SPORTS news package about: {topic}\n"
            f"Angle: {trend.get('angle','Match/event significance')}\n\n"
            + _schema("ARENA", "Sports", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# 5. NEXUS — World Politics & Geopolitics
# ═══════════════════════════════════════════════════════════════════════════
class NexusAgent_(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are NEXUS, NEXUS NOW's World Politics expert. "
        "ALWAYS present all sides without personal opinion. "
        "Cite governments, officials, and international bodies by name. "
        "Explain geopolitical context — why this region matters. "
        "Note civilian/humanitarian impact. Never use inflammatory language."
    )

    def __init__(self):
        super().__init__("nexus_politics", "world politics")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"side_a": "Position of the first party/government",'
            '\n  "side_b": "Position of the second party/government",'
            '\n  "international_view": "What the broader world community says",'
            '\n  "humanitarian": "Civilian or humanitarian dimension — 2 sentences",'
        )
        instructions = (
            f"Write a WORLD POLITICS news package about: {topic}\n"
            f"Angle: {trend.get('angle','Geopolitical significance')}\n\n"
            + _schema("NEXUS", "World Politics", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# 6. PRISM — Entertainment & Culture
# ═══════════════════════════════════════════════════════════════════════════
class PrismAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are PRISM, NEXUS NOW's Entertainment & Culture expert. "
        "ALWAYS mention fan reactions and social media buzz by name. "
        "Include box office, streaming numbers, or chart positions. "
        "Be energetic and culturally plugged-in. "
        "Connect this moment to broader cultural trends."
    )

    def __init__(self):
        super().__init__("prism_entertainment", "entertainment")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"fan_reaction": "How fans and social media are responding",'
            '\n  "cultural_significance": "What this moment says about culture today",'
        )
        instructions = (
            f"Write an ENTERTAINMENT & CULTURE news package about: {topic}\n"
            f"Angle: {trend.get('angle','Cultural impact')}\n\n"
            + _schema("PRISM", "Entertainment", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# 7. TERRA — Environment & Climate
# ═══════════════════════════════════════════════════════════════════════════
class TerraAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are TERRA, NEXUS NOW's Environment & Climate expert. "
        "ALWAYS cite a named scientific body: NOAA, NASA, IPCC, WHO. "
        "Give geographic scope and affected population size. "
        "Cover solutions equally to problems — never only doom. "
        "End with one actionable item for readers or policymakers."
    )

    def __init__(self):
        super().__init__("terra_environment", "environment")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"scientific_source": "Named body: NOAA/NASA/IPCC/WHO etc",'
            '\n  "solutions": "What solutions exist — tech, policy, or individual action",'
            '\n  "action_item": "One concrete thing readers can do",'
        )
        instructions = (
            f"Write an ENVIRONMENT & CLIMATE news package about: {topic}\n"
            f"Angle: {trend.get('angle','Environmental impact and solutions')}\n\n"
            + _schema("TERRA", "Environment", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# 8. CIPHER — Crime & Justice
# ═══════════════════════════════════════════════════════════════════════════
class CipherAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are CIPHER, NEXUS NOW's Crime & Justice expert. "
        "ALWAYS use 'alleged' when charges are unproven. "
        "State the court and jurisdiction explicitly. "
        "Explain legal process in plain language for non-lawyers. "
        "Balance victim impact and due process equally. "
        "State next legal steps or upcoming proceedings."
    )

    def __init__(self):
        super().__init__("cipher_crime", "crime")

    def research_and_write(self, topic: str, trend: dict) -> dict:
        extra = (
            '"court_jurisdiction": "Court name and jurisdiction",'
            '\n  "legal_explanation": "Plain-language explanation of the law involved",'
            '\n  "next_steps": "Next legal proceedings or court dates",'
        )
        instructions = (
            f"Write a CRIME & JUSTICE news package about: {topic}\n"
            f"Angle: {trend.get('angle','Legal significance')}\n\n"
            + _schema("CIPHER", "Crime & Justice", extra)
        )
        return _run_agent(self, topic, trend.get("angle",""), self.BASE_SYSTEM_PROMPT, instructions)


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════
_REGISTRY: dict[str, type] = {
    "technology":    VoltAgent,    "tech":          VoltAgent,
    "ai":            VoltAgent,    "cyber":         VoltAgent,
    "business":      TitanAgent,   "finance":       TitanAgent,
    "economy":       TitanAgent,   "market":        TitanAgent,
    "science":       PulseAgent,   "health":        PulseAgent,
    "medical":       PulseAgent,   "space":         PulseAgent,
    "sports":        ArenaAgent,   "football":      ArenaAgent,
    "cricket":       ArenaAgent,   "basketball":    ArenaAgent,
    "politics":      NexusAgent_,  "world":         NexusAgent_,
    "geopolitics":   NexusAgent_,  "war":           NexusAgent_,
    "entertainment": PrismAgent,   "celebrity":     PrismAgent,
    "music":         PrismAgent,   "film":          PrismAgent,
    "environment":   TerraAgent,   "climate":       TerraAgent,
    "nature":        TerraAgent,   "energy":        TerraAgent,
    "crime":         CipherAgent,  "justice":       CipherAgent,
    "legal":         CipherAgent,  "court":         CipherAgent,
}


def get_agent(category: str) -> NexusAgent:
    """Return the correct specialist agent for a category string."""
    key = category.lower().strip().split()[0]
    cls = _REGISTRY.get(key, NexusAgent_)
    return cls()


def all_agents() -> list[NexusAgent]:
    """One instance of every unique agent class."""
    seen, agents = set(), []
    for cls in _REGISTRY.values():
        name = cls.__name__
        if name not in seen:
            seen.add(name)
            agents.append(cls())
    return agents
