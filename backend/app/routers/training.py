from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.training import TrainModelResponse, BenchmarkResponse
from app.schemas.models import ModelItem, ModelListResponse, ActivateModelResponse
from app.services.training import train_model, list_models, activate_model, benchmark_models
from app.engine.model_benchmark import AVAILABLE_ALGORITHMS

router = APIRouter(prefix="/api", tags=["training"])


@router.post("/benchmark-models")
async def benchmark_models_endpoint(
    file: UploadFile = File(...),
    technology: str = Form(..., pattern="^(Lummus|Technip)$"),
    feed_type: str = Form(..., pattern="^(Ethane|Propane)$"),
    algorithms: str = Form(..., description="Comma-separated algorithm names"),
    db: Session = Depends(get_db),
):
    """
    Benchmark user-selected algorithms on uploaded simulation CSV.

    Trains each algorithm, measures accuracy + interpolation, and recommends
    the best model for production use.

    algorithms: comma-separated, e.g. "Ridge,XGBoost,LightGBM"
    Available: Ridge, RandomForest, GradientBoosting, XGBoost, LightGBM
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")

    csv_bytes = await file.read()
    if len(csv_bytes) == 0:
        raise HTTPException(400, "Uploaded CSV is empty")

    algo_list = [a.strip() for a in algorithms.split(",") if a.strip()]
    invalid = [a for a in algo_list if a not in AVAILABLE_ALGORITHMS]
    if invalid:
        raise HTTPException(
            400,
            f"Invalid algorithm(s): {invalid}. Available: {AVAILABLE_ALGORITHMS}",
        )

    if not algo_list:
        raise HTTPException(400, "At least one algorithm must be selected")

    try:
        result = benchmark_models(db, csv_bytes, technology, feed_type, algo_list)
    except ValueError as e:
        raise HTTPException(422, str(e))

    return result


@router.get("/available-algorithms")
def get_available_algorithms():
    """Return list of available ML algorithms for benchmarking."""
    return {"algorithms": AVAILABLE_ALGORITHMS}


@router.post("/train-model", response_model=TrainModelResponse)
async def train_model_endpoint(
    file: UploadFile = File(...),
    technology: str = Form(..., pattern="^(Lummus|Technip)$"),
    feed_type: str = Form(..., pattern="^(Ethane|Propane)$"),
    algorithm: str = Form("Ridge", description="Algorithm name"),
    db: Session = Depends(get_db),
):
    """
    Train a production soft-sensor model from uploaded CSV.

    algorithm: Ridge, RandomForest, GradientBoosting, XGBoost, LightGBM
    Default: Ridge (best for interpolation on sparse grid data).
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")

    csv_bytes = await file.read()
    if len(csv_bytes) == 0:
        raise HTTPException(400, "Uploaded CSV is empty")

    if algorithm not in AVAILABLE_ALGORITHMS:
        raise HTTPException(
            400,
            f"Invalid algorithm: {algorithm}. Available: {AVAILABLE_ALGORITHMS}",
        )

    try:
        result = train_model(db, csv_bytes, technology, feed_type, algorithm)
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
