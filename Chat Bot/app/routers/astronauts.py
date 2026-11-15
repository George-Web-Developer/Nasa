from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.models import Astronaut, Session, Analysis
from app.schemas import SessionHistoryItem

router = APIRouter(prefix="/astronauts", tags=["Astronauts"])


class AstronautRead(BaseModel):
    id: int
    name: str
    language: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[AstronautRead])
def list_astronauts(db: DBSession = Depends(get_db)):
    """List all registered astronauts."""
    return db.query(Astronaut).all()


@router.get("/{id}/history", response_model=List[SessionHistoryItem])
def get_astronaut_history(id: int, db: DBSession = Depends(get_db)):
    """
    Get chronological history of sessions for an astronaut with date, mission_day,
    and psychological dimension scores to power frontend trend charts.
    """
    astronaut = db.query(Astronaut).filter(Astronaut.id == id).first()
    if not astronaut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Astronaut with id {id} not found."
        )

    sessions = (
        db.query(Session)
        .filter(Session.astronaut_id == id)
        .order_by(Session.created_at.asc())
        .all()
    )

    history = []
    for s in sessions:
        scores = None
        risk_flag = None
        if s.analysis:
            scores = s.analysis.scores
            risk_flag = s.analysis.risk_flag

        history.append(
            SessionHistoryItem(
                session_id=s.id,
                created_at=s.created_at,
                ended_at=s.ended_at,
                mission_day=s.mission_day,
                status=s.status,
                mode=s.mode,
                scores=scores,
                risk_flag=risk_flag,
            )
        )

    return history
