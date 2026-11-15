from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import Alert
from app.schemas import AlertRead, AlertHandleResponse
from app.config import logger

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=List[AlertRead])
def get_alerts(
    include_handled: bool = Query(False, description="Whether to include already handled alerts"),
    db: DBSession = Depends(get_db),
):
    """
    Fetch psychological and safety alerts.
    By default, returns only open (unhandled) alerts ordered with newest first.
    """
    query = db.query(Alert)
    if not include_handled:
        query = query.filter(Alert.handled == False)

    return query.order_by(Alert.created_at.desc()).all()


@router.patch("/{id}/handle", response_model=AlertHandleResponse)
def handle_alert(id: int, db: DBSession = Depends(get_db)):
    """
    Mark an active safety or clinical risk alert as handled.
    Used by mission flight controllers or flight surgeons.
    """
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {id} not found."
        )

    alert.handled = True
    db.commit()
    db.refresh(alert)

    logger.info(f"Alert {id} for session {alert.session_id} marked as handled.")

    return AlertHandleResponse(
        id=alert.id,
        session_id=alert.session_id,
        reason=alert.reason,
        source=alert.source,
        handled=alert.handled,
        message="Alert marked as handled successfully.",
    )
