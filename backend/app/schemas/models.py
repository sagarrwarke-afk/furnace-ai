from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ModelItem(BaseModel):
    id: int
    model_name: str
    technology: str
    feed_type: str
    target: str
    algorithm: str
    hyperparams: Optional[dict] = None
    metrics: Optional[dict] = None
    active: bool
    trained_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ModelListResponse(BaseModel):
    models: list[ModelItem]


class ActivateModelResponse(BaseModel):
    id: int
    model_name: str
    active: bool
    sensitivities_copied: int
