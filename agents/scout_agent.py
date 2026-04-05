"""
NEXUS NOW — SCOUT Agent
Fetches Google Trends, classifies, scores, routes to specialist.
"""
import json
import datetime
import requests
from agents.base_agent import NexusAgent, gemini_raw
from agents.ai_client import extract_json


class ScoutAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are SCOUT for NEXUS NOW. Classify news topics by category. "
        "Always return valid JSON arrays only. Be concise and accurate."
    )

    FALLBACK_TOPICS = [
        ("artificial intelligence breakthroughs 2026", "technology",    "VOLT"),
        ("global economy markets outlook",              "business",      "TITAN"),
        ("climate change extreme weather events",       "environment",   "TERRA"),
        ("world politics international relations",      "politics",      "NEXUS"),
        ("science health medical research news",        "science",       "PULSE"),
        ("sports champions league results",             "sports",        "ARENA"),
        ("entertainment celebrity viral moments",       "entertainment", "PRISM"),
        ("crime justice court verdicts",                "crime",         "CIPHER"),
    ]

    CATEGORY_MAP = {
        "technology": "VOLT",    "tech": "VOLT",      "ai": "VOLT",
        "business":   "TITAN",   "finance": "TITAN",  "economy": "TITAN",
        "science":    "PULSE",   "health": "PULSE",   "medical": "PULSE",
        "sports":     "ARENA",   "football": "ARENA", "cricket": "ARENA",
        "politics":   "NEXUS",   "world": "NEXUS",    "geopolitics": "NEXUS",
        "entertainment": "PRISM","celebrity": "PRISM","music": "PRISM",
        "environment": "TERRA",  "climate": "TERRA",  "nature": "TERRA",
        "crime":      "CIPHER",  "justice": "CIPHER", "court": "CIPHER",
    }

    def __init__(self):
        super().__init__("scout_master", "trend_detection")

    def fetch_trends(self, geo: str = "US") -> list[str]:
        """Fetch Google Trends RSS. Returns list of topic strings."""
        topics = []
        urls = [
            f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN",
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; NexusNow/1.0)"
                })
                if r.status_code != 200:
                    continue
                # Parse RSS without feedparser (avoid dependency issues)
                import re
                # Match CDATA titles
                matches = re.findall(
                    r"<title><!\[CDATA\[(.+?)\]\]></title>", r.text
                )
                if not matches:
                    # Try plain title tags
                    matches = re.findall(r"<title>(.+?)</title>", r.text)
                    matches = [m for m in matches
                               if m and "Google" not in m and "Trends" not in m]
                for t in matches[:12]:
                    t = t.strip()
                    if t and t not in topics and len(t) > 3:
                        topics.append(t)
            except Exception as e:
                self.log(f"Trend fetch error ({url}): {e}")

        self.log(f"Fetched {len(topics)} raw trends")
        return topics

    def classify(self, topics: list[str], n: int = 2) -> list[dict]:
        """Classify topics and select top N. Always returns exactly n items."""
        if not topics:
            topics = [t[0] for t in self.FALLBACK_TOPICS[:n*2]]

        prompt = (
            f"Today: {datetime.datetime.utcnow().strftime('%B %d, %Y')}.\n"
            f"Select the TOP {n} most newsworthy topics from this list "
            f"for a global news channel.\n\n"
            f"Topics: {json.dumps(topics[:20])}\n\n"
            f"Rules:\n"
            f"- Pick exactly {n} different topics\n"
            f"- Cover different categories if possible\n"
            f"- category must be ONE of: technology, business, science, "
            f"sports, politics, entertainment, environment, crime\n\n"
            f"Return ONLY a JSON array:\n"
            f'[{{"topic":"exact topic text","category":"technology",'
            f'"angle":"specific news angle","why":"why this is trending now"}}]'
        )
        try:
            self.increment_run()
            raw  = gemini_raw(prompt, max_tokens=500)
            data = json.loads(extract_json(raw))
            if not isinstance(data, list) or not data:
                raise ValueError("Empty result")

            results = []
            for item in data[:n]:
                cat   = item.get("category", "politics").lower().strip()
                agent = self.CATEGORY_MAP.get(cat, "NEXUS")
                results.append({
                    "topic":  item.get("topic", topics[0]),
                    "category": cat,
                    "agent":  agent,
                    "angle":  item.get("angle", "Latest developments"),
                    "why":    item.get("why", "Currently trending"),
                })

            # Pad to n if needed
            fallback_idx = 0
            while len(results) < n:
                ft = self.FALLBACK_TOPICS[fallback_idx % len(self.FALLBACK_TOPICS)]
                results.append({
                    "topic": ft[0], "category": ft[1], "agent": ft[2],
                    "angle": "Latest developments", "why": "Global interest"
                })
                fallback_idx += 1

            self.log(f"Selected: {[r['topic'][:40] for r in results]}")
            return results[:n]

        except Exception as e:
            self.log(f"Classification failed ({e}) — using fallbacks")
            out = []
            for i in range(n):
                ft = self.FALLBACK_TOPICS[i % len(self.FALLBACK_TOPICS)]
                out.append({
                    "topic": ft[0], "category": ft[1], "agent": ft[2],
                    "angle": "Latest developments", "why": "Global interest"
                })
            return out

    def run(self, n: int = 2) -> list[dict]:
        """Full scout run. Always returns n topics."""
        topics = self.fetch_trends()
        return self.classify(topics, n)
