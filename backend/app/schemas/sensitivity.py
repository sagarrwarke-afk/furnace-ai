from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SensitivityItem(BaseModel):
    id: int
    technology: str
    feed_type: str
    parameter: str
    sensitivity_type: str
    value: float
    unit: Optional[str] = None
    source: Optional[str] = None
    updated_at: Optional[datetime] = None


class SensitivityGroup(BaseModel):
    technology: str
    feed_type: str
    sensitivities: list[SensitivityItem]


class SensitivityListResponse(BaseModel):
    groups: list[SensitivityGroup]


class SensitivityUpdateRequest(BaseModel):
    id: int
    value: float


class SensitivityUpdateResponse(BaseModel):
    id: int
    parameter: str
    old_value: float
    new_value: float
    updated_at: datetime
