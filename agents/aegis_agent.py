"""
NEXUS NOW - AEGIS: Verification + Copyright Agent
Fact-checks every story. Issues unique copyright ID. Stamps all content fields.
"""
import json, hashlib, datetime
from agents.base_agent import NexusAgent
from agents.ai_client  import ai_text, extract_json

CODES = {
    "business":"BIZ","finance":"BIZ","economy":"BIZ",
    "science":"SCI","health":"SCI","medical":"SCI",
    "technology":"TEC","tech":"TEC","ai":"TEC",
    "sports":"SPT","football":"SPT","cricket":"SPT",
    "politics":"POL","world":"POL","war":"POL",
    "entertainment":"ENT","celebrity":"ENT","music":"ENT",
    "environment":"ENV","climate":"ENV","nature":"ENV",
    "crime":"CRM","justice":"CRM","legal":"CRM",
}


class AegisAgent(NexusAgent):
    BASE_SYSTEM_PROMPT = (
        "You are AEGIS, NEXUS NOW's verification agent. "
        "Fact-check rigorously. Return valid JSON only."
    )

    def __init__(self):
        super().__init__("aegis_verification", "verification")

    def _copyright_id(self, content: dict) -> str:
        cat  = content.get("category","general").lower().split()[0]
        code = CODES.get(cat, "GEN")
        ts   = datetime.datetime.utcnow().strftime("%Y-%m%d-%H%M%S")
        h    = hashlib.md5(content.get("headline","").encode()).hexdigest()[:6].upper()
        return f"NN-{ts}-{code}-{h}"

    def fact_check(self, content: dict) -> dict:
        try:
            raw = ai_text(
                f"Fact-check this news story.\n"
                f"Headline: {content.get('headline','')}\n"
                f"Summary: {content.get('summary','')[:250]}\n"
                f"Is this plausible and safe to publish?\n"
                f'Return ONLY JSON: {{"status":"VERIFIED","badge":"✅ VERIFIED",'
                f'"confidence":8.0,"safe_to_publish":true,"caveat":""}}',
                max_tokens=150)
            d = json.loads(extract_json(raw))
            return {
                "status":          d.get("status", "UNVERIFIED"),
                "badge":           d.get("badge",  "🔍 UNVERIFIED"),
                "confidence":      float(d.get("confidence", 5.0)),
                "safe_to_publish": bool(d.get("safe_to_publish", True)),
                "caveat":          d.get("caveat", ""),
            }
        except Exception:
            return {"status":"UNVERIFIED","badge":"🔍 UNVERIFIED",
                    "confidence":5.0,"safe_to_publish":True,"caveat":""}

    def stamp(self, content: dict) -> dict:
        self.increment_run()
        v   = self.fact_check(content)
        cid = self._copyright_id(content)
        yr  = datetime.datetime.utcnow().year

        # Stamp video script
        s = content.get("video_script","")
        if s:
            content["video_script"] = s + f"\n[{v['badge']} | © {yr} NEXUS NOW | {cid}]"

        # Stamp YouTube description
        yt = content.get("youtube_description","")
        content["youtube_description"] = (
            yt + f"\n\n© {yr} NEXUS NOW — All Rights Reserved\n"
            f"ID: {cid} | {v['badge']}\nAI-generated editorial content.")

        # Stamp Instagram
        ig = content.get("instagram_caption","")
        content["instagram_caption"] = ig + f"\n\n{v['badge']} · © NEXUS NOW · {cid}"

        # Stamp last tweet
        tw = content.get("tweet_thread",[])
        if tw:
            tw[-1] = tw[-1].rstrip() + f" | {v['badge']} #NexusNow"
            content["tweet_thread"] = tw

        content["copyright_id"]       = cid
        content["copyright_notice"]   = f"© {yr} NEXUS NOW · {cid} · All Rights Reserved"
        content["verification_status"]= v["status"]
        content["verification_badge"] = v["badge"]
        content["safe_to_publish"]    = v["safe_to_publish"]

        self.log(f"{v['badge']} | ID={cid}")
        return content
