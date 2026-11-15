"""
Interactive and Automated Knowledge Base Approval Script for NASA Space Apps Challenge 2026.
Challenge: Health Monitoring Software.

Allows approving verified chunks individually by ID or in bulk (--all-verified),
saving the updated review file and optionally loading approved chunks directly into
the astronaut check-in database and FTS5 search index.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kb_load import load_approved_chunks
from app.config import logger


def approve_chunks(
    file_path: Path,
    ids: list[int] = None,
    all_verified: bool = False,
    load_to_db: bool = False,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Approves chunks in the specified review JSON file.
    Returns (newly_approved_count, total_approved_count).
    """
    if not file_path.exists():
        print(f"[ERROR] Review file not found: {file_path}")
        return 0, 0

    with open(file_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not isinstance(chunks, list):
        print(f"[ERROR] Invalid format in {file_path}: expected list of chunks.")
        return 0, 0

    id_set = set(ids or [])
    newly_approved = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for chunk in chunks:
        cid = chunk.get("id")
        verif = chunk.get("verification", {})
        url_opened = verif.get("url_opened", False)
        confidence = verif.get("confidence", "low")

        should_approve = False
        if all_verified and url_opened and confidence in ("high", "medium"):
            should_approve = True
        elif cid in id_set:
            should_approve = True

        if should_approve:
            if not chunk.get("approved", False):
                newly_approved += 1
                chunk["approved"] = True
                chunk["last_reviewed"] = now_iso
                print(f"[APPROVED] #{cid}: {chunk.get('title')} ({chunk.get('language')}) - {chunk.get('topic')}")
            else:
                print(f"[ALREADY APPROVED] #{cid}: {chunk.get('title')}")

    total_approved = sum(1 for c in chunks if c.get("approved", False))

    if not dry_run and newly_approved > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVED] Updated {file_path.name} with {newly_approved} new approvals.")

    print(f"\nApproval Status: {total_approved}/{len(chunks)} approved ({newly_approved} newly marked)")

    db_loaded = 0
    if load_to_db and not dry_run:
        print("\nLoading approved chunks into database and rebuilding FTS5 index...")
        db_loaded = load_approved_chunks(file_path, force_approve=False)
        print(f"[DATABASE] Successfully loaded {db_loaded} approved chunks into SQLite.")

    return newly_approved, total_approved


def main():
    parser = argparse.ArgumentParser(
        description="Approve verified knowledge base chunks and sync with database."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=str(PROJECT_ROOT / "data" / "kb_review.json"),
        help="Path to the KB review JSON file (default: data/kb_review.json)",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        type=int,
        help="One or more chunk IDs to approve (e.g. --ids 101 102 103)",
    )
    parser.add_argument(
        "--all-verified",
        action="store_true",
        help="Approve all chunks whose source URL has been opened and verified with high/medium confidence",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Load all approved chunks into the database and rebuild FTS5 index",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate approvals without writing to file or database",
    )

    args = parser.parse_args()

    if not args.all_verified and not args.ids and not args.load:
        parser.print_help()
        print("\n[NOTE] Specify --ids <id1 id2 ...>, --all-verified, or --load.")
        return

    file_path = Path(args.file)
    approve_chunks(
        file_path=file_path,
        ids=args.ids,
        all_verified=args.all_verified,
        load_to_db=args.load,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
