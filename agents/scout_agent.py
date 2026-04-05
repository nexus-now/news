"""
NEXUS NOW — SCOUT Agent (Upgraded)
=====================================
Monitors Google Trends, classifies each trend into a category,
then routes it to the correct specialist agent.

Self-improves its scoring model based on which stories
performed best historically.
"""

import json
import datetime
import feedparser
import requests
from agents.base_agent import NexusAgent, gemini_raw, extract_json


class ScoutAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """
You are SCOUT, the Trend Intelligence Agent for NEXUS NOW.

Your job is to:
1. Evaluate trending topics for news value
2. Accurately classify each topic into the correct category
3. Identify the best content angle for that category's specialist agent
4. Score topics to select the top 2 per run

SCORING CRITERIA:
- Global significance (not just local/niche)
- Content potential (video + article + social all work?)
- Brand safety (no graphic violence, pure gossip, or misinformation)
- Audience interest across demographics
- Trending velocity (rising fast = higher score)

CATEGORIES: business, science, technology, sports, politics, entertainment, environment, crime

OUTPUT: Always structured JSON. Always route to exactly one category.
"""

    def __init__(self):
        super().__init__("scout_master", "trend_detection")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)

    def fetch_trends(self, geo: str = "US") -> list[str]:
        """Fetch from multiple Google Trends RSS feeds."""
        self.log("Fetching Google Trends RSS feeds...")
        topics = []
        feeds = [
            f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB",
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN",
        ]
        for url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:15]:
                    title = entry.get("title", "").strip()
                    if title and title not in topics:
                        topics.append(title)
            except Exception as e:
                self.log(f"Feed error ({url}): {e}")

        self.log(f"Fetched {len(topics)} raw trends")
        return topics

    def classify_and_score(self, topics: list[str], n: int = 2) -> list[dict]:
        """
        Ask Gemini to classify each trend, score it, and select the best n.
        Self-improves scoring using past performance data.
        """
        expertise = self.get_expertise_context()
        past_winners = self.memory.get("top_performing", [])[:5]

        prompt = f"""
{self.system_prompt}

{expertise}

PAST TOP-PERFORMING STORY TYPES (for calibration):
{json.dumps(past_winners)}

TODAY: {datetime.datetime.utcnow().strftime('%B %d, %Y %H:%M UTC')}

TRENDING TOPICS TO CLASSIFY AND SCORE:
{json.dumps(topics, indent=2)}

For each topic, classify and score. Then select the TOP {n} highest-scoring topics.

Return ONLY a JSON array of the top {n} selected topics:
[
  {{
    "topic": "exact topic string",
    "category": "one of: business/science/technology/sports/politics/entertainment/environment/crime",
    "agent": "one of: TITAN/PULSE/VOLT/ARENA/NEXUS/PRISM/TERRA/CIPHER",
    "score": 8.5,
    "score_reasoning": "Why this scored high",
    "content_angle": "The specific news angle to pursue",
    "why_trending": "Brief explanation of why this is trending now",
    "estimated_audience": "Who will be most interested in this story",
    "content_types": ["youtube_video", "instagram_reel", "tweet_thread", "article"]
  }}
]

Select exactly {n} topics. Ensure they cover DIFFERENT categories if possible.
"""
        try:
            self.increment_run()
            raw = gemini_raw(prompt, max_tokens=1200, system=self.system_prompt)
            selected = json.loads(extract_json(raw))
            self.log(f"Selected topics: {[t['topic'] for t in selected]}")
            return selected
        except Exception as e:
            self.log(f"Classification error: {e}")
            # Fallback: return first n topics with default category
            return [{"topic": t, "category": "politics", "agent": "NEXUS",
                     "score": 5.0, "content_angle": "Latest developments",
                     "why_trending": "Trending now", "content_types": ["article"]}
                    for t in topics[:n]]

    def run(self, geo: str = "US", n: int = 2) -> list[dict]:
        """Full scout run: fetch → classify → return top n."""
        raw_topics = self.fetch_trends(geo)
        if not raw_topics:
            self.log("No topics fetched — check network access")
            return []
        return self.classify_and_score(raw_topics, n)
