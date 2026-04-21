"""
NEXUS NOW - SCOUT Agent
Fetches Google Trends via RSS (free, no key).
Classifies into categories, routes to specialist agents.
Falls back to curated topics if trends unavailable.
"""
import json, datetime, re, requests
from agents.base_agent import NexusAgent, gemini_raw
from agents.ai_client  import extract_json


class ScoutAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are SCOUT for NEXUS NOW global news. "
        "Select the most newsworthy topics from trending searches. "
        "Always return valid JSON only."
    )

    CAT_MAP = {
        "technology":"VOLT",  "tech":"VOLT",    "ai":"VOLT",      "cyber":"VOLT",
        "business":"TITAN",   "finance":"TITAN", "economy":"TITAN","market":"TITAN",
        "science":"PULSE",    "health":"PULSE",  "medical":"PULSE","space":"PULSE",
        "sports":"ARENA",     "football":"ARENA","cricket":"ARENA","basketball":"ARENA",
        "politics":"NEXUS",   "world":"NEXUS",   "war":"NEXUS",    "election":"NEXUS",
        "entertainment":"PRISM","celebrity":"PRISM","music":"PRISM","film":"PRISM",
        "environment":"TERRA","climate":"TERRA", "nature":"TERRA", "energy":"TERRA",
        "crime":"CIPHER",     "justice":"CIPHER","court":"CIPHER", "legal":"CIPHER",
    }

    FALLBACKS = [
        ("artificial intelligence new developments", "technology",    "VOLT"),
        ("global stock markets economy update",      "business",      "TITAN"),
        ("medical science breakthrough research",    "science",       "PULSE"),
        ("champions league premier league football", "sports",        "ARENA"),
        ("world politics international diplomacy",   "politics",      "NEXUS"),
        ("climate change environment disaster",      "environment",   "TERRA"),
        ("celebrity entertainment viral news",       "entertainment", "PRISM"),
        ("crime court justice verdict",              "crime",         "CIPHER"),
    ]

    def __init__(self):
        super().__init__("scout_master", "trend_detection")

    def fetch_trends(self) -> list:
        topics = []
        for geo in ["US", "IN", "GB"]:
            try:
                r = requests.get(
                    f"https://trends.google.com/trends/trendingsearches"
                    f"/daily/rss?geo={geo}",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15)
                if r.status_code != 200:
                    continue
                for m in re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", r.text):
                    m = m.strip()
                    if m and m not in topics and len(m) > 3:
                        topics.append(m)
                if not topics:
                    for m in re.findall(r"<title>(.+?)</title>", r.text):
                        if m and "Google" not in m and m not in topics:
                            topics.append(m.strip())
            except Exception:
                pass
        self.log(f"Fetched {len(topics)} trends from Google")
        return topics

    def classify(self, topics: list, n: int) -> list:
        if not topics:
            topics = [f[0] for f in self.FALLBACKS]

        prompt = (
            f"Date: {datetime.datetime.utcnow().strftime('%B %d, %Y')}\n"
            f"Pick the TOP {n} most newsworthy global topics.\n"
            f"Topics: {json.dumps(topics[:20])}\n\n"
            f"category must be one of: technology, business, science, "
            f"sports, politics, entertainment, environment, crime\n\n"
            f"Return ONLY JSON array:\n"
            f'[{{"topic":"topic text","category":"technology",'
            f'"angle":"the news angle to pursue"}}]'
        )
        try:
            self.increment_run()
            data = json.loads(extract_json(gemini_raw(prompt, max_tokens=400)))
            if not isinstance(data, list):
                raise ValueError("not a list")
            results = []
            for item in data[:n]:
                cat   = str(item.get("category","politics")).lower().strip()
                results.append({
                    "topic":    item.get("topic", topics[0]),
                    "category": cat,
                    "agent":    self.CAT_MAP.get(cat, "NEXUS"),
                    "angle":    item.get("angle", "Latest developments"),
                })
            while len(results) < n:
                fb = self.FALLBACKS[len(results) % len(self.FALLBACKS)]
                results.append({"topic":fb[0],"category":fb[1],"agent":fb[2],"angle":"Latest news"})
            self.log(f"Selected: {[r['topic'][:35] for r in results]}")
            return results[:n]
        except Exception as e:
            self.log(f"Classify failed ({e}), using fallbacks")
            return [{"topic":f[0],"category":f[1],"agent":f[2],"angle":"Latest news"}
                    for f in self.FALLBACKS[:n]]

    def run(self, n: int = 2) -> list:
        return self.classify(self.fetch_trends(), n)
