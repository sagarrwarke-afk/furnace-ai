from sqlalchemy import (
    Column, Integer, SmallInteger, String, Numeric, Boolean, Text, DateTime,
    LargeBinary, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# INPUT TABLES (from Excel upload)
# =============================================================================

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


class CoilSnapshot(Base):
    __tablename__ = "coil_snapshot"

    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("upload_history.id", ondelete="CASCADE"), nullable=False)
    snapshot_ts = Column(DateTime(timezone=True), nullable=False)
    furnace_id = Column(String(10), nullable=False)
    coil_number = Column(SmallInteger, nullable=False)
    feed = Column(Numeric(8, 3))
    cot = Column(Numeric(6, 2))
    shc = Column(Numeric(5, 3))
    cop = Column(Numeric(6, 2))
    cit = Column(Numeric(6, 2))
    thickness = Column(Numeric(6, 3))
    coking_rate = Column(Numeric(8, 4))
    delta_hours = Column(Numeric(8, 2))


class DownstreamStatus(Base):
    __tablename__ = "downstream_status"

    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("upload_history.id", ondelete="CASCADE"), nullable=False)
    snapshot_ts = Column(DateTime(timezone=True), nullable=False)
    c2_splitter_load_pct = Column(Numeric(5, 2))
    cgc_suction_bar = Column(Numeric(5, 3))
    cgc_power_mw = Column(Numeric(8, 2))
    cgc_vhp_steam_tph = Column(Numeric(8, 3))


class FeedComposition(Base):
    __tablename__ = "feed_composition"

    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("upload_history.id", ondelete="CASCADE"), nullable=False)
    snapshot_ts = Column(DateTime(timezone=True), nullable=False)
    furnace_id = Column(String(10), nullable=False)
    ethane_pct = Column(Numeric(6, 3))
    propane_pct = Column(Numeric(6, 3))
    butane_pct = Column(Numeric(6, 3))
    other_pct = Column(Numeric(6, 3))


# =============================================================================
# CONFIG TABLES (editable from UI)
# =============================================================================

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


class SensitivityConfig(Base):
    __tablename__ = "sensitivity_config"
    __table_args__ = (
        UniqueConstraint("technology", "feed_type", "parameter", "sensitivity_type"),
    )

    id = Column(Integer, primary_key=True)
    technology = Column(String(30), nullable=False)
    feed_type = Column(String(20), nullable=False)
    parameter = Column(String(50), nullable=False)
    sensitivity_type = Column(String(20), nullable=False, default="per_cot_degC")
    value = Column(Numeric(10, 4), nullable=False)
    unit = Column(String(30))
    source = Column(String(30), default="manual")
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class EconomicParam(Base):
    __tablename__ = "economic_params"

    id = Column(Integer, primary_key=True)
    param_name = Column(String(50), nullable=False, unique=True)
    value = Column(Numeric(12, 4), nullable=False)
    unit = Column(String(30))
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ConstraintLimit(Base):
    __tablename__ = "constraint_limits"

    id = Column(Integer, primary_key=True)
    constraint_name = Column(String(50), nullable=False, unique=True)
    limit_value = Column(Numeric(10, 4), nullable=False)
    unit = Column(String(30))
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class CrossFeedConfig(Base):
    __tablename__ = "cross_feed_config"
    __table_args__ = (UniqueConstraint("source_type"),)

    id = Column(Integer, primary_key=True)
    source_type = Column(String(20), nullable=False)
    ethane_frac = Column(Numeric(5, 3), nullable=False)
    propane_frac = Column(Numeric(5, 3), nullable=False)
    other_frac = Column(Numeric(5, 3), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    technology = Column(String(30), nullable=False)
    feed_type = Column(String(20), nullable=False)
    target = Column(String(50), nullable=False)
    algorithm = Column(String(50), default="GradientBoostingRegressor")
    hyperparams = Column(JSONB)
    metrics = Column(JSONB)
    model_blob = Column(LargeBinary)
    active = Column(Boolean, default=False)
    trained_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# OUTPUT TABLES
# =============================================================================

class OptimizerResult(Base):
    __tablename__ = "optimizer_results"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("upload_history.id"))
    run_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    delta_feed_eth = Column(Numeric(8, 2), default=0)
    delta_feed_prop = Column(Numeric(8, 2), default=0)
    ethane_purity = Column(Numeric(6, 3))
    propane_purity = Column(Numeric(6, 3))
    per_furnace = Column(JSONB, nullable=False)
    fleet_totals = Column(JSONB, nullable=False)
    config_used = Column(JSONB)
    notes = Column(Text)


class SoftSensorPrediction(Base):
    __tablename__ = "soft_sensor_predictions"

    id = Column(Integer, primary_key=True)
    model_id = Column(Integer, ForeignKey("model_registry.id"))
    upload_id = Column(Integer, ForeignKey("upload_history.id"))
    furnace_id = Column(String(10), nullable=False)
    predicted_at = Column(DateTime(timezone=True), server_default=func.now())
    target = Column(String(50), nullable=False)
    predicted_value = Column(Numeric(10, 4))
    actual_value = Column(Numeric(10, 4))
    residual = Column(Numeric(10, 4))


class RunlengthForecast(Base):
    __tablename__ = "runlength_forecast"

    id = Column(Integer, primary_key=True)
    furnace_id = Column(String(10), nullable=False)
    forecast_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    day_number = Column(Integer, nullable=False)
    projected_tmt = Column(Numeric(6, 1))
    projected_coke = Column(Numeric(6, 3))
    projected_yield = Column(Numeric(5, 2))
    remaining_days = Column(Integer)
    confidence = Column(Numeric(4, 2))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(String(50))
    user_name = Column(String(100), default="system")
    details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
