"""
NEXUS NOW - 8 Specialist Category Agents
Each is a domain expert with self-improvement built in.
"""
import json, datetime
from agents.base_agent import NexusAgent, gemini_raw
from agents.ai_client  import extract_json


def _date():
    return datetime.datetime.utcnow().strftime("%B %d, %Y")


def _schema(agent_name, category, extra=""):
    return (
        f'Return ONLY valid JSON:\n{{\n'
        f'  "agent": "{agent_name}",\n'
        f'  "category": "{category}",\n'
        f'  "headline": "Max 12 words, specific names and numbers",\n'
        f'  "subheadline": "Supporting detail, max 20 words",\n'
        f'  "summary": "3 sentences: what happened, why it matters, what comes next",\n'
        f'  "key_facts": ["specific fact 1","fact 2","fact 3","fact 4","fact 5"],\n'
        f'  "deep_analysis": "4 paragraphs: what happened, root causes, ripple effects, outlook",\n'
        f'{extra}'
        f'  "video_script": "70-second TV anchor script, 175-200 words, strong hook, clear close",\n'
        f'  "youtube_title": "SEO title max 70 chars including year 2026",\n'
        f'  "youtube_description": "200 words, context and key points",\n'
        f'  "youtube_tags": ["nexusnow","news","{category.lower()}","2026","breaking","tag5","tag6"],\n'
        f'  "instagram_caption": "Hook. 3 bullet points. CTA. 15 hashtags including #NexusNow",\n'
        f'  "tweet_thread": [\n'
        f'    "Tweet 1/5: Hook with key fact max 270 chars",\n'
        f'    "Tweet 2/5: The details",\n'
        f'    "Tweet 3/5: Why it matters",\n'
        f'    "Tweet 4/5: Context or expert view",\n'
        f'    "Tweet 5/5: CTA Follow @NexusNow"\n'
        f'  ],\n'
        f'  "thumbnail_prompt": "Dark dramatic background, bold headline text, red NEXUS NOW branding, broadcast aesthetic",\n'
        f'  "tags": ["{category.lower()}","nexusnow","news"],\n'
        f'  "quality_notes": "one sentence self-assessment"\n'
        f'}}'
    )


def _generate(agent: NexusAgent, topic: str, angle: str,
              system: str, instructions: str) -> dict:
    """Core generation: training context + generate + evaluate + record."""
    agent.increment_run()

    ctx    = agent.get_training_context()
    strat  = agent.memory.get("strategy", "default")
    prompt = (
        f"{ctx}"
        f"TODAY: {_date()}\n"
        f"TOPIC: {topic}\n"
        f"ANGLE: {angle}\n"
        f"STRATEGY THIS RUN: {strat}\n\n"
        f"{instructions}"
    )

    try:
        raw    = gemini_raw(prompt, max_tokens=2500, system=agent.get_prompt())
        result = json.loads(extract_json(raw))
    except Exception as e:
        agent.log(f"Generation error: {e} — using fallback")
        result = {
            "agent":       agent.agent_id,
            "category":    agent.category,
            "headline":    f"Breaking: {topic[:70]}",
            "subheadline": "Developing — NEXUS NOW",
            "summary":     f"NEXUS NOW is tracking {topic}. Full story developing.",
            "key_facts":   [f"Topic: {topic}", "Story developing"],
            "deep_analysis": f"Monitoring {topic} for updates.",
            "video_script":  f"Welcome to NEXUS NOW. We are tracking {topic}.",
            "youtube_title": f"{topic[:55]} | NEXUS NOW 2026",
            "youtube_description": f"NEXUS NOW covers {topic}.",
            "youtube_tags":  ["nexusnow", "news", "2026", "breaking"],
            "instagram_caption": f"🔴 {topic[:100]}\n\nFollow @nexusnow\n#NexusNow #News",
            "tweet_thread":  [
                f"🔴 NEXUS NOW: {topic[:230]} 1/3",
                f"Story developing. AI agents researching now. 2/3",
                f"Follow @NexusNow. #NexusNow #News 3/3"],
            "thumbnail_prompt": f"Breaking news thumbnail: {topic[:40]}, dark, NEXUS NOW red branding",
            "tags":          [agent.category, "news", "nexusnow"],
            "quality_notes": "Fallback content",
        }

    # Evaluate and learn
    score = agent.evaluate(result)
    result["quality_score"] = score
    agent.record(result.get("headline", topic), score, agent.category)
    agent.log(f"'{result.get('headline','')[:50]}' Q={score:.1f}/10 "
              f"Strategy={agent.memory.get('strategy')}")
    return result


# ── 8 SPECIALIST AGENTS ────────────────────────────────────────────────────

class TitanAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are TITAN, NEXUS NOW Business & Finance expert. "
        "ALWAYS: lead with specific numbers and percentages. "
        "Name companies, executives, and markets. "
        "Connect Wall Street to everyday consumer impact. "
        "Include market reaction and analyst outlook."
    )
    def __init__(self):
        super().__init__("titan_business", "business")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("TITAN","Business",
                '  "market_impact": "specific stock/index movement",\n'
                '  "consumer_impact": "how this affects ordinary people",\n'))


class PulseAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are PULSE, NEXUS NOW Science & Health expert. "
        "ALWAYS: cite the research institution by name. "
        "State sample size for medical studies. "
        "Explain the methodology briefly. "
        "Give realistic timeline to real-world application. "
        "Include expert caveat or limitation."
    )
    def __init__(self):
        super().__init__("pulse_science", "science")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("PULSE","Science",
                '  "research_source": "Institution and journal name",\n'
                '  "expert_caveat": "important limitation or more-research-needed note",\n'))


class VoltAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are VOLT, NEXUS NOW Technology & AI expert. "
        "ALWAYS: name the specific company and product. "
        "Cut through hype with concrete facts and specs. "
        "Explain with one plain-English analogy. "
        "State who wins, who loses competitively. "
        "Cover privacy and safety risks."
    )
    def __init__(self):
        super().__init__("volt_technology", "technology")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("VOLT","Technology",
                '  "plain_english": "one analogy for non-technical readers",\n'
                '  "risk": "privacy or safety concern in 1-2 sentences",\n'))


class ArenaAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are ARENA, NEXUS NOW Sports expert. "
        "ALWAYS: include specific scores, stats, and player names. "
        "State historical significance and records broken. "
        "Capture the fan emotion and drama vividly. "
        "Close with what happens next — upcoming fixtures."
    )
    def __init__(self):
        super().__init__("arena_sports", "sports")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("ARENA","Sports",
                '  "historical_note": "record broken or first-time achievement",\n'
                '  "fan_emotion": "vivid 2-sentence fan reaction",\n'))


class NexusPAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are NEXUS, NEXUS NOW World Politics expert. "
        "ALWAYS: present ALL sides without personal opinion. "
        "Cite governments, officials, and international bodies by name. "
        "Explain geopolitical context — why this region matters. "
        "Note civilian and humanitarian impact. "
        "Use precise, measured language."
    )
    def __init__(self):
        super().__init__("nexus_politics", "world politics")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("NEXUS","World Politics",
                '  "side_a": "position of first party",\n'
                '  "side_b": "position of second party",\n'
                '  "humanitarian": "civilian impact in 2 sentences",\n'))


class PrismAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are PRISM, NEXUS NOW Entertainment & Culture expert. "
        "ALWAYS: mention fan reactions and social media buzz specifically. "
        "Include box office, streaming, or chart numbers. "
        "Be energetic and culturally plugged-in. "
        "Connect to broader cultural trends."
    )
    def __init__(self):
        super().__init__("prism_entertainment", "entertainment")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("PRISM","Entertainment",
                '  "fan_reaction": "social media and fan response",\n'
                '  "cultural_note": "broader cultural significance",\n'))


class TerraAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are TERRA, NEXUS NOW Environment & Climate expert. "
        "ALWAYS: cite NOAA, NASA, IPCC, or WHO by name. "
        "Give geographic scope and affected population. "
        "Cover solutions equally — never only doom. "
        "End with one actionable item for readers."
    )
    def __init__(self):
        super().__init__("terra_environment", "environment")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("TERRA","Environment",
                '  "scientific_source": "named scientific body",\n'
                '  "solutions": "what can be done — tech, policy, individual",\n'))


class CipherAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are CIPHER, NEXUS NOW Crime & Justice expert. "
        "ALWAYS: use 'alleged' when charges are unproven. "
        "State the court and jurisdiction explicitly. "
        "Explain legal process in plain language. "
        "Balance victim impact and due process. "
        "State next legal steps."
    )
    def __init__(self):
        super().__init__("cipher_crime", "crime")
    def research_and_write(self, topic, trend):
        return _generate(self, topic, trend.get("angle",""),
            self.BASE_SYSTEM_PROMPT,
            _schema("CIPHER","Crime & Justice",
                '  "court_jurisdiction": "court name and jurisdiction",\n'
                '  "next_steps": "upcoming proceedings or court dates",\n'))


# ── REGISTRY ───────────────────────────────────────────────────────────────
_REG = {
    "technology":VoltAgent,  "tech":VoltAgent,    "ai":VoltAgent,
    "business":TitanAgent,   "finance":TitanAgent, "economy":TitanAgent,
    "science":PulseAgent,    "health":PulseAgent,  "medical":PulseAgent,
    "sports":ArenaAgent,     "football":ArenaAgent,"cricket":ArenaAgent,
    "politics":NexusPAgent,  "world":NexusPAgent,  "war":NexusPAgent,
    "entertainment":PrismAgent,"celebrity":PrismAgent,"music":PrismAgent,
    "environment":TerraAgent,"climate":TerraAgent, "nature":TerraAgent,
    "crime":CipherAgent,     "justice":CipherAgent,"legal":CipherAgent,
}

def get_agent(category: str) -> NexusAgent:
    key = category.lower().strip().split()[0]
    return (_REG.get(key) or NexusPAgent)()
