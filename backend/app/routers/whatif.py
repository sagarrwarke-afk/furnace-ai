from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.optimizer import run_whatif

router = APIRouter(prefix="/api", tags=["whatif"])


class WhatIfRequest(BaseModel):
    furnace_id: str
    upload_id: str = "latest"
    delta_cot: float = Field(0.0, description="COT change in °C (negative = reduce)")
    delta_shc: float = Field(0.0, description="SHC change (e.g. +0.01)")
    delta_feed: float = Field(0.0, description="Feed rate change in t/hr")
    ethane_feed_purity: float = Field(92.0, description="% ethane in ethane furnace feed")
    propane_feed_purity: float = Field(85.0, description="% propane in propane furnace feed")


@router.post("/whatif")
def whatif_simulation(req: WhatIfRequest, db: Session = Depends(get_db)):
    try:
        result = run_whatif(
            db,
            furnace_id=req.furnace_id,
            upload_id=req.upload_id,
            delta_cot=req.delta_cot,
            delta_shc=req.delta_shc,
            delta_feed=req.delta_feed,
            ethane_feed_purity=req.ethane_feed_purity,
            propane_feed_purity=req.propane_feed_purity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
