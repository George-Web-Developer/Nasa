"""
Dashboard Telemetry & Mission Analytics Router.
NASA Space Apps Challenge 2026 - Health Monitoring Software.

Provides aggregated read endpoints for mission control & flight surgeon monitoring dashboards:
- Latest fused multimodal scores per astronaut
- Open unhandled alerts
- Audit trail of knowledge base protocols referenced during companion dialogue
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import Astronaut, Session, FusionResult, Alert, KBUsage, KBChunk
from app.schemas import LatestFusedScoreItem, AlertRead, KBUsageRead

router = APIRouter(prefix="/dashboard", tags=["Dashboard Analytics"])


@router.get("/fused-latest", response_model=List[LatestFusedScoreItem])
def get_latest_fused_scores(db: DBSession = Depends(get_db)):
    """
    Retrieve the most recent fused multimodal assessment for each crew member.
    Powers flight surgeon overview telemetry graphs.
    """
    astronauts = db.query(Astronaut).all()
    results = []

    for astro in astronauts:
        # Find latest completed session with fusion result
        latest_fusion = (
            db.query(FusionResult)
            .join(Session, FusionResult.session_id == Session.id)
            .filter(FusionResult.astronaut_id == astro.id)
            .order_by(FusionResult.created_at.desc())
            .first()
        )

        if latest_fusion:
            session = latest_fusion.session
            results.append(
                LatestFusedScoreItem(
                    astronaut_id=astro.id,
                    astronaut_name=astro.name,
                    session_id=latest_fusion.session_id,
                    mission_day=session.mission_day if session else 0,
                    composite_score=latest_fusion.composite_score,
                    fused_scores=latest_fusion.fused_scores,
                    z_scores=latest_fusion.z_scores,
                    channel_conflict=latest_fusion.channel_conflict,
                    baseline_confidence=latest_fusion.baseline_confidence,
                    created_at=latest_fusion.created_at,
                )
            )

    return results


@router.get("/alerts", response_model=List[AlertRead])
def get_open_alerts(db: DBSession = Depends(get_db)):
    """
    Retrieve all unhandled clinical and operational alerts across crew sessions.
    Sources: chat, keyword, analysis, fusion.
    """
    open_alerts = (
        db.query(Alert)
        .filter(Alert.handled == False)
        .order_by(Alert.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        AlertRead(
            id=a.id,
            session_id=a.session_id,
            reason=a.reason,
            source=a.source,
            handled=a.handled,
            created_at=a.created_at,
        )
        for a in open_alerts
    ]


@router.get("/kb-usage", response_model=List[KBUsageRead])
def get_recent_kb_usage(limit: int = 50, db: DBSession = Depends(get_db)):
    """
    Audit log of clinical knowledge base countermeasure chunks referenced by the AI companion.
    """
    usages = (
        db.query(KBUsage)
        .order_by(KBUsage.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for u in usages:
        chunk = u.chunk
        items.append(
            KBUsageRead(
                id=u.id,
                message_id=u.message_id,
                chunk_id=u.chunk_id,
                chunk_title=chunk.title if chunk else "Unknown Chunk",
                chunk_topic=chunk.topic if chunk else "General",
                source_name=chunk.source_name if chunk else "Onboard Protocol",
                created_at=u.created_at,
            )
        )
    return items
