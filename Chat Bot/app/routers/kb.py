from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.schemas import KBChunkRead
from app.services.kb_service import search_knowledge_base

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])


@router.get("/search", response_model=List[KBChunkRead])
def search_kb(
    q: Optional[str] = Query(None, description="Search terms for full text matching"),
    topic: Optional[str] = Query(None, description="Topic filter (sleep, stress, anxiety, fatigue, isolation, mood, focus, escalation)"),
    severity: Optional[float] = Query(None, ge=0.0, le=10.0, description="Severity score (0-10) to filter appropriate countermeasures"),
    language: Optional[str] = Query(None, description="Language filter ('en' or 'ar')"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of results to return"),
    db: DBSession = Depends(get_db),
):
    """
    Search approved knowledge base chunks.
    Uses SQLite FTS5 bm25 full-text ranking when search query `q` is provided.
    Filters by topic, language, and clinical severity range.
    """
    results = search_knowledge_base(
        db=db,
        query=q,
        topic=topic,
        severity=severity,
        language=language,
        limit=limit,
    )
    return results
