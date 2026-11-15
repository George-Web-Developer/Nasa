import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Core LLM and Database Settings
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()  # "anthropic" | "openai_compatible"
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "").strip()
LLM_API_KEY: str = os.getenv("LLM_API_KEY", os.getenv("ANTHROPIC_API_KEY", os.getenv("OPENAI_API_KEY", ""))).strip()
LLM_MODEL: str = os.getenv("LLM_MODEL", os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")).strip()
MOCK_LLM: bool = os.getenv("MOCK_LLM", "true").strip().lower() in ("true", "1", "t", "yes")
DB_URL: str = os.getenv("DB_URL", "sqlite:///./astronaut_checkin.db")

# Backwards compatibility aliases
ANTHROPIC_API_KEY: str = LLM_API_KEY
CLAUDE_MODEL: str = LLM_MODEL

# Security, Auth, and CORS Settings
ALLOWED_ORIGINS_RAW: str = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: list[str] = [origin.strip() for origin in ALLOWED_ORIGINS_RAW.split(",") if origin.strip()]
API_TOKEN: str = os.getenv("API_TOKEN", "")  # Optional auth bearer token

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("astronaut_backend")
