"""
NEXUS NOW — Category News Agents
==================================
8 dedicated agents, each a domain expert in their category.
Each agent has:
  - Deep category-specific system prompt
  - Its own memory and self-improvement loop
  - Specialised content angles for its domain
  - Category-specific SEO and hashtag knowledge
  - Independent quality scoring for its domain

Categories:
  1. TITAN   — Business & Finance
  2. PULSE   — Science & Health
  3. VOLT    — Technology & AI
  4. ARENA   — Sports
  5. NEXUS   — World Politics & Geopolitics
  6. PRISM   — Entertainment & Culture
  7. TERRA   — Environment & Climate
  8. CIPHER  — Crime & Justice
"""

import json
from agents.base_agent import NexusAgent, gemini_raw, extract_json


# ═══════════════════════════════════════════════════════════════════════════
# 1. TITAN — Business & Finance Agent
# ═══════════════════════════════════════════════════════════════════════════
class TitanAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are TITAN, the Business & Finance correspondent for NEXUS NOW.

EXPERTISE:
- Stock markets, earnings reports, IPOs, M&A deals
- Central bank policy, inflation, interest rates
- Startup ecosystem, venture capital, unicorns
- Global trade, supply chains, economic indicators
- Personal finance impacts on everyday people

STYLE:
- Lead with market impact and numbers (always cite specific figures)
- Explain complex financial concepts in plain language
- Connect Wall Street to Main Street — how does this affect ordinary people?
- Use strong financial verbs: surges, plummets, outpaces, disrupts
- Always include: market reaction, expert outlook, what to watch next

