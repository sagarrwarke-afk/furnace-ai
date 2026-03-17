from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EconomicParamItem(BaseModel):
    id: int
    param_name: str
    value: float
    unit: Optional[str] = None
    updated_at: Optional[datetime] = None


class EconomicParamsResponse(BaseModel):
    params: list[EconomicParamItem]


class EconomicParamUpdate(BaseModel):
    param_name: str
    value: float


class EconomicParamsUpdateRequest(BaseModel):
    params: list[EconomicParamUpdate]


class ConstraintItem(BaseModel):
    id: int
    constraint_name: str
    limit_value: float
    unit: Optional[str] = None
    updated_at: Optional[datetime] = None


class ConstraintsResponse(BaseModel):
    constraints: list[ConstraintItem]


class ConstraintUpdate(BaseModel):
    constraint_name: str
    limit_value: float


class ConstraintsUpdateRequest(BaseModel):
    constraints: list[ConstraintUpdate]
