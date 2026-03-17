from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.sensitivity import (
    SensitivityListResponse,
    SensitivityUpdateRequest,
    SensitivityUpdateResponse,
)
from app.services.sensitivity import get_all_sensitivities, update_sensitivity

router = APIRouter(prefix="/api", tags=["sensitivity"])


@router.get("/sensitivity", response_model=SensitivityListResponse)
def get_sensitivities(db: Session = Depends(get_db)):
    """Return all sensitivities grouped by technology/feed_type."""
    return {"groups": get_all_sensitivities(db)}


@router.put("/sensitivity", response_model=SensitivityUpdateResponse)
def put_sensitivity(body: SensitivityUpdateRequest, db: Session = Depends(get_db)):
    """Update a single sensitivity value (by id). Logs to audit_log."""
    try:
        return update_sensitivity(db, body.id, body.value)
    except ValueError as e:
        raise HTTPException(404, str(e))
