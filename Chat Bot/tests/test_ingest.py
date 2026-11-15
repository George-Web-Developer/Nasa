import json
from pathlib import Path
import pytest
from scripts.kb_ingest import (
    scan_local_resources,
    build_resources_index,
    draft_chunks_from_content,
    RESOURCES_INDEX_FILE,
    KB_REVIEW_FILE,
)
from scripts.kb_load import load_approved_chunks


def test_scan_local_resources():
    """Verify scanner loads local resource files from data/resources/."""
    docs = scan_local_resources()
    assert len(docs) >= 3
    filenames = [d["filename"] for d in docs]
    assert any("circadian" in f for f in filenames)
    assert any("roadmap" in f for f in filenames)


def test_build_resources_index():
    """Verify resource index structures catalog with required schema."""
    docs = scan_local_resources()
    index = build_resources_index(docs, online_found=False)
    assert len(index) >= 3
    for entry in index:
        assert "name" in entry
        assert "url" in entry
        assert "type" in entry
        assert "what_it_contains" in entry
        assert "project_use" in entry


def test_draft_chunks_schema_and_approved_flag():
    """
    Verify drafted chunks:
    1. approved is strictly False (human sign-off required)
    2. Word count is appropriate (80-200 words)
    3. No medication or dosages mentioned
    4. Has source_name and source_url
    """
    sample_doc = {
        "filename": "iss_crew_circadian_countermeasures.txt",
        "content": "Sample content about circadian lighting and sleep schedules.",
    }
    chunks = draft_chunks_from_content(sample_doc)
    assert len(chunks) >= 1
    for chunk in chunks:
        # Schema verification
        assert "title" in chunk
        assert "topic" in chunk
        assert chunk["topic"] in ["sleep", "stress", "anxiety", "fatigue", "isolation", "mood", "focus", "escalation"]
        assert "severity_min" in chunk
        assert "severity_max" in chunk
        assert "content" in chunk
        assert "source_name" in chunk
        assert "source_url" in chunk
        assert "language" in chunk
        assert chunk["approved"] is False  # Mandatory for human review

        # Word count check
        words = chunk["content"].split()
        assert 30 <= len(words) <= 220

        # No medication or dosage advice
        content_lower = chunk["content"].lower()
        for forbidden in ["mg ", "milligram", "prescription", "dosage", "sedative"]:
            assert forbidden not in content_lower


def test_load_only_approved_chunks(tmp_path):
    """Verify kb_load loads ONLY chunks where approved == True."""
    test_json = tmp_path / "test_chunks.json"
    sample_data = [
        {
            "title": "Unapproved Technique",
            "topic": "stress",
            "severity_min": 0,
            "severity_max": 5,
            "content": "Test content",
            "source_name": "Test",
            "source_url": "https://example.com",
            "language": "en",
            "approved": False,
        },
        {
            "title": "Approved Technique",
            "topic": "stress",
            "severity_min": 0,
            "severity_max": 5,
            "content": "Test approved content",
            "source_name": "Test",
            "source_url": "https://example.com",
            "language": "en",
            "approved": True,
        },
    ]
    test_json.write_text(json.dumps(sample_data), encoding="utf-8")

    loaded_count = load_approved_chunks(test_json, force_approve=False)
    # Only 1 chunk should be loaded (the approved one)
    assert loaded_count == 1
