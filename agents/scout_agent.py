"""
NEXUS NOW — SCOUT Agent
Monitors Google Trends, classifies trends, routes to specialists.
"""
import json, datetime, requests
from agents.base_agent import NexusAgent, gemini_raw, extract_json

try:
    import feedparser
except ImportError:
    feedparser = None


class ScoutAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = """You are SCOUT, the Trend Intelligence Agent for NEXUS NOW.
Evaluate trending topics for news value. Classify into exactly one category:
business, science, technology, sports, politics, entertainment, environment, crime.
Score each topic 1-10. Select the top N with most content potential.
Always return valid JSON only."""

    def __init__(self):
        super().__init__("scout_master", "trend_detection")

    def fetch_trends(self, geo: str = "US") -> list:
        """Fetch Google Trends via RSS — free, no key needed."""
        self.log("Fetching Google Trends RSS...")
        topics = []
        urls = [
            f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB",
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN",
        ]
        if feedparser:
            for url in urls:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:15]:
                        title = entry.get("title", "").strip()
                        if title and title not in topics:
                            topics.append(title)
                except Exception as e:
                    self.log(f"Feed error: {e}")
        else:
            # Fallback: scrape via requests
            for url in urls[:1]:
                try:
                    r = requests.get(url, timeout=15,
                                     headers={"User-Agent": "Mozilla/5.0"})
                    import re
                    found = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", r.text)
                    topics.extend([t for t in found if t not in topics][:15])
                except Exception as e:
                    self.log(f"RSS fallback error: {e}")

        # Always add some evergreen topics if trends fail
        if len(topics) < 4:
            self.log("Using fallback topics")
            topics = [
                "artificial intelligence latest developments",
                "global economy markets update",
                "climate change news",
                "technology innovation 2026",
                "world politics breaking news",
                "science discovery research",
            ]

        self.log(f"Fetched {len(topics)} raw trends")
        return topics

    def classify_and_score(self, topics: list, n: int = 2) -> list:
        """Ask AI to classify and score each trend."""
        prompt = f"""You are SCOUT for NEXUS NOW news channel. Today: {datetime.datetime.utcnow().strftime('%B %d, %Y')}.

Classify and score these {len(topics)} trending topics. Select TOP {n}.

Topics: {json.dumps(topics[:20])}

Return ONLY a JSON array of exactly {n} items:
[
  {{
    "topic": "exact topic string from list",
    "category": "one of: business/science/technology/sports/politics/entertainment/environment/crime",
    "agent": "one of: TITAN/PULSE/VOLT/ARENA/NEXUS/PRISM/TERRA/CIPHER",
    "score": 8.5,
    "content_angle": "specific news angle to pursue",
    "why_trending": "brief reason this is trending now"
  }}
]

Rules: Select exactly {n} topics. Cover DIFFERENT categories if possible."""
        try:
            self.increment_run()
            raw      = gemini_raw(prompt, max_tokens=600)
            selected = json.loads(extract_json(raw))
            if not isinstance(selected, list):
                raise ValueError("Not a list")
            # Ensure we have exactly n items
            if len(selected) < n:
                # Pad with fallbacks
                cats = ["technology", "politics", "business", "science"]
                agents_map = {"technology":"VOLT","politics":"NEXUS",
                              "business":"TITAN","science":"PULSE"}
                for i in range(n - len(selected)):
                    cat = cats[i % len(cats)]
                    selected.append({
                        "topic": topics[len(selected) % len(topics)],
                        "category": cat,
                        "agent": agents_map.get(cat, "NEXUS"),
                        "score": 5.0,
                        "content_angle": "Latest developments",
                        "why_trending": "Currently trending"
                    })
            self.log(f"Selected: {[t['topic'][:40] for t in selected[:n]]}")
            return selected[:n]
        except Exception as e:
            self.log(f"Classification failed: {e} — using fallback")
            # Safe fallback
            fallbacks = [
                {"topic": topics[0] if topics else "AI technology news",
                 "category": "technology", "agent": "VOLT",
                 "score": 6.0, "content_angle": "Latest tech developments",
                 "why_trending": "Trending now"},
                {"topic": topics[1] if len(topics) > 1 else "global economy update",
                 "category": "business", "agent": "TITAN",
                 "score": 6.0, "content_angle": "Market impact",
                 "why_trending": "Trending now"},
            ]
            return fallbacks[:n]

    def run(self, geo: str = "US", n: int = 2) -> list:
        raw_topics = self.fetch_trends(geo)
        return self.classify_and_score(raw_topics, n)
