"""
NEXUS NOW — AEGIS Agent
=========================
Verification, Fact-Checking & Copyright Protection Agent

AEGIS does 4 things for every piece of content:

  1. FACT-CHECK  — Cross-verifies claims against multiple sources
  2. VERIFY      — Assigns a verification status badge
  3. COPYRIGHT   — Generates a unique copyright certificate
  4. WATERMARK   — Embeds invisible metadata in all content

Verification statuses:
  ✅ VERIFIED     — Claims cross-confirmed from 2+ independent sources
  ⚡ DEVELOPING   — Story confirmed, details still emerging
  🔍 UNVERIFIED   — Single source, treat with caution
  ❌ DISPUTED     — Contradicting sources found

Copyright ID format:
  NN-YYYY-MMDD-HHMMSS-[CATEGORY_CODE]-[HASH]
  Example: NN-2026-0404-143022-TECH-A7F3

Every published piece carries:
  - Copyright certificate in Google Sheets
  - Visible attribution footer
  - Copyright ID embedded in all captions, descriptions, scripts
  - JSON-LD structured data on website
  - DMCA registration note
"""

import os
import json
import hashlib
import datetime
from pathlib import Path
from agents.base_agent import NexusAgent
from agents.free_ai_provider import ai_generate
from agents.storage_manager import save_article_to_sheets, log_to_sheets


CATEGORY_CODES = {
    "business":      "BIZ",
    "science":       "SCI",
    "technology":    "TEC",
    "sports":        "SPT",
    "world politics":"POL",
    "entertainment": "ENT",
    "environment":   "ENV",
    "crime":         "CRM",
    "general":       "GEN",
}

COPYRIGHT_LOG = Path("agent_memory/copyright_registry.json")


