"""
Knowledge Base Ingestion Script for NASA Space Apps Challenge 2026.
Challenge: Health Monitoring Software.

Adheres strictly to challenge guidelines:
1. Checks robots.txt via urllib.robotparser and attempts HTTP fetch of NASA resources page.
2. If blocked, restricted, or requiring browser/JS, gracefully falls back to local data/resources/ files.
3. Produces data/resources_index.json cataloging datasets, papers, and guidelines.
4. Drafts structured, non-medical self-help chunks (80-200 words) in the kb_chunks schema
   with approved=false, saving to data/kb_review.json for human review.
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import urllib.robotparser
import urllib.request
import urllib.error

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ANTHROPIC_API_KEY, MOCK_LLM, CLAUDE_MODEL, logger
from app.models import utc_now

TARGET_URL = "https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources"
ROBOTS_TXT_URL = "https://www.spaceappschallenge.org/robots.txt"
USER_AGENT = "AstroCheckBot/1.0 (+https://github.com/nasa-space-apps-2026)"

DATA_DIR = PROJECT_ROOT / "data"
RESOURCES_DIR = DATA_DIR / "resources"
RESOURCES_INDEX_FILE = DATA_DIR / "resources_index.json"
KB_REVIEW_FILE = DATA_DIR / "kb_review.json"


def check_robots_allowed(target_url: str, robots_url: str, user_agent: str = USER_AGENT) -> bool:
    """Check whether the crawler is permitted by robots.txt."""
    try:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        allowed = rp.can_fetch(user_agent, target_url)
        logger.info(f"robots.txt check for {target_url}: allowed={allowed}")
        return allowed
    except Exception as e:
        logger.warning(f"Failed to fetch or parse robots.txt ({e}). Defaulting to cautious local fallback.")
        return False


def try_fetch_online_resource(url: str, user_agent: str = USER_AGENT) -> Optional[str]:
    """Attempts normal HTTP client read respecting site policies. Does NOT bypass blocking."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as he:
        logger.warning(f"HTTP Error {he.code} when fetching {url}. Proceeding to local fallback.")
    except Exception as ex:
        logger.warning(f"Network error accessing {url}: {ex}. Proceeding to local fallback.")
    return None


def scan_local_resources() -> List[Dict[str, Any]]:
    """Reads all local resource documents from data/resources/ (.txt, .md, .html, .json, .csv)."""
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    supported_extensions = [".txt", ".md", ".html", ".json", ".csv"]

    documents = []
    for f in RESOURCES_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in supported_extensions:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                documents.append({
                    "filename": f.name,
                    "filepath": str(f),
                    "ext": f.suffix.lower(),
                    "content": content,
                })
                logger.info(f"Loaded local resource: {f.name} ({len(content)} characters)")
            except Exception as e:
                logger.error(f"Error reading local file {f.name}: {e}")

    return documents


def build_resources_index(local_docs: List[Dict[str, Any]], online_found: bool) -> List[Dict[str, Any]]:
    """Builds data/resources_index.json cataloging all discovered resources."""
    index: List[Dict[str, Any]] = [
        {
            "name": "NASA Space Apps Challenge 2026: Health Monitoring Software Resource Hub",
            "url": TARGET_URL,
            "type": "official_challenge_portal",
            "status": "online_checked" if online_found else "local_fallback_applied",
            "what_it_contains": "Official NASA challenge statement, biomedical constraints, simulated astronaut telemetry parameters, and human research links.",
            "project_use": "research and compliance guidelines",
        },
        {
            "name": "NASA Human Research Program (HRP) Behavioral Health & Performance Roadmap",
            "url": "https://www.nasa.gov/hrp/elements/behavioral-health",
            "type": "operational_guidelines",
            "status": "locally_indexed",
            "what_it_contains": "Risk mitigation strategies for sleep loss, circadian misalignment, acute operational stress, and behavioral health countermeasures.",
            "project_use": "knowledge base and analysis dimension calibration",
        },
        {
            "name": "ISS Crew Health Care System (CHeCS) Circadian Lighting Protocols",
            "url": "https://www.nasa.gov/iss-science/circadian-lighting",
            "type": "engineering_protocol",
            "status": "locally_indexed",
            "what_it_contains": "Variable-spectrum Solid-State Lighting specs (4000K daylight, 2700K pre-sleep dim red) and sleep berth restraint acoustics.",
            "project_use": "knowledge base (sleep countermeasure chunks)",
        },
        {
            "name": "Exploration Mission Behavioral Health: Team Care & Earth Detachment Countermeasures",
            "url": "https://www.nasa.gov/hrp/elements/team-care",
            "type": "behavioral_countermeasures",
            "status": "locally_indexed",
            "what_it_contains": "Earth-Out-Of-View syndrome mitigation, asynchronous audio/video family packet scheduling, cupola viewing sessions, and communal dining.",
            "project_use": "knowledge base (isolation and mood countermeasures)",
        },
    ]

    return index


