"""
Package Script for Astronaut Psychological Check-in Assistant.
NASA Space Apps Challenge 2026 - Health Monitoring Software.

Builds a clean, production-ready 'astro-chatbot.zip' archive for teammates.
Excludes:
- .env (live environment configuration)
- venv/ (.venv/, env/)
- *.db, *.sqlite (local SQLite databases)
- __pycache__/, *.pyc, .pytest_cache/
- .git/ and previous archives

Performs automated security scanning to ensure no secrets or API keys are leaked.
"""

import os
import re
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = BASE_DIR / "astro-chatbot.zip"

# Excluded directory names
EXCLUDE_DIRS = {
    "venv",
    ".venv",
    "env",
    "ENV",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

# Excluded file patterns
EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db",
    ".sqlite",
    ".sqlite3",
}

EXCLUDE_EXACT_FILES = {
    ".env",
    "astro-chatbot.zip",
    ".DS_Store",
    "Thumbs.db",
}

# Security scanner regex patterns
SECRET_PATTERNS = [
    re.compile(r"\bsk-ant-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"\bsk-[a-zA-Z0-9_\-]{30,}"),
    re.compile(r"ANTHROPIC_API_KEY\s*=\s*['\"][a-zA-Z0-9_\-]{15,}['\"]"),
]


def is_excluded(path: Path) -> bool:
    """Check if a file or directory should be excluded from the zip."""
    rel_parts = path.relative_to(BASE_DIR).parts

    # Check if any parent directory is excluded
    for part in rel_parts[:-1]:
        if part in EXCLUDE_DIRS:
            return True

    # Check the file/dir itself
    name = path.name
    if path.is_dir() and name in EXCLUDE_DIRS:
        return True

    if name in EXCLUDE_EXACT_FILES:
        return True

    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True

    return False


def scan_file_for_secrets(file_path: Path) -> list:
    """Scan file content for leaked API keys or credentials."""
    findings = []
    # Skip binary or very large files
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    for pattern in SECRET_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            # Allow documented placeholders
            if "your_anthropic_api_key_here" in match or "your_" in match:
                continue
            findings.append((pattern.pattern, match[:10] + "..." if len(match) > 10 else match))

    return findings


def build_package():
    print("=====================================================================")
    print(" AstroCheck Assistant - Teammate Package Builder")
    print("=====================================================================")
    print(f"Base Directory: {BASE_DIR}")
    print(f"Target Output:  {OUTPUT_ZIP.name}")
    print("\n[Step 1/3] Scanning project files and verifying security...")

    files_to_pack = []
    security_violations = []

    for root, dirs, files in os.walk(BASE_DIR):
        current_dir = Path(root)

        # Prune excluded directories from traversal
        dirs[:] = [d for d in dirs if not is_excluded(current_dir / d)]

        for file in files:
            file_path = current_dir / file
            if not is_excluded(file_path):
                # Run secret scan
                findings = scan_file_for_secrets(file_path)
                if findings:
                    security_violations.append((file_path, findings))
                files_to_pack.append(file_path)

    # Report security findings
    if security_violations:
        print("\n[SECURITY ALERT] Potential secrets found! Packaging aborted:")
        for path, issues in security_violations:
            rel = path.relative_to(BASE_DIR)
            print(f"  - {rel}: {issues}")
        return False

    print(f"  -> Scan clean! 0 secrets detected across {len(files_to_pack)} candidate files.")

    print("\n[Step 2/3] Creating zip archive...")
    if OUTPUT_ZIP.exists():
        try:
            OUTPUT_ZIP.unlink()
        except Exception as e:
            print(f"Note removing existing zip: {e}")

    total_bytes = 0
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files_to_pack:
            arcname = file_path.relative_to(BASE_DIR)
            zipf.write(file_path, arcname)
            total_bytes += file_path.stat().st_size

    zip_size_kb = OUTPUT_ZIP.stat().st_size / 1024
    total_mb = total_bytes / (1024 * 1024)

    print(f"  -> Created: {OUTPUT_ZIP.name} ({zip_size_kb:.1f} KB, uncompressed: {total_mb:.2f} MB)")

    print("\n[Step 3/3] Verification Checklist:")
    checklist = [
        (".env excluded", not any(f.name == ".env" for f in files_to_pack)),
        ("venv/ excluded", not any("venv" in f.parts for f in files_to_pack)),
        ("*.db databases excluded", not any(f.suffix == ".db" for f in files_to_pack)),
        ("__pycache__ excluded", not any("__pycache__" in f.parts for f in files_to_pack)),
        ("No leaked API secrets", len(security_violations) == 0),
        ("run.bat included", any(f.name == "run.bat" for f in files_to_pack)),
        ("web/chatbot-demo.html included", any(f.name == "chatbot-demo.html" for f in files_to_pack)),
        ("web/widget.js included", any(f.name == "widget.js" for f in files_to_pack)),
        ("docs/TEAMMATE_GUIDE.md included", any(f.name == "TEAMMATE_GUIDE.md" for f in files_to_pack)),
        ("seed.py & requirements.txt included", any(f.name == "seed.py" for f in files_to_pack) and any(f.name == "requirements.txt" for f in files_to_pack)),
    ]

    all_passed = True
    for item, status in checklist:
        mark = "✓ PASS" if status else "✗ FAIL"
        if not status:
            all_passed = False
        print(f"  [{mark}] {item}")

    print("\n=====================================================================")
    if all_passed:
        print(" SUCCESS: astro-chatbot.zip is ready to share with your teammate!")
    else:
        print(" WARNING: Some verification checks failed. Review checklist above.")
    print("=====================================================================")
    return all_passed


if __name__ == "__main__":
    build_package()