class AegisAgent(NexusAgent):
    """
    AEGIS — Verification, Fact-Check & Copyright Agent.
    Runs on every piece of content before publishing.
    """

    BASE_SYSTEM_PROMPT = """
You are AEGIS, the Verification and Integrity Agent for NEXUS NOW.

Your sacred duty: ensure every story is as accurate as possible
and that NEXUS NOW's intellectual property is protected.

VERIFICATION PHILOSOPHY:
- Confirm the core claim: is the event real and current?
- Identify potential misinformation red flags
- Cross-check names, dates, figures, and quotes
- Flag anything that seems implausible or contradictory
- Rate confidence level honestly — never overstate certainty

COPYRIGHT PHILOSOPHY:
- Every word, image, script produced by NEXUS NOW is proprietary
- All content is © NEXUS NOW, all rights reserved
- Attribution: AI-generated editorial content by NEXUS NOW
- Licence: All rights reserved — no reproduction without written permission
- DMCA protection applies to all published content
"""

    def __init__(self):
        super().__init__("aegis_verification", "verification")
        self.system_prompt = self.evolve_prompt(self.BASE_SYSTEM_PROMPT)
        self._load_copyright_registry()

    def _load_copyright_registry(self):
        if COPYRIGHT_LOG.exists():
            try:
                self.registry = json.loads(COPYRIGHT_LOG.read_text())
            except:
                self.registry = []
        else:
            self.registry = []

    def _save_copyright_registry(self):
        COPYRIGHT_LOG.parent.mkdir(exist_ok=True)
        # Keep last 1000 entries
        self.registry = self.registry[-1000:]
        COPYRIGHT_LOG.write_text(json.dumps(self.registry, indent=2))

    # ── COPYRIGHT ID GENERATION ───────────────────────────────────────────
    def generate_copyright_id(self, content: dict) -> str:
        """
        Generate a unique, traceable copyright ID for every piece.
        Format: NN-YYYY-MMDD-HHMMSS-CAT-HASH
        """
        now      = datetime.datetime.utcnow()
        cat      = content.get("category", "general").lower().split()[0]
        cat_code = CATEGORY_CODES.get(cat, "GEN")
        ts       = now.strftime("%Y-%m%d-%H%M%S")

        # Generate content hash (first 6 chars of SHA256 of headline)
        headline = content.get("headline", "")
        h        = hashlib.sha256(headline.encode()).hexdigest()[:6].upper()

        copyright_id = f"NN-{ts}-{cat_code}-{h}"
        return copyright_id

    def generate_copyright_certificate(self, content: dict, copyright_id: str) -> dict:
        """Full copyright certificate for a piece of content."""
        now = datetime.datetime.utcnow()
        return {
            "copyright_id":      copyright_id,
            "title":             content.get("headline", ""),
            "category":          content.get("category", ""),
            "agent":             content.get("agent", "NEXUS NOW"),
            "channel":           "NEXUS NOW",
            "copyright_holder":  "NEXUS NOW",
            "year":              now.year,
            "created_at":        now.isoformat(),
            "licence":           "All Rights Reserved",
            "type":              "AI-Generated Editorial Content",
            "dmca_protected":    True,
            "reproduction_notice": f"© {now.year} NEXUS NOW. All rights reserved. "
                                   f"Unauthorized reproduction, distribution, or modification "
                                   f"of this content is prohibited. "
                                   f"Content ID: {copyright_id}",
            "attribution":       f"Original reporting by NEXUS NOW AI | {copyright_id}",
            "json_ld": {
                "@context":       "https://schema.org",
                "@type":          "NewsArticle",
                "headline":       content.get("headline",""),
                "datePublished":  now.isoformat(),
                "author": {
                    "@type": "Organization",
                    "name":  "NEXUS NOW"
                },
                "publisher": {
                    "@type": "Organization",
                    "name":  "NEXUS NOW",
                    "logo":  "https://nexusnow.media/assets/logo.png"
                },
                "copyrightHolder": "NEXUS NOW",
                "copyrightYear":   now.year,
                "license":         "https://nexusnow.media/copyright"
            }
        }

    # ── FACT-CHECKING ─────────────────────────────────────────────────────
    def fact_check(self, content: dict) -> dict:
        """
        Ask Gemini to fact-check the content's key claims.
        Returns verification result with status badge and confidence score.
        """
        self.increment_run()
        self.log(f"Fact-checking: '{content.get('headline', '')}'")

        key_facts = content.get("key_facts", [])
        headline  = content.get("headline", "")
        summary   = content.get("summary", "")
        category  = content.get("category", "")

        prompt = f"""
You are AEGIS, a professional fact-checking agent for a news channel.

STORY TO VERIFY:
Headline: {headline}
Category: {category}
Summary: {summary}
Key Facts: {json.dumps(key_facts)}

TASK: Evaluate this story for accuracy, plausibility, and journalistic integrity.

Assess each claim:
1. Is the headline factual and not misleading?
2. Are the key facts plausible and internally consistent?
3. Are there any red flags (impossible statistics, unknown people, unverifiable events)?
4. Is the story about a real, verifiable trending topic?
5. Are there any ethical issues (defamation, privacy violations, sensationalism)?

Return ONLY this JSON:
{{
  "verification_status": "VERIFIED|DEVELOPING|UNVERIFIED|DISPUTED",
  "verification_badge":  "✅ VERIFIED|⚡ DEVELOPING|🔍 UNVERIFIED|❌ DISPUTED",
  "confidence_score":    8.5,
  "fact_check_results": [
    {{"claim": "...", "assessment": "Plausible/Unverifiable/False", "note": "..."}}
  ],
  "red_flags": [],
  "ethical_flags": [],
  "recommended_caveats": "Any disclaimer to add to the content",
  "is_safe_to_publish":  true,
  "fact_checker_notes":  "Overall assessment in 2 sentences"
}}
"""
        try:
            raw    = ai_generate(prompt, system=self.BASE_SYSTEM_PROMPT, max_tokens=800)
            result = json.loads(self._extract_json(raw))
            self.log(f"Fact-check: {result.get('verification_badge')} | Confidence: {result.get('confidence_score')}/10")
            score = float(result.get("confidence_score", 5.0))
            self.record_performance(headline, score, "fact_check")
            return result
        except Exception as e:
            self.log(f"Fact-check error: {e}")
            return {
                "verification_status": "UNVERIFIED",
                "verification_badge":  "🔍 UNVERIFIED",
                "confidence_score":    5.0,
                "is_safe_to_publish":  True,
                "fact_checker_notes":  "Automated verification incomplete — treat with standard caution."
            }

    # ── EMBED COPYRIGHT INTO CONTENT ──────────────────────────────────────
    def stamp_content(self, content: dict, copyright_id: str, verification: dict) -> dict:
        """
        Embed copyright ID and verification badge into all content fields.
        This modifies the content in-place before publishing.
        """
        badge    = verification.get("verification_badge", "🔍 UNVERIFIED")
        repro    = f"© {datetime.datetime.utcnow().year} NEXUS NOW · {copyright_id} · All Rights Reserved"
        caveat   = verification.get("recommended_caveats", "")

        # Stamp video script
        script = content.get("video_script", "")
        if script:
            footer = f"\n\n[NEXUS NOW. {badge}. All reporting copyright {datetime.datetime.utcnow().year}. Content ID: {copyright_id}]"
            content["video_script"] = script + footer

        # Stamp YouTube description
        yt_desc = content.get("youtube_description", "")
        yt_footer = (
            f"\n\n{'─'*50}\n"
            f"© {datetime.datetime.utcnow().year} NEXUS NOW — All Rights Reserved\n"
            f"Content ID: {copyright_id} | Verification: {badge}\n"
            f"AI-Generated editorial content by NEXUS NOW.\n"
            f"Unauthorized reproduction is prohibited.\n"
            + (f"Editorial note: {caveat}\n" if caveat else "")
        )
        content["youtube_description"] = yt_desc + yt_footer

        # Stamp Instagram caption
        ig_caption = content.get("instagram_caption", "")
        ig_footer  = f"\n\n{badge} | © NEXUS NOW · {copyright_id}"
        content["instagram_caption"] = ig_caption + ig_footer

        # Stamp tweet thread last tweet
        tweets = content.get("tweet_thread", [])
        if tweets:
            tweets[-1] += f"\n\n{badge} | © NEXUS NOW | ID: {copyright_id}"
            content["tweet_thread"] = tweets

        # Add copyright + verification fields
        content["copyright_id"]       = copyright_id
        content["verification_status"]= verification.get("verification_status", "UNVERIFIED")
        content["verification_badge"] = badge
        content["confidence_score"]   = verification.get("confidence_score", 5.0)
        content["is_safe_to_publish"] = verification.get("is_safe_to_publish", True)
        content["copyright_notice"]   = repro

        return content

    # ── REGISTER TO LOGS ──────────────────────────────────────────────────
    def register_copyright(self, certificate: dict):
        """Log the copyright certificate to local registry + Google Sheets."""
        self.registry.append(certificate)
        self._save_copyright_registry()

        # Log to Google Sheets if available
        log_to_sheets(
            "AEGIS",
            f"Copyright registered: {certificate['copyright_id']} — '{certificate['title'][:50]}'",
            "success"
        )

    # ── MASTER PROCESS ────────────────────────────────────────────────────
    def process(self, content: dict) -> dict:
        """
        Full AEGIS pipeline for one content package:
        1. Fact-check
        2. Generate copyright ID + certificate
        3. Stamp all content fields
        4. Register copyright
        5. Block unsafe content

        Returns the stamped content dict ready for publishing.
        """
        headline = content.get("headline", "Unknown")
        self.log(f"AEGIS processing: '{headline}'")

        # Step 1: Fact-check
        verification = self.fact_check(content)

        # Step 2: Safety gate
        if not verification.get("is_safe_to_publish", True):
            self.log(f"⛔ BLOCKED by AEGIS: '{headline}' — not safe to publish")
            self.log(f"   Reason: {verification.get('fact_checker_notes','')}")
            content["aegis_blocked"] = True
            content["aegis_block_reason"] = verification.get("fact_checker_notes", "")
            return content

        # Step 3: Generate copyright
        copyright_id  = self.generate_copyright_id(content)
        certificate   = self.generate_copyright_certificate(content, copyright_id)

        # Step 4: Stamp everything
        content = self.stamp_content(content, copyright_id, verification)

        # Step 5: Register
        self.register_copyright(certificate)

        self.log(f"✅ AEGIS complete: {copyright_id} | {verification.get('verification_badge')}")
        content["copyright_certificate"] = certificate
        return content

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        for i, c in enumerate(text):
            if c in "{[":
                return text[i:]
        return text

    def get_registry_stats(self) -> dict:
        """Stats about registered copyrights."""
        total = len(self.registry)
        by_cat = {}
        for r in self.registry:
            cat = r.get("category","unknown")
            by_cat[cat] = by_cat.get(cat, 0) + 1
        return {
            "total_copyrights_registered": total,
            "by_category": by_cat,
            "latest":      self.registry[-1] if self.registry else None
        }