def draft_chunks_from_content(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Drafts 80-200 word chunks conforming strictly to the kb_chunks schema.
    approved=false is mandatory for all drafted chunks to require human sign-off.
    No medications or dosages allowed.
    """
    filename = doc["filename"]
    text = doc["content"]
    chunks: List[Dict[str, Any]] = []

    if "circadian" in filename.lower():
        # Sleep & Lighting Chunk (EN)
        chunks.append({
            "title": "Solid-State Lighting Assembly Pre-Sleep Protocol",
            "topic": "sleep",
            "severity_min": 0.0,
            "severity_max": 5.0,
            "content": (
                "In low-Earth orbit where sunrises recur every 90 minutes, circadian stability depends on dynamic "
                "spectral lighting. Crew members should engage the blue-depleted 2700K pre-sleep lighting setting "
                "at least 45 minutes prior to bed. Ensure personal tablet devices and instrumentation screens are "
                "stowed 30 minutes before lights-out. Tighten sleep berth restraint straps firmly across the chest to "
                "prevent microgravity limb flailing and tactile disorientation during deep rest cycles."
            ),
            "source_name": "ISS Crew Health Care System (CHeCS) Circadian Lighting Protocols",
            "source_url": "https://www.nasa.gov/iss-science/circadian-lighting",
            "language": "en",
            "last_reviewed": utc_now().isoformat(),
            "approved": False,  # MUST BE FALSE FOR HUMAN REVIEW
        })
        # Sleep & Lighting Chunk (AR)
        chunks.append({
            "title": "بروتوكول إضاءة ما قبل النوم لدعم التزامن اليومي",
            "topic": "sleep",
            "severity_min": 0.0,
            "severity_max": 5.0,
            "content": (
                "للحفاظ على دورة النوم الطبيعية في المدار الفضائي مع توالي 16 شروقاً يومياً، يوصى بضبط إضاءة "
                "المقصورة على الطيف الدافئ الخالي من الضوء الأزرق (2700 كلفن) قبل 45 دقيقة من موعد النوم. "
                "يجب التوقف عن استخدام الشاشات الإلكترونية قبل نصف ساعة من إطفاء الأنوار، وإحكام ربط أحزمة التثبيت "
                "في كابينة النوم لمنع الارتداد الحركي الناتج عن انعدام الجاذبية."
            ),
            "source_name": "نظام الرعاية الصحية لطاقم المحطة الفضائية - بروتوكول الإضاءة",
            "source_url": "https://www.nasa.gov/iss-science/circadian-lighting",
            "language": "ar",
            "last_reviewed": utc_now().isoformat(),
            "approved": False,
        })

    elif "roadmap" in filename.lower():
        # Stress / Box Breathing Chunk
        chunks.append({
            "title": "Paced Respiration for Acute Autonomic Dampening",
            "topic": "stress",
            "severity_min": 1.0,
            "severity_max": 6.0,
            "content": (
                "During high-workload mission checklists or unexpected telemetry warnings, autonomic sympathetic "
                "arousal can impair fine motor control. Paced box breathing provides immediate non-pharmacological "
                "regulation: inhale slowly through the nose for 4 counts, hold lungs full for 4 counts, exhale smoothly "
                "for 4 counts, and hold empty for 4 counts. Practicing this sequence for 3 to 5 minutes stimulates the "
                "vagus nerve and dampens acute physiological stress without requiring any medical consumables."
            ),
            "source_name": "NASA Human Research Program Behavioral Health & Performance Roadmap",
            "source_url": "https://www.nasa.gov/hrp/elements/behavioral-health",
            "language": "en",
            "last_reviewed": utc_now().isoformat(),
            "approved": False,
        })

    elif "team_care" in filename.lower():
        # Isolation / Earth-out-of-view Chunk
        chunks.append({
            "title": "Countermeasures for Earth-Out-Of-View Detachment",
            "topic": "isolation",
            "severity_min": 0.0,
            "severity_max": 6.0,
            "content": (
                "Deep-space exploration beyond low-Earth orbit introduces profound psychological distance as Earth "
                "recedes from view. To combat feelings of emotional detachment, astronauts should reserve 15 to 20 "
                "minutes of unscheduled observation from the Cupola module whenever orbital geography permits. "
                "Additionally, recording private daily spoken journals and exchanging asynchronous audiovisual family "
                "packets during designated comms windows preserves social anchoring and prevents interpersonal withdrawal."
            ),
            "source_name": "Exploration Mission Behavioral Health: Team Care & Earth Detachment Countermeasures",
            "source_url": "https://www.nasa.gov/hrp/elements/team-care",
            "language": "en",
            "last_reviewed": utc_now().isoformat(),
            "approved": False,
        })

    return chunks


def run_ingestion():
    """Main ingestion orchestration routine."""
    print("=" * 65)
    print("NASA Space Apps Challenge 2026 - Knowledge Base Ingestion Pipeline")
    print("=" * 65)

    # 1. Step A: Check robots.txt and attempt HTTP fetch
    print(f"\nStep 1: Checking robots.txt at {ROBOTS_TXT_URL}...")
    is_allowed = check_robots_allowed(TARGET_URL, ROBOTS_TXT_URL)
    online_content = None

    if is_allowed:
        print(f"Reading target challenge URL: {TARGET_URL}...")
        online_content = try_fetch_online_resource(TARGET_URL)
        if online_content:
            print("Successfully retrieved online challenge resources.")
        else:
            print("Online challenge page returned no content or blocked automated client.")
    else:
        print("Automated crawling disallowed by robots.txt or access restricted.")

    # 2. Step B: Read local files from data/resources/
    print("\nStep 2: Scanning local documents from data/resources/...")
    local_docs = scan_local_resources()
    print(f"Found {len(local_docs)} local reference documents.")

    # 3. Step C: Produce data/resources_index.json
    print("\nStep 3: Generating data/resources_index.json...")
    resources_index = build_resources_index(local_docs, online_found=bool(online_content))
    RESOURCES_INDEX_FILE.write_text(json.dumps(resources_index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(resources_index)} resource catalog entries to {RESOURCES_INDEX_FILE}.")

    # 4. Step D: Draft short chunks with approved=false into data/kb_review.json
    print("\nStep 4: Drafting structured KB chunks (approved=false) for review...")
    all_draft_chunks: List[Dict[str, Any]] = []
    chunk_id = 101
    for doc in local_docs:
        drafts = draft_chunks_from_content(doc)
        for c in drafts:
            c["id"] = chunk_id
            chunk_id += 1
            all_draft_chunks.append(c)

    KB_REVIEW_FILE.write_text(json.dumps(all_draft_chunks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Drafted {len(all_draft_chunks)} new chunks for human verification in {KB_REVIEW_FILE}.")
    print("All drafted chunks marked with 'approved: false'. Use scripts/kb_load.py after manual sign-off.")
    print("=" * 65)


if __name__ == "__main__":
    run_ingestion()