ALWAYS INCLUDE in every story:
- At least 2 specific data points or percentages
- A "What This Means For You" angle
- Forward-looking market implication
"""

    def __init__(self):
        super().__init__("titan_business", "business")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING TOPIC: {topic}
TREND CONTEXT: {json.dumps(trend_context)}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce a comprehensive BUSINESS & FINANCE news package. Return ONLY this JSON:
{{
  "agent": "TITAN",
  "category": "Business & Finance",
  "headline": "Power headline with specific figure or company name (max 12 words)",
  "subheadline": "Supporting detail that adds urgency (max 20 words)",
  "summary": "3 sentences. Lead with the number/impact. Explain the mechanism. State the implication.",
  "key_facts": [
    "Specific statistic or data point 1",
    "Market reaction or movement",
    "Comparison to historical benchmark",
    "Expert or analyst reaction",
    "What happens next / outlook"
  ],
  "deep_analysis": "4-paragraph business analysis: (1) What happened and exact figures, (2) Why it happened — root causes, (3) Market and economic ripple effects, (4) Long-term strategic implications",
  "for_everyday_people": "2 sentences: How does this directly affect ordinary consumers or workers?",
  "market_indicators": {{"mentioned_stocks": [], "indices": [], "commodities": [], "currencies": []}},
  "video_script": "75-second authoritative anchor script. Open with a market stat. Build the story. End with outlook. 190-210 words.",
  "youtube_title": "SEO business title — include company/market/figure, year 2026 (max 70 chars)",
  "youtube_description": "250-word YT description with financial context, key points, disclaimer that this is news not financial advice",
  "youtube_tags": ["business news", "stock market", "finance", "economy", "investing", "2026", "breaking news", "wall street", "markets today"],
  "instagram_caption": "Business IG caption. Hook with emoji + stat. 3 bullet insights. CTA. 20 finance hashtags.",
  "tweet_thread": [
    "🔴 BREAKING BUSINESS: [hook with number] — Thread 🧵 1/6",
    "The numbers: [specific data] 2/6",
    "Why this happened: [root cause] 3/6",
    "Market reaction: [stocks/indices response] 4/6",
    "What experts say: [analyst take] 5/6",
    "Bottom line for you: [personal finance impact] + Follow @NexusNow for live business coverage 6/6"
  ],
  "thumbnail_prompt": "Dramatic business news thumbnail: Dark background with red/gold tones. Large bold white text overlay with headline. Visual: stock chart, skyscraper, or money symbol. NEXUS NOW logo bottom right. Professional broadcast aesthetic.",
  "tags": ["business", "finance", "economy", "markets"],
  "quality_notes": "Self-assessment of this article's business journalism quality"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(
            result.get("headline", topic),
            score,
            "business_article",
            result.get("quality_notes", "")
        )
        result["quality_score"] = score
        self.log(f"Published: '{result.get('headline')}' | Score: {score}/10")
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 2. PULSE — Science & Health Agent
# ═══════════════════════════════════════════════════════════════════════════
class PulseAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are PULSE, the Science & Health correspondent for NEXUS NOW.

EXPERTISE:
- Medical breakthroughs, clinical trials, FDA approvals
- Space exploration, astronomy, physics discoveries
- Biology, genetics, neuroscience research
- Public health, pandemics, mental health
- Nutrition science, longevity research

STYLE:
- Make complex science accessible without dumbing it down
- Always cite the journal, institution, or research body
- Explain the methodology briefly — how was this discovered?
- Address: Is this peer-reviewed? How large was the study?
- Connect to human impact — what does this change for patients/people?
- Use precise scientific language with lay explanations in parentheses

ALWAYS INCLUDE:
- The research institution or journal name
- Sample size or study scope if medical
- Timeline to real-world application
- Expert caveat or limitation of the finding
"""

    def __init__(self):
        super().__init__("pulse_science", "science")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING TOPIC: {topic}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce a comprehensive SCIENCE & HEALTH news package. Return ONLY this JSON:
{{
  "agent": "PULSE",
  "category": "Science & Health",
  "headline": "Clear, accurate science headline — no hype, all substance (max 12 words)",
  "subheadline": "Research context and implication (max 20 words)",
  "summary": "3 sentences: The discovery, the method, the implication for humanity.",
  "key_facts": [
    "Research institution and journal/source",
    "Core finding with specific measurement",
    "Study methodology and sample size",
    "What this changes vs. current understanding",
    "Timeline to practical application"
  ],
  "deep_analysis": "4-paragraph science analysis: (1) The discovery in plain terms, (2) How scientists found this, (3) What it overturns or confirms in current science, (4) Road to real-world impact and remaining questions",
  "expert_caveat": "Important limitation, caveat, or 'more research needed' note",
  "human_impact": "In 2 sentences: How will this change lives once applied?",
  "video_script": "75-second science journalist script. Open with the 'wow' factor. Explain clearly. End with what comes next. 190-210 words.",
  "youtube_title": "Science discovery title — include the breakthrough, 2026 (max 70 chars)",
  "youtube_description": "250-word science YT description — accessible, enthusiastic, accurate",
  "youtube_tags": ["science news", "health", "medical breakthrough", "research", "discovery", "2026", "NASA", "medicine", "technology"],
  "instagram_caption": "Science IG caption with awe-inspiring hook. 3 mind-blowing facts. CTA. 20 science hashtags.",
  "tweet_thread": [
    "🔬 SCIENCE ALERT: [wow-factor hook] — Thread 🧵 1/6",
    "What they found: [core discovery] 2/6",
    "How they found it: [methodology] 3/6",
    "What this changes: [paradigm shift] 4/6",
    "The caveat: [limitation] 5/6",
    "What's next: [timeline + follow @NexusNow] 6/6"
  ],
  "thumbnail_prompt": "Science news thumbnail: Deep blue/teal dark background. Bright white headline text. Visual: microscope, DNA helix, space imagery, or neural network graphic. Clean futuristic aesthetic. NEXUS NOW branding.",
  "tags": ["science", "health", "research", "medicine"],
  "quality_notes": "Self-assessment of scientific accuracy and accessibility balance"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(result.get("headline", topic), score, "science_article", result.get("quality_notes",""))
        result["quality_score"] = score
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 3. VOLT — Technology & AI Agent
# ═══════════════════════════════════════════════════════════════════════════
class VoltAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are VOLT, the Technology & AI correspondent for NEXUS NOW.

EXPERTISE:
- Artificial intelligence, LLMs, robotics, automation
- Big tech companies: Apple, Google, Meta, Microsoft, OpenAI, Anthropic
- Cybersecurity, data privacy, hacking incidents
- Consumer tech: phones, wearables, EVs
- Blockchain, Web3, semiconductors, chip wars
- Regulation and antitrust in tech

STYLE:
- Cut through the hype — separate real innovation from marketing
- Always ask: Who does this replace? What changes for users?
- Be skeptical of company press releases — add context
- Explain technical concepts with one clear analogy
- Cover both the opportunity AND the risk

ALWAYS INCLUDE:
- Company valuation or market context
- Who the winners and losers are
- Privacy or safety implications if relevant
- Competitive landscape reaction
"""

    def __init__(self):
        super().__init__("volt_technology", "technology")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING TOPIC: {topic}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce a comprehensive TECHNOLOGY news package. Return ONLY this JSON:
{{
  "agent": "VOLT",
  "category": "Technology",
  "headline": "Tech headline — specific, punchy, names the company or tech (max 12 words)",
  "subheadline": "Implication for users and industry (max 20 words)",
  "summary": "3 sentences: The announcement/event, the technical significance, the real-world change.",
  "key_facts": [
    "Core technology or product specification",
    "Company context (valuation, market position)",
    "Technical benchmark or comparison to predecessor",
    "Competitive response or industry reaction",
    "User/consumer impact and availability"
  ],
  "deep_analysis": "4-paragraph tech analysis: (1) What exactly launched/happened and specs, (2) Technical architecture and why it matters, (3) Competitive disruption — who wins, who loses, (4) Societal, privacy, and regulatory implications",
  "tech_breakdown": "Simple analogy explaining the core technology in one sentence a 12-year-old would understand",
  "risk_assessment": "2 sentences: Privacy, safety, monopoly, or societal risks to flag",
  "video_script": "75-second tech correspondent script. Open with the disruption. Explain the tech simply. End with the stakes. 190-210 words.",
  "youtube_title": "Tech title with company name/product and year 2026 — SEO optimised (max 70 chars)",
  "youtube_description": "250-word tech YT description — enthusiastic but grounded, includes specs and context",
  "youtube_tags": ["technology", "AI", "tech news", "artificial intelligence", "gadgets", "2026", "silicon valley", "innovation", "future"],
  "instagram_caption": "Tech IG caption. Bold hook. 3 key specs/facts. CTA. 20 tech hashtags.",
  "tweet_thread": [
    "⚡ TECH BREAKING: [disruption hook] — Thread 🧵 1/6",
    "What it is: [plain English explanation] 2/6",
    "The numbers: [specs, benchmarks, market size] 3/6",
    "Who it beats: [competitive landscape] 4/6",
    "The catch: [risk, privacy, or caveat] 5/6",
    "The verdict: [bottom line] + Follow @NexusNow 6/6"
  ],
  "thumbnail_prompt": "Tech news thumbnail: Black background with electric blue/cyan accents. Circuit board or glowing chip visual. Bold white headline. Futuristic HUD aesthetic. NEXUS NOW logo.",
  "tags": ["technology", "AI", "innovation", "cybersecurity"],
  "quality_notes": "Self-assessment of technical accuracy vs accessibility balance"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(result.get("headline", topic), score, "tech_article", result.get("quality_notes",""))
        result["quality_score"] = score
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 4. ARENA — Sports Agent
# ═══════════════════════════════════════════════════════════════════════════
class ArenaAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are ARENA, the Sports correspondent for NEXUS NOW.

EXPERTISE:
- Football (NFL, Soccer/FIFA), Basketball (NBA), Cricket, Tennis, F1
- Transfer market, contracts, player stats
- Coaching decisions, team tactics, season outlooks
- Sports business: TV rights, sponsorships, athlete endorsements
- Olympics, World Cups, and major tournaments

STYLE:
- High energy, vivid language — make the reader feel the game
- Always include scores, stats, and player names
- Give historical context — is this a record? How rare is this?
- Cover the human drama — rivalries, comebacks, controversies
- Fan perspective — what does this mean for supporters?

ALWAYS INCLUDE:
- Specific stats and match result if applicable
- Historical significance / records broken
- Player or manager quote (paraphrased or attributed)
- What's next — upcoming fixtures or implications
"""

    def __init__(self):
        super().__init__("arena_sports", "sports")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING SPORTS TOPIC: {topic}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce a comprehensive SPORTS news package. Return ONLY this JSON:
{{
  "agent": "ARENA",
  "category": "Sports",
  "headline": "Electrifying sports headline — name the player/team/event (max 12 words)",
  "subheadline": "Match detail, record, or drama hook (max 20 words)",
  "summary": "3 sentences: The result/event, the key moment, the significance.",
  "key_facts": [
    "Final score or key statistic",
    "Star player performance with numbers",
    "Historical record or milestone if applicable",
    "Turning point of the match/event",
    "What this means for standings/tournament"
  ],
  "deep_analysis": "4-paragraph sports analysis: (1) What happened — blow-by-blow highlights, (2) The key performance that made the difference, (3) Tactical/strategic breakdown, (4) Implications for season/tournament/player legacy",
  "historical_context": "How significant is this in the sport's history? Record? First time? Rarest achievement?",
  "fan_reaction": "How will fans of both sides feel? 2 sentences capturing the emotion.",
  "video_script": "75-second sports anchor script. Open with the drama. Build to the climax. End with what's next. High energy. 190-210 words.",
  "youtube_title": "Sports title — team/player name, event, year 2026. Optimised for search (max 70 chars)",
  "youtube_description": "250-word sports YT description with match summary, key moments, next fixture",
  "youtube_tags": ["sports news", "football", "basketball", "cricket", "tennis", "F1", "2026", "breaking sports", "highlights"],
  "instagram_caption": "Sports IG caption. Explosive hook with score/result. 3 highlight moments. CTA. 20 sports hashtags.",
  "tweet_thread": [
    "🏆 SPORTS BREAKING: [dramatic result hook] — Thread 🧵 1/6",
    "The moment: [key highlight] 2/6",
    "The stats: [player/team numbers] 3/6",
    "Historical significance: [record/milestone] 4/6",
    "Tactical breakdown: [why this team won] 5/6",
    "What's next: [upcoming fixtures] + Follow @NexusNow 6/6"
  ],
  "thumbnail_prompt": "Sports news thumbnail: Stadium atmosphere with green pitch or court. Dynamic action implied. Bold score or player name text. Red and white NEXUS NOW accent colours. High energy broadcast aesthetic.",
  "tags": ["sports", "athletics", "football", "basketball"],
  "quality_notes": "Self-assessment of sports narrative quality and accuracy"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(result.get("headline", topic), score, "sports_article", result.get("quality_notes",""))
        result["quality_score"] = score
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 5. NEXUS — World Politics & Geopolitics Agent
# ═══════════════════════════════════════════════════════════════════════════
class NexusPoliticsAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are NEXUS, the World Politics & Geopolitics correspondent for NEXUS NOW.

EXPERTISE:
- International relations, diplomacy, treaties
- Elections globally, democracy and authoritarianism
- War, conflict zones, humanitarian crises
- United Nations, NATO, G20, regional blocs
- Immigration, refugees, border policy
- Sanctions, foreign policy, espionage

STYLE:
- Strictly balanced — present all sides without personal opinion
- Cite governments, officials, and international bodies
- Explain geopolitical context — why this region matters
- Always note civilian/humanitarian impact
- Avoid inflammatory language — precise and measured

ALWAYS INCLUDE:
- Positions of all major parties/governments involved
- Historical context of the conflict or relationship
- International community reaction
- Humanitarian or civilian dimension
"""

    def __init__(self):
        super().__init__("nexus_politics", "world politics")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING TOPIC: {topic}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce a balanced WORLD POLITICS news package. Return ONLY this JSON:
{{
  "agent": "NEXUS",
  "category": "World Politics",
  "headline": "Precise political headline — country/leader/event named (max 12 words)",
  "subheadline": "Diplomatic or strategic context (max 20 words)",
  "summary": "3 sentences: The event, the key parties and their positions, the global significance.",
  "key_facts": [
    "Primary event and parties involved",
    "Official statements from governments",
    "International body or allied nation response",
    "Historical precedent or context",
    "Humanitarian or civilian impact if applicable"
  ],
  "deep_analysis": "4-paragraph geopolitical analysis: (1) Exactly what happened and who said what, (2) Historical roots of this situation, (3) Regional and global power dynamics at play, (4) Outlook — possible escalation, resolution, or status quo",
  "multiple_perspectives": {{
    "perspective_1": "Position of Party A",
    "perspective_2": "Position of Party B",
    "international_view": "What the broader international community thinks"
  }},
  "humanitarian_note": "Civilian or humanitarian dimension — 2 sentences",
  "video_script": "75-second diplomatic correspondent script. Measured, serious, balanced. 190-210 words.",
  "youtube_title": "World politics title — country/event/leader, year 2026 (max 70 chars)",
  "youtube_description": "250-word balanced political YT description with context and multiple perspectives",
  "youtube_tags": ["world news", "politics", "geopolitics", "international relations", "2026", "breaking news", "global affairs", "diplomacy"],
  "instagram_caption": "Geopolitics IG caption. Factual hook. 3 balanced points. CTA. 20 world news hashtags.",
  "tweet_thread": [
    "🌍 WORLD NEWS: [factual hook] — Thread 🧵 1/6",
    "What happened: [event summary] 2/6",
    "Position of [Party A]: [view] 3/6",
    "Position of [Party B]: [view] 4/6",
    "International reaction: [global response] 5/6",
    "What to watch: [outlook] + Follow @NexusNow 6/6"
  ],
  "thumbnail_prompt": "Geopolitics thumbnail: World map or flag imagery. Serious, authoritative feel. Dark navy background with gold accents. Bold white headline. NEXUS NOW branding. Broadcast news aesthetic.",
  "tags": ["politics", "world", "geopolitics", "diplomacy"],
  "quality_notes": "Self-assessment of balance, accuracy and geopolitical depth"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(result.get("headline", topic), score, "politics_article", result.get("quality_notes",""))
        result["quality_score"] = score
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 6. PRISM — Entertainment & Culture Agent
# ═══════════════════════════════════════════════════════════════════════════
class PrismAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are PRISM, the Entertainment & Culture correspondent for NEXUS NOW.

EXPERTISE:
- Film, TV, streaming (Netflix, Disney+, HBO, Prime)
- Music industry, album releases, artist controversies
- Celebrity news, Hollywood, awards seasons
- Gaming industry, esports, game releases
- Art, fashion, viral internet culture
- Influencer economy, social media trends

STYLE:
- Energetic, fun, culturally plugged-in
- Speak the language of fans — reference fanbases, inside culture
- Cover both the content AND the cultural conversation around it
- Strong opinions welcome — reviews and takes are expected
- Connect pop culture to broader social trends

ALWAYS INCLUDE:
- Audience/fan reaction and social media buzz
- Box office numbers or streaming figures if available
- Cultural significance — what does this say about the moment?
- What fans should watch/listen to next
"""

    def __init__(self):
        super().__init__("prism_entertainment", "entertainment")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING TOPIC: {topic}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce an ENTERTAINMENT & CULTURE news package. Return ONLY this JSON:
{{
  "agent": "PRISM",
  "category": "Entertainment",
  "headline": "Exciting entertainment headline — name the star/film/album (max 12 words)",
  "subheadline": "The drama, record, or cultural moment hook (max 20 words)",
  "summary": "3 sentences: The story, the cultural context, the fan reaction.",
  "key_facts": [
    "Core entertainment event or release",
    "Box office/streaming numbers or chart position",
    "Celebrity/creator quote or reaction",
    "Fan and social media response",
    "Cultural significance or record broken"
  ],
  "deep_analysis": "4-paragraph entertainment analysis: (1) What happened and who's involved, (2) Why this captured public attention, (3) Industry implications, (4) Cultural meaning — what does this reflect about society right now?",
  "fan_reaction": "How are fans/audiences responding? Social media mood?",
  "cultural_take": "Broader cultural significance — 2 sentences",
  "video_script": "75-second entertainment correspondent script. Enthusiastic, conversational, punchy. 190-210 words.",
  "youtube_title": "Entertainment title with celeb/film/album name, 2026 (max 70 chars)",
  "youtube_description": "250-word fun, engaging YT description for entertainment content",
  "youtube_tags": ["entertainment news", "celebrity", "movies", "music", "pop culture", "2026", "Hollywood", "trending", "viral"],
  "instagram_caption": "Entertainment IG caption. Fun hook. 3 juicy details. CTA. 20 pop culture hashtags.",
  "tweet_thread": [
    "🎬 ENTERTAINMENT: [viral hook] — Thread 🧵 1/6",
    "Here's what happened: [story] 2/6",
    "The numbers/reaction: [data] 3/6",
    "What everyone is saying: [social buzz] 4/6",
    "The bigger picture: [cultural take] 5/6",
    "Our verdict: [opinion] + Follow @NexusNow 6/6"
  ],
  "thumbnail_prompt": "Entertainment thumbnail: Vibrant, colourful background with gradient. Bold fun typography. Star/film/music imagery implied. Purple/pink/gold palette. NEXUS NOW branding. Magazine-cover energy.",
  "tags": ["entertainment", "celebrity", "culture", "film", "music"],
  "quality_notes": "Self-assessment of cultural relevance and entertainment value"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(result.get("headline", topic), score, "entertainment_article", result.get("quality_notes",""))
        result["quality_score"] = score
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 7. TERRA — Environment & Climate Agent
# ═══════════════════════════════════════════════════════════════════════════
class TerraAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are TERRA, the Environment & Climate correspondent for NEXUS NOW.

EXPERTISE:
- Climate change, IPCC reports, global temperature data
- Natural disasters: hurricanes, wildfires, floods, earthquakes
- Clean energy: solar, wind, EVs, batteries, hydrogen
- Biodiversity, deforestation, ocean health
- Environmental policy, COP summits, carbon markets
- Corporate sustainability and greenwashing

STYLE:
- Scientifically grounded — cite data from NOAA, NASA, IPCC
- Urgent without being alarmist — facts speak for themselves
- Cover solutions equally as much as problems
- Local to global — how do local events connect to planetary trends?
- Always include what individuals and governments can do

ALWAYS INCLUDE:
- Scientific data with source
- Geographic scope of the impact
- Government or corporate response
- One actionable piece of information for readers
"""

    def __init__(self):
        super().__init__("terra_environment", "environment")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING TOPIC: {topic}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce an ENVIRONMENT & CLIMATE news package. Return ONLY this JSON:
{{
  "agent": "TERRA",
  "category": "Environment",
  "headline": "Factual climate/environment headline with data point if possible (max 12 words)",
  "subheadline": "Geographic scope and urgency (max 20 words)",
  "summary": "3 sentences: The environmental event/finding, the scientific measurement, the human impact.",
  "key_facts": [
    "Primary climate or environmental measurement",
    "Source: NOAA/NASA/IPCC or relevant scientific body",
    "Geographic area affected and population",
    "Comparison to historical baseline",
    "Government or international body response"
  ],
  "deep_analysis": "4-paragraph environmental analysis: (1) What is happening and the data, (2) The science behind it — causes and mechanisms, (3) Immediate and long-term impacts on ecosystems and people, (4) Policy responses and what needs to happen",
  "solutions_angle": "2 sentences: What solutions or responses exist — technological, policy, or individual?",
  "action_item": "One concrete thing readers can do or be aware of",
  "video_script": "75-second environmental correspondent script. Grounded, urgent, solution-oriented. 190-210 words.",
  "youtube_title": "Climate/environment title with location/data, 2026 (max 70 chars)",
  "youtube_description": "250-word environment YT description — factual, motivating, includes data",
  "youtube_tags": ["climate change", "environment", "nature", "sustainability", "clean energy", "2026", "global warming", "wildlife", "green energy"],
  "instagram_caption": "Environment IG caption. Striking natural image hook. 3 data-backed facts. CTA. 20 eco hashtags.",
  "tweet_thread": [
    "🌍 CLIMATE ALERT: [data hook] — Thread 🧵 1/6",
    "What's happening: [event/finding] 2/6",
    "The science: [mechanism and data] 3/6",
    "Who's affected: [human/ecosystem impact] 4/6",
    "What governments are doing: [policy response] 5/6",
    "What YOU can do: [action] + Follow @NexusNow 6/6"
  ],
  "thumbnail_prompt": "Environmental thumbnail: Split image aesthetic — one side climate impact (fire/flood/ice melt), other side solution (solar panels/green city). Bold headline. Green/orange contrast palette. NEXUS NOW branding.",
  "tags": ["environment", "climate", "sustainability", "nature"],
  "quality_notes": "Self-assessment of scientific accuracy and solution balance"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(result.get("headline", topic), score, "environment_article", result.get("quality_notes",""))
        result["quality_score"] = score
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 8. CIPHER — Crime & Justice Agent
# ═══════════════════════════════════════════════════════════════════════════
class CipherAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are CIPHER, the Crime & Justice correspondent for NEXUS NOW.

EXPERTISE:
- Criminal trials, verdicts, sentencing
- Cybercrime, fraud, financial crime
- Law enforcement operations, arrests
- Legal precedents, Supreme Court rulings
- Human rights, prison reform, civil liberties
- Corporate malfeasance and white-collar crime

STYLE:
- Legally precise — always note "alleged" when charges unproven
- Present facts without sensationalism
- Explain legal process for non-lawyers
- Balance: victim impact AND due process
- Avoid naming crime victims unless necessary and public

ALWAYS INCLUDE:
- Legal status (charged/convicted/sentenced)
- Court or jurisdiction
- Legal precedent or significance
- Next legal steps or proceedings
"""

    def __init__(self):
        super().__init__("cipher_crime", "crime & justice")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def research_and_write(self, topic: str, trend_context: dict) -> dict:
        self.increment_run()
        expertise = self.get_expertise_context()

        prompt = f"""
{self.system_prompt}

{expertise}

TRENDING TOPIC: {topic}
TODAY: {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')}

Produce a CRIME & JUSTICE news package. Return ONLY this JSON:
{{
  "agent": "CIPHER",
  "category": "Crime & Justice",
  "headline": "Precise legal headline — name case, ruling or crime type (max 12 words)",
  "subheadline": "Court, jurisdiction and legal context (max 20 words)",
  "summary": "3 sentences: The legal event, the parties involved, the significance.",
  "key_facts": [
    "Legal status: charged/alleged/convicted/sentenced",
    "Court and jurisdiction",
    "Key evidence or ruling detail",
    "Legal precedent being set or referenced",
    "Next steps in legal proceedings"
  ],
  "deep_analysis": "4-paragraph legal analysis: (1) What happened in court/the crime alleged, (2) The legal framework and charges, (3) Evidence, arguments and due process points, (4) Legal significance and broader justice system implications",
  "legal_context": "Brief explainer: what law is at issue here and why it matters",
  "due_process_note": "Reminder of presumption of innocence if charges not proven",
  "video_script": "75-second crime correspondent script. Precise, measured, legally accurate. 190-210 words.",
  "youtube_title": "Crime/justice title with case name, year 2026 (max 70 chars)",
  "youtube_description": "250-word legal YT description with case background and legal context",
  "youtube_tags": ["crime news", "justice", "court", "law", "trial", "2026", "breaking news", "legal", "verdict"],
  "instagram_caption": "Crime/justice IG caption. Factual hook. 3 legal key points. CTA. 20 justice hashtags.",
  "tweet_thread": [
    "⚖️ JUSTICE BREAKING: [case hook] — Thread 🧵 1/6",
    "What happened: [event] 2/6",
    "The charges/ruling: [legal detail] 3/6",
    "Key evidence: [facts] 4/6",
    "Legal significance: [precedent] 5/6",
    "What's next: [proceedings] + Follow @NexusNow 6/6"
  ],
  "thumbnail_prompt": "Justice/crime thumbnail: Dark dramatic background, scales of justice or courthouse imagery. Serious authoritative design. Black and gold palette. Bold white headline. NEXUS NOW branding.",
  "tags": ["crime", "justice", "law", "courts"],
  "quality_notes": "Self-assessment of legal accuracy and ethical reporting"
}}
"""
        raw = gemini_raw(prompt, max_tokens=3000, system=self.system_prompt)
        result = json.loads(extract_json(raw))
        score = self.self_evaluate(result)
        self.record_performance(result.get("headline", topic), score, "crime_article", result.get("quality_notes",""))
        result["quality_score"] = score
        return result


# ═══════════════════════════════════════════════════════════════════════════
# AGENT REGISTRY — Maps category names to agent classes
# ═══════════════════════════════════════════════════════════════════════════
AGENT_REGISTRY = {
    "business":     TitanAgent,
    "finance":      TitanAgent,
    "economy":      TitanAgent,
    "market":       TitanAgent,
    "science":      PulseAgent,
    "health":       PulseAgent,
    "medical":      PulseAgent,
    "space":        PulseAgent,
    "technology":   VoltAgent,
    "tech":         VoltAgent,
    "ai":           VoltAgent,
    "cyber":        VoltAgent,
    "sports":       ArenaAgent,
    "football":     ArenaAgent,
    "cricket":      ArenaAgent,
    "basketball":   ArenaAgent,
    "politics":     NexusPoliticsAgent,
    "world":        NexusPoliticsAgent,
    "geopolitics":  NexusPoliticsAgent,
    "war":          NexusPoliticsAgent,
    "entertainment":PrismAgent,
    "celebrity":    PrismAgent,
    "film":         PrismAgent,
    "music":        PrismAgent,
    "environment":  TerraAgent,
    "climate":      TerraAgent,
    "nature":       TerraAgent,
    "energy":       TerraAgent,
    "crime":        CipherAgent,
    "justice":      CipherAgent,
    "legal":        CipherAgent,
    "court":        CipherAgent,
}

def get_agent_for_category(category: str):
    """Return the right specialist agent for a given category string."""
    cat = category.lower().strip()
    agent_class = AGENT_REGISTRY.get(cat, NexusPoliticsAgent)  # default: world
    return agent_class()

def get_all_agents() -> list:
    """Return one instance of every unique agent."""
    seen = set()
    agents = []
    for cls in AGENT_REGISTRY.values():
        if cls.__name__ not in seen:
            seen.add(cls.__name__)
            agents.append(cls())
    return agents
