from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.config import (
    EconomicParamsResponse,
    EconomicParamsUpdateRequest,
    ConstraintsResponse,
    ConstraintsUpdateRequest,
)
from app.services.config import (
    get_economics,
    update_economics,
    get_constraints,
    update_constraints,
)

router = APIRouter(prefix="/api/config", tags=["config"])


# ---------- Economics ----------

@router.get("/economics", response_model=EconomicParamsResponse)
def get_economics_endpoint(db: Session = Depends(get_db)):
    """View all economic parameters."""
    return {"params": get_economics(db)}


@router.put("/economics", response_model=EconomicParamsResponse)
def put_economics(body: EconomicParamsUpdateRequest, db: Session = Depends(get_db)):
    """Update one or more economic parameters. Logs changes to audit_log."""
    try:
        updated = update_economics(db, [p.model_dump() for p in body.params])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"params": updated}


# ---------- Constraints ----------

@router.get("/constraints", response_model=ConstraintsResponse)
def get_constraints_endpoint(db: Session = Depends(get_db)):
    """View all constraint limits."""
    return {"constraints": get_constraints(db)}


@router.put("/constraints", response_model=ConstraintsResponse)
def put_constraints(body: ConstraintsUpdateRequest, db: Session = Depends(get_db)):
    """Update one or more constraint limits. Logs changes to audit_log."""
    try:
        updated = update_constraints(db, [c.model_dump() for c in body.constraints])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"constraints": updated}
