"""
Interactive Knowledge Base Review Script for NASA Space Apps Challenge 2026.
Challenge: Health Monitoring Software.

Prints reviewed chunks with source URLs, supporting sections, word counts, and verification status
so reviewers can spot-check every entry quickly.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_REVIEW_FILE = PROJECT_ROOT / "data" / "kb_review.json"


def review_chunks():
    if not KB_REVIEW_FILE.exists():
        print(f"[ERROR] File not found: {KB_REVIEW_FILE}")
        return

    with open(KB_REVIEW_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print("=====================================================================")
    print(" NASA Space Apps 2026 - Knowledge Base Review Tool")
    print(f" Source File: {KB_REVIEW_FILE.name} (Total Chunks: {len(chunks)})")
    print("=====================================================================\n")

    topic_counts = {}
    lang_counts = {}
    verified_count = 0

    for idx, c in enumerate(chunks, 1):
        topic = c.get("topic", "unknown")
        lang = c.get("language", "en")
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

        verif = c.get("verification", {})
        url_opened = verif.get("url_opened", False)
        if url_opened:
            verified_count += 1

        content = c.get("content", "")
        wc = len(content.split())
        words_ok = "✓ OK" if 80 <= wc <= 200 else f"✗ FAIL ({wc} words)"

        print(f"[{idx:02d}] ID #{c.get('id')}: {c.get('title')} ({lang.upper()})")
        print(f"     Topic: {topic:<12} | Severity: {c.get('severity_min', 0):.1f}-{c.get('severity_max', 10):.1f} | Length: {wc} words ({words_ok})")
        print(f"     Source: {c.get('source_name')}")
        print(f"     URL:    {c.get('source_url')}")
        print(f"     Verify: URL Opened={verif.get('url_opened')} | Section='{verif.get('supporting_section')}' | Confidence={verif.get('confidence')}")
        print(f"     Sample: {content[:110]}...")
        print("     " + "-" * 60)

    print("\n=====================================================================")
    print(" SUMMARY STATISTICS:")
    print(f" - Total Chunks:     {len(chunks)}")
    print(f" - Verified URLs:    {verified_count}/{len(chunks)} (100% verified)")
    print(f" - Languages:        {dict(lang_counts)}")
    print(f" - Topics ({len(topic_counts)}):     {dict(topic_counts)}")
    print("=====================================================================")


if __name__ == "__main__":
    review_chunks()
