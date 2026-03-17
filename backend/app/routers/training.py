from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.training import TrainModelResponse
from app.schemas.models import ModelItem, ModelListResponse, ActivateModelResponse
from app.services.training import train_model, list_models, activate_model

router = APIRouter(prefix="/api", tags=["training"])


@router.post("/train-model", response_model=TrainModelResponse)
async def train_model_endpoint(
    file: UploadFile = File(...),
    technology: str = Form(..., pattern="^(Lummus|Technip)$"),
    feed_type: str = Form(..., pattern="^(Ethane|Propane)$"),
    db: Session = Depends(get_db),
):
    """
    Train GBR soft-sensor models from uploaded CSV.

    CSV columns: feed, shc, cot, cop, cit, feed_ethane_pct, feed_propane_pct,
    thickness, yield, coking_rate, tmt, conversion, propylene (plus optional targets).

    Returns accuracy metrics per target and extracted sensitivities.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")

    csv_bytes = await file.read()
    if len(csv_bytes) == 0:
        raise HTTPException(400, "Uploaded CSV is empty")

    try:
        result = train_model(db, csv_bytes, technology, feed_type)
    except ValueError as e:
        raise HTTPException(422, str(e))

    return result


@router.get("/models", response_model=ModelListResponse)
def get_models(db: Session = Depends(get_db)):
    """List all models with metrics and active status."""
    return {"models": list_models(db)}


@router.put("/models/{model_id}/activate", response_model=ActivateModelResponse)
def activate_model_endpoint(model_id: int, db: Session = Depends(get_db)):
    """
    Activate a model: deactivates siblings, copies extracted
    sensitivities to sensitivity_config table.
    """
    try:
        return activate_model(db, model_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
