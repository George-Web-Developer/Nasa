"""
Modular Astro Router for Host Application Integration (Mode B).
NASA Space Apps Challenge 2026 - Health Monitoring Software.

Allows teammates building in FastAPI / Python to mount the entire Astronaut Psychological
Check-in and Biometric Fusion engine as a single APIRouter using:

    from app.astro_router import create_astro_router
    app.include_router(create_astro_router(db_url="...", config={...}))

Reuses the host app's database connection, isolates tables with 'astro_' prefix,
and optionally secures all endpoints via API_TOKEN.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.responses import FileResponse

import app.config as app_config
from app.database import configure_database, init_db
from app.routers import sessions, chat, astronauts, alerts, kb, dashboard


def create_astro_router(
    db_url: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> APIRouter:
    """
    Factory that instantiates and returns a unified APIRouter containing all astronaut
    check-in, conversational companion, and multimodal fusion endpoints.

    Parameters:
    - db_url: Optional connection string (e.g. teammate's PostgreSQL or SQLite).
              When provided, reconfigures the ORM engine and runs versioned migrations.
    - config: Optional configuration dictionary:
        - "api_token": Optional secret string; when provided, requires 'Authorization: Bearer <token>'
        - "mock_llm": Optional bool; forces mock mode for testing without LLM API keys
        - "llm_provider": Optional str ('anthropic' | 'openai_compatible')
        - "llm_api_key": Optional str API key
        - "llm_model": Optional str model identifier
    """
    cfg = config or {}

    # 1. Configure database if custom DB_URL provided
    if db_url:
        app_config.DB_URL = db_url
        configure_database(db_url)
    else:
        # Ensure default DB tables are initialized
        init_db()

    # 2. Apply runtime configuration overrides
    if "mock_llm" in cfg:
        app_config.MOCK_LLM = bool(cfg["mock_llm"])
    if "api_token" in cfg:
        app_config.API_TOKEN = str(cfg["api_token"]) if cfg["api_token"] else None
    if "llm_provider" in cfg:
        app_config.LLM_PROVIDER = str(cfg["llm_provider"])
    if "llm_api_key" in cfg:
        app_config.LLM_API_KEY = str(cfg["llm_api_key"])
    if "llm_model" in cfg:
        app_config.LLM_MODEL = str(cfg["llm_model"])

    # 3. Setup optional token verification dependency
    dependencies = []
    api_token = cfg.get("api_token") or app_config.API_TOKEN
    if api_token:
        async def verify_token(authorization: Optional[str] = Header(None)):
            expected = f"Bearer {api_token}"
            if not authorization or authorization != expected:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API Token",
                )
        dependencies.append(Depends(verify_token))

    # 4. Create Master Router
    router = APIRouter(
        tags=["Astronaut Check-in Subsystem"],
        dependencies=dependencies,
    )

    # 5. Include all domain sub-routers
    router.include_router(sessions.router)
    router.include_router(chat.router)
    router.include_router(astronauts.router)
    router.include_router(alerts.router)
    router.include_router(kb.router)
    router.include_router(dashboard.router)

    # 6. Expose web component widget.js through router for seamless frontend embedding
    web_dir = Path(__file__).resolve().parent.parent / "web"

    @router.get("/widget.js", tags=["Frontend Widget"])
    def get_widget_script():
        """Serve the framework-free drop-in Web Component <astro-chat>."""
        widget_path = web_dir / "widget.js"
        if not widget_path.exists():
            raise HTTPException(status_code=404, detail="widget.js not found in web directory")
        return FileResponse(widget_path, media_type="application/javascript")

    @router.get("/astro-health", tags=["Health"])
    def checkin_subsystem_health():
        """Health check endpoint for the astronaut check-in subsystem."""
        return {
            "status": "healthy",
            "subsystem": "Astronaut Psychological Check-in & Multimodal Fusion",
            "mock_llm": app_config.MOCK_LLM,
            "llm_provider": getattr(app_config, "LLM_PROVIDER", "anthropic"),
            "db_url": app_config.DB_URL,
        }

    return router
