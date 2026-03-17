from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, Text, DateTime, ForeignKey,
)
from sqlalchemy.sql import func

from app.database import Base


class UploadHistory(Base):
    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    uploaded_by = Column(String(100), default="system")
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    row_count = Column(Integer)
    validation_ok = Column(Boolean, default=True)
    validation_msg = Column(Text)
    snapshot_ts = Column(DateTime(timezone=True))


class FurnaceSnapshot(Base):
    __tablename__ = "furnace_snapshot"

    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("upload_history.id", ondelete="CASCADE"), nullable=False)
    snapshot_ts = Column(DateTime(timezone=True), nullable=False)
    furnace_id = Column(String(10), nullable=False)
    feed_rate = Column(Numeric(8, 2))
    cot = Column(Numeric(6, 2))
    shc = Column(Numeric(5, 3))
    cop = Column(Numeric(6, 2))
    cit = Column(Numeric(6, 2))
    tmt_max = Column(Numeric(6, 1))
    yield_ = Column("yield", Numeric(5, 2))
    conversion = Column(Numeric(5, 2))
    coking_rate = Column(Numeric(6, 3))
    propylene = Column(Numeric(5, 2))
    feed_valve_pct = Column(Numeric(5, 2))
    fgv_pct = Column(Numeric(5, 2))
    damper_pct = Column(Numeric(5, 2))
    sec = Column(Numeric(6, 3))
    run_days_elapsed = Column(Integer)
    run_days_total = Column(Integer)
    status = Column(String(30))
    feed_ethane_pct = Column(Numeric(6, 3))
    feed_propane_pct = Column(Numeric(6, 3))
    coke_thickness_1 = Column(Numeric(6, 3))
    coke_thickness_2 = Column(Numeric(6, 3))
    coke_thickness_3 = Column(Numeric(6, 3))
    coke_thickness_4 = Column(Numeric(6, 3))
    coke_thickness_5 = Column(Numeric(6, 3))
    coke_thickness_6 = Column(Numeric(6, 3))
    coke_thickness_7 = Column(Numeric(6, 3))
    coke_thickness_8 = Column(Numeric(6, 3))


class FurnaceConfig(Base):
    __tablename__ = "furnace_config"

    id = Column(Integer, primary_key=True)
    furnace_id = Column(String(10), nullable=False, unique=True)
    technology = Column(String(30), nullable=False)
    feed_type = Column(String(20), nullable=False)
    num_passes = Column(Integer, default=4)
    num_coils = Column(Integer, default=8)
    design_capacity = Column(Numeric(8, 2))
    max_cot = Column(Numeric(6, 1), default=860.0)
    min_cot = Column(Numeric(6, 1), default=800.0)
    max_feed_rate = Column(Numeric(8, 2))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
