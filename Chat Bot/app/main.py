from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import (
    CLAUDE_MODEL,
    MOCK_LLM,
    DB_URL,
    ALLOWED_ORIGINS,
    API_TOKEN,
    BASE_DIR,
    logger,
)
from app.database import init_db
from app.routers import sessions, chat, astronauts, alerts, kb, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables and FTS5 index on application startup."""
    logger.info("Initializing database tables and SQLite FTS5 index...")
    init_db()
    logger.info(
        f"Astronaut Psychological Check-in Backend started (MOCK_LLM={MOCK_LLM}, MODEL={CLAUDE_MODEL})"
    )
    yield
    logger.info("Application shutdown.")


app = FastAPI(
    title="Astronaut Psychological Check-in Assistant API",
    description=(
        "NASA Space Apps Challenge 2026 - Health Monitoring Software. "
        "Provides structured astronaut psychological check-ins, evidence-grounded analysis rating, "
        "companion support with RAG knowledge-base guidance, and dual-layer crisis safety safeguards."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware with ALLOWED_ORIGINS support
cors_origins = ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Optional API Token Authentication Middleware
@app.middleware("http")
async def verify_api_token(request: Request, call_next):
    if API_TOKEN:
        # Exclude documentation and static endpoints from token requirement
        public_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/",
            "/widget.js",
            "/chat-ui",
            "/chatbot-demo.html",
            "/sources",
            "/SOURCES.md",
        ]
        if (
            request.url.path not in public_paths
            and not request.url.path.startswith("/static")
            and not request.url.path.startswith("/web")
        ):
            auth_header = request.headers.get("Authorization")
            expected = f"Bearer {API_TOKEN}"
            if not auth_header or auth_header != expected:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API Token",
                )
    return await call_next(request)


# Register API Routers
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(astronauts.router)
app.include_router(alerts.router)
app.include_router(kb.router)
app.include_router(dashboard.router)


# Static and Web Component Endpoints
STATIC_DIR = BASE_DIR / "static"
WEB_DIR = BASE_DIR / "web"
WEB_DIR.mkdir(exist_ok=True)


@app.get("/widget.js", tags=["Frontend Widget"])
def get_widget_js():
    """Serve the framework-free drop-in Web Component <astro-chat>."""
    widget_path = WEB_DIR / "widget.js"
    if not widget_path.exists():
        raise HTTPException(status_code=404, detail="widget.js not found in web directory")
    return FileResponse(widget_path, media_type="application/javascript")


@app.get("/chat-ui", tags=["Frontend Widget"])
def get_chat_ui():
    """Serve the full-page standalone chat UI (for iframe embedding)."""
    chat_ui_path = STATIC_DIR / "chat-ui.html"
    if not chat_ui_path.exists():
        raise HTTPException(status_code=404, detail="chat-ui.html not found")
    return FileResponse(chat_ui_path, media_type="text/html")


@app.get("/chatbot-demo.html", tags=["Frontend Widget"])
def get_chatbot_demo():
    """Serve the interactive chatbot-demo.html for teammates testing the widget contract."""
    demo_path = WEB_DIR / "chatbot-demo.html"
    if not demo_path.exists():
        raise HTTPException(status_code=404, detail="chatbot-demo.html not found")
    return FileResponse(demo_path, media_type="text/html")


@app.get("/sources", tags=["Documentation"])
@app.get("/SOURCES.md", tags=["Documentation"])
def get_sources():
    """Serve the verified scientific literature and open-source citations document."""
    sources_path = BASE_DIR / "SOURCES.md"
    if not sources_path.exists():
        raise HTTPException(status_code=404, detail="SOURCES.md not found")
    return FileResponse(sources_path, media_type="text/markdown; charset=utf-8")


# Mount /web directory for teammate pages and assets
app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "service": "Astronaut Psychological Check-in Assistant",
        "challenge": "NASA Space Apps Challenge 2026 - Health Monitoring Software",
        "mock_llm": MOCK_LLM,
        "model": CLAUDE_MODEL,
        "docs": "/docs",
        "widget": "/widget.js",
        "chat_ui": "/chat-ui",
        "demo": "/chatbot-demo.html",
        "sources": "/sources",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "database": DB_URL,
        "mock_llm": MOCK_LLM,
    }
