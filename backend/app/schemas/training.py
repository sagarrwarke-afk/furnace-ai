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
    algorithm: str = "GradientBoostingRegressor"
    targets_trained: list[str]
    metrics: dict[str, TargetMetrics]
    extracted_sensitivities: dict[str, float]


# ---------------------------------------------------------------------------
# Benchmark schemas
# ---------------------------------------------------------------------------

class BenchmarkTargetMetrics(BaseModel):
    r2: float
    rmse: float
    mape_pct: float
    r2_train: float
    n_train: int
    n_test: int


class BenchmarkAlgorithmResult(BaseModel):
    algorithm: str
    metrics: dict[str, BenchmarkTargetMetrics]
    interpolation_r2: Optional[float] = None
    interpolation_mape: Optional[float] = None
    overall_score: float
    recommended: bool = False
    recommendation_reason: Optional[str] = None


class BenchmarkResponse(BaseModel):
    technology: str
    feed_type: str
    n_rows: int
    selected_algorithms: list[str]
    algorithms: list[BenchmarkAlgorithmResult]
    recommended_algorithm: str
    recommendation_reason: str
    grid_analysis: dict[str, int]
