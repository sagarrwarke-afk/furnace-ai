from pydantic import BaseModel, Field
from typing import Optional


class TrainModelRequest(BaseModel):
    technology: str = Field(..., pattern="^(Lummus|Technip)$", description="Lummus or Technip")
    feed_type: str = Field(..., pattern="^(Ethane|Propane)$", description="Ethane or Propane")


class TargetMetrics(BaseModel):
    r2_train: float
    r2_test: float
    mae: float
    mape_pct: Optional[float] = None
    n_train: int
    n_test: int


class TrainModelResponse(BaseModel):
    model_ids: list[int]
    technology: str
    feed_type: str
    targets_trained: list[str]
    metrics: dict[str, TargetMetrics]
    extracted_sensitivities: dict[str, float]
