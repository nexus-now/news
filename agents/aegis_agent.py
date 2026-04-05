"""
NEXUS NOW — AEGIS Agent
Fact-checks every story. Issues copyright ID. Stamps all content.
"""
import json
import hashlib
import datetime
from agents.base_agent import NexusAgent
from agents.ai_client  import ai_text, extract_json

CATEGORY_CODES = {
    "business": "BIZ", "finance": "BIZ", "economy": "BIZ",
    "science":  "SCI", "health":  "SCI", "medical": "SCI",
    "technology":"TEC", "tech":   "TEC", "ai":      "TEC",
    "sports":   "SPT", "football":"SPT", "cricket": "SPT",
    "politics": "POL", "world":   "POL", "geopolitics":"POL",
    "entertainment":"ENT","celebrity":"ENT","music":  "ENT",
    "environment":"ENV","climate": "ENV", "nature":  "ENV",
    "crime":    "CRM", "justice": "CRM", "legal":   "CRM",
}


class AegisAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are AEGIS, the Verification and Copyright agent for NEXUS NOW. "
        "Fact-check rigorously. Flag misinformation. Protect intellectual property. "
        "Always return valid JSON only."
    )

    def __init__(self):
        super().__init__("aegis_verification", "verification")

    def _make_copyright_id(self, content: dict) -> str:
        now   = datetime.datetime.utcnow()
        cat   = content.get("category", "general").lower().split()[0]
        code  = CATEGORY_CODES.get(cat, "GEN")
        ts    = now.strftime("%Y-%m%d-%H%M%S")
        h     = hashlib.md5(
            content.get("headline", "").encode()
        ).hexdigest()[:6].upper()
        return f"NN-{ts}-{code}-{h}"

    def fact_check(self, content: dict) -> dict:
        """Verify the story. Returns verification dict."""
        headline  = content.get("headline", "")
        summary   = content.get("summary", "")
        key_facts = content.get("key_facts", [])
        prompt = (
            f"Fact-check this news story for NEXUS NOW.\n"
            f"Headline: {headline}\n"
            f"Summary: {summary[:300]}\n"
            f"Key facts: {json.dumps(key_facts[:3])}\n\n"
            f"Assess: Is this plausible and safe to publish?\n"
            f"Return ONLY JSON:\n"
            f'{{"status":"VERIFIED","badge":"✅ VERIFIED",'
            f'"confidence":8.5,"safe_to_publish":true,'
            f'"caveat":"Any important caveat or empty string"}}'
        )
        try:
            raw  = ai_text(prompt, max_tokens=200)
            data = json.loads(extract_json(raw))
            return {
                "status":          data.get("status", "UNVERIFIED"),
                "badge":           data.get("badge", "🔍 UNVERIFIED"),
                "confidence":      float(data.get("confidence", 5.0)),
                "safe_to_publish": bool(data.get("safe_to_publish", True)),
                "caveat":          data.get("caveat", ""),
            }
        except Exception:
            return {
                "status": "UNVERIFIED", "badge": "🔍 UNVERIFIED",
                "confidence": 5.0, "safe_to_publish": True, "caveat": ""
            }

    def stamp(self, content: dict) -> dict:
        """
        Full AEGIS processing:
        1. Fact-check
        2. Generate copyright ID
        3. Stamp ID into all content fields
        """
        self.increment_run()
        verification  = self.fact_check(content)
        copyright_id  = self._make_copyright_id(content)
        badge         = verification["badge"]
        year          = datetime.datetime.utcnow().year
        notice        = f"© {year} NEXUS NOW · {copyright_id} · All Rights Reserved"

        # Stamp into each platform's content
        script = content.get("video_script", "")
        if script:
            content["video_script"] = (
                script + f"\n\n[{badge} | © {year} NEXUS NOW | ID: {copyright_id}]"
            )

        yt_desc = content.get("youtube_description", "")
        content["youtube_description"] = (
            yt_desc
            + f"\n\n{'─'*40}\n"
            f"© {year} NEXUS NOW — All Rights Reserved\n"
            f"Content ID: {copyright_id} | {badge}\n"
            f"AI-generated editorial content. Reproduction prohibited."
            + (f"\nNote: {verification['caveat']}" if verification.get("caveat") else "")
        )

        ig = content.get("instagram_caption", "")
        content["instagram_caption"] = ig + f"\n\n{badge} · © NEXUS NOW · {copyright_id}"

        tweets = content.get("tweet_thread", [])
        if tweets:
            tweets[-1] = tweets[-1].rstrip() + f" | {badge} #NexusNow"
            content["tweet_thread"] = tweets

        # Attach metadata
        content["copyright_id"]        = copyright_id
        content["copyright_notice"]     = notice
        content["verification_status"]  = verification["status"]
        content["verification_badge"]   = badge
        content["verification_confidence"] = verification["confidence"]
        content["safe_to_publish"]      = verification["safe_to_publish"]

        self.log(f"{badge} | ID: {copyright_id} | Safe: {verification['safe_to_publish']}")
        return content
