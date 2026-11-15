"""
Script to load reviewed and approved KB chunks into the database and rebuild FTS5 index.
NASA Space Apps Challenge 2026 - Health Monitoring Software.
"""
import sys
import json
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, init_db, rebuild_fts_index
from app.models import KBChunk, utc_now
from app.config import logger


def load_approved_chunks(file_path: Path, force_approve: bool = False) -> int:
    """
    Reads a JSON file of KB chunks and loads ONLY those with approved == True.
    If force_approve is set, marks all loaded chunks as approved (useful for placeholder seeding).
    """
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return 0

    with open(file_path, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)

    if not isinstance(chunks_data, list):
        logger.error(f"Expected a list of chunks in {file_path}, got {type(chunks_data)}")
        return 0

    init_db()
    db = SessionLocal()
    loaded_count = 0

    try:
        for item in chunks_data:
            is_approved = True if force_approve else item.get("approved", False)
            if not is_approved:
                logger.info(f"Skipping unapproved chunk: '{item.get('title')}'")
                continue

            # Check if chunk with title and topic already exists
            title = item.get("title", "").strip()
            topic = item.get("topic", "").strip()
            existing = db.query(KBChunk).filter(KBChunk.title == title, KBChunk.topic == topic).first()

            if existing:
                existing.content = item.get("content", existing.content)
                existing.severity_min = float(item.get("severity_min", existing.severity_min))
                existing.severity_max = float(item.get("severity_max", existing.severity_max))
                existing.source_name = item.get("source_name", existing.source_name)
                existing.source_url = item.get("source_url", existing.source_url)
                existing.language = item.get("language", existing.language)
                existing.approved = True
                existing.last_reviewed = utc_now()
                logger.info(f"Updated approved chunk: '{title}' [{topic}]")
            else:
                chunk = KBChunk(
                    title=title,
                    topic=topic,
                    severity_min=float(item.get("severity_min", 0.0)),
                    severity_max=float(item.get("severity_max", 10.0)),
                    content=item.get("content", ""),
                    source_name=item.get("source_name", "NASA Space Apps"),
                    source_url=item.get("source_url", "https://www.spaceappschallenge.org"),
                    language=item.get("language", "en"),
                    last_reviewed=utc_now(),
                    approved=True,
                )
                db.add(chunk)
                logger.info(f"Added approved chunk: '{title}' [{topic}]")

            loaded_count += 1

        db.commit()
        logger.info(f"Successfully loaded {loaded_count} approved chunks.")

        # Rebuild FTS5 index
        rebuild_fts_index(db)
        return loaded_count
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to load KB chunks: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Load approved KB chunks into SQLite database.")
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=str(PROJECT_ROOT / "data" / "kb_seed_placeholder.json"),
        help="Path to JSON file containing KB chunks",
    )
    parser.add_argument(
        "--force-approve",
        action="store_true",
        help="Force approve all chunks in the file (e.g. for seed placeholders)",
    )
    args = parser.parse_args()

    target_file = Path(args.file)
    print(f"Loading chunks from: {target_file}")
    loaded = load_approved_chunks(target_file, force_approve=args.force_approve)
    print(f"Done. Loaded/Updated {loaded} approved chunks.")


if __name__ == "__main__":
    main()
