"""
Model training service: trains GBR soft-sensor models from CSV data,
pickles them to model_registry, and extracts sensitivities by perturbation.
"""

import io
import pickle
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.engine.furnace_runlength_forecasting import (
    FurnaceSoftSensorModels,
    INDEPENDENT_VARS,
    TARGET_VARS,
)
from app.models.furnace import ModelRegistry, SensitivityConfig, AuditLog


# Targets we extract sensitivities for
SENSITIVITY_TARGETS = ["yield_c2h4", "propylene", "conversion", "tmt", "coking_rate"]

# Maps engine target names → sensitivity_config parameter names
TARGET_TO_PARAM = {
    "yield_c2h4": "ethylene_yield",
    "propylene": "propylene",
    "conversion": "conversion",
    "tmt": "tmt",
    "coking_rate": "coking_rate",
}


def _build_base_point(df: pd.DataFrame) -> dict:
    """Return the median of each feature column as the base operating point."""
    return {col: float(df[col].median()) for col in INDEPENDENT_VARS if col in df.columns}


def _extract_sensitivities(
    model_set: FurnaceSoftSensorModels,
    base_point: dict,
) -> dict[str, float]:
    """
    Extract sensitivities by perturbation:
      - COT +1°C  → Δtarget / 1  = per_cot_degC
      - SHC +0.01 → Δtarget / 0.01 = per_shc_001 (for run_length proxy via coking_rate)
    Returns dict like {"ethylene_yield_per_cot": 0.218, "tmt_per_cot": 1.66, ...}
    """
    sensitivities = {}

    base_pred = model_set.predict(base_point)

    # --- COT perturbation (+1°C) ---
    perturbed = {**base_point, "cot": base_point["cot"] + 1.0}
    pert_pred = model_set.predict(perturbed)

    for target in SENSITIVITY_TARGETS:
        if target in base_pred and target in pert_pred:
            delta = pert_pred[target] - base_pred[target]
            param_name = TARGET_TO_PARAM[target]
            sensitivities[f"{param_name}_per_cot"] = round(delta, 4)

    # --- SHC perturbation (+0.01) ---
    perturbed_shc = {**base_point, "shc": base_point["shc"] + 0.01}
    shc_pred = model_set.predict(perturbed_shc)

    if "coking_rate" in base_pred and "coking_rate" in shc_pred:
        # Lower coking_rate → longer run. Approximate run_length sensitivity
        # from coking_rate change: if coking drops, run extends.
        delta_coking = shc_pred["coking_rate"] - base_pred["coking_rate"]
        sensitivities["coking_rate_per_shc_001"] = round(delta_coking, 4)

    # --- Feed ethane perturbation (+1%) ---
    if "feed_ethane_pct" in base_point:
        perturbed_eth = {
            **base_point,
            "feed_ethane_pct": base_point["feed_ethane_pct"] + 1.0,
            "feed_propane_pct": base_point.get("feed_propane_pct", 0) - 1.0,
        }
        eth_pred = model_set.predict(perturbed_eth)
        for target in SENSITIVITY_TARGETS:
            if target in base_pred and target in eth_pred:
                delta = eth_pred[target] - base_pred[target]
                param_name = TARGET_TO_PARAM[target]
                sensitivities[f"{param_name}_per_ethane_pct"] = round(delta, 4)

    # --- Thickness perturbation (+0.5 mm) ---
    if "thickness" in base_point:
        perturbed_thick = {**base_point, "thickness": base_point["thickness"] + 0.5}
        thick_pred = model_set.predict(perturbed_thick)
        for target in ["coking_rate", "tmt"]:
            if target in base_pred and target in thick_pred:
                delta = thick_pred[target] - base_pred[target]
                param_name = TARGET_TO_PARAM[target]
                sensitivities[f"{param_name}_per_thickness_05mm"] = round(delta, 4)

    return sensitivities


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Accept both the dedicated training CSV format AND the standard operating
    data upload template, renaming columns as needed so the engine always
    receives the canonical feature names.

    Upload template → canonical mapping:
      feed_rate  → feed
      tmt_max    → tmt       (also used as target)
      yield      → yield_c2h4  (the engine target name)
      coke_thickness_1..8 → thickness (mean of available columns)
    """
    df = df.copy()

    col_map = {
        "feed_rate": "feed",
        "tmt_max": "tmt",
    }
    for src, dst in col_map.items():
        if src in df.columns and dst not in df.columns:
            df.rename(columns={src: dst}, inplace=True)

    # yield → yield_c2h4 (engine target name)
    if "yield" in df.columns and "yield_c2h4" not in df.columns:
        df.rename(columns={"yield": "yield_c2h4"}, inplace=True)

    # Compute thickness as mean of coke_thickness_N columns
    if "thickness" not in df.columns:
        thick_cols = [c for c in df.columns if c.startswith("coke_thickness_")]
        if thick_cols:
            df["thickness"] = df[thick_cols].mean(axis=1)

    # Drop non-numeric / metadata columns that would confuse the model builder
    drop_cols = [
        "timestamp", "furnace_id", "status",
        "feed_valve_pct", "fgv_pct", "damper_pct",
        "run_days_elapsed", "run_days_total", "sec",
    ]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    return df


def train_model(
    db: Session,
    csv_bytes: bytes,
    technology: str,
    feed_type: str,
) -> dict:
    """
    Train GBR models from CSV data, pickle to model_registry,
    extract sensitivities, return metrics.
    """
    df = pd.read_csv(io.BytesIO(csv_bytes))

    # Accept upload-template column aliases so users can train directly
    # from their operating data CSV without reformatting
    df = _normalise_columns(df)

    if len(df) < 50:
        raise ValueError(
            f"CSV has only {len(df)} data rows — need at least 50 rows to train. "
            "Upload multiple snapshots or historical operating data."
        )

    model_name = f"{technology}-{feed_type}"
    model_set = FurnaceSoftSensorModels(
        name=model_name,
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
    )
    try:
        model_set.build(df, features=INDEPENDENT_VARS, targets=TARGET_VARS)
    except Exception as e:
        raise ValueError(f"Model training failed: {e}. Check that the CSV has numeric data in all feature columns.")

    if not model_set.models:
        raise ValueError("No targets had sufficient data to train (need >50 rows per target).")

    # Pickle entire model_set (models + scaler) as one blob
    blob = pickle.dumps({"models": model_set.models, "scalers": model_set.scalers, "feature_names": model_set.feature_names})

    now = datetime.now(timezone.utc)
    model_ids = []

    for target, model in model_set.models.items():
        metrics = model_set.metrics.get(target, {})
        reg = ModelRegistry(
            model_name=model_name,
            technology=technology,
            feed_type=feed_type,
            target=target,
            algorithm="GradientBoostingRegressor",
            hyperparams={
                "n_estimators": 200,
                "max_depth": 5,
                "learning_rate": 0.1,
                "subsample": 0.8,
            },
            metrics=metrics,
            model_blob=blob,
            active=False,
            trained_at=now,
        )
        db.add(reg)
        db.flush()
        model_ids.append(reg.id)

    # Extract sensitivities by perturbation
    base_point = _build_base_point(df)
    extracted_sens = _extract_sensitivities(model_set, base_point)

    # Audit
    db.add(AuditLog(
        action="model_trained",
        entity_type="model_registry",
        entity_id=str(model_ids),
        details={
            "technology": technology,
            "feed_type": feed_type,
            "targets": list(model_set.models.keys()),
            "extracted_sensitivities": extracted_sens,
        },
    ))
    db.commit()

    # Build response metrics dict
    resp_metrics = {}
    for target, m in model_set.metrics.items():
        resp_metrics[target] = {
            "r2_train": m["r2_train"],
            "r2_test": m["r2_test"],
            "mae": m["mae"],
            "mape_pct": m["mape_pct"],
            "n_train": m["n_train"],
            "n_test": m["n_test"],
        }

    return {
        "model_ids": model_ids,
        "technology": technology,
        "feed_type": feed_type,
        "targets_trained": list(model_set.models.keys()),
        "metrics": resp_metrics,
        "extracted_sensitivities": extracted_sens,
    }


def activate_model(db: Session, model_id: int) -> dict:
    """
    Activate a model: sets active=True, deactivates others for same
    (technology, feed_type, target), and copies extracted sensitivities
    to sensitivity_config.
    """
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        raise ValueError(f"Model {model_id} not found")

    # Deactivate siblings (same tech/feed/target)
    db.query(ModelRegistry).filter(
        ModelRegistry.technology == model.technology,
        ModelRegistry.feed_type == model.feed_type,
        ModelRegistry.target == model.target,
        ModelRegistry.id != model_id,
    ).update({"active": False})

    model.active = True

    # Copy COT sensitivity from model metrics to sensitivity_config
    # The model's metrics contain r2/mae etc. The sensitivities are extracted
    # at training time and stored in audit_log. We re-derive from the model blob.
    sens_copied = _copy_sensitivities_from_model(db, model)

    db.add(AuditLog(
        action="model_activated",
        entity_type="model_registry",
        entity_id=str(model_id),
        details={
            "technology": model.technology,
            "feed_type": model.feed_type,
            "target": model.target,
            "sensitivities_copied": sens_copied,
        },
    ))
    db.commit()

    return {
        "id": model.id,
        "model_name": model.model_name,
        "active": True,
        "sensitivities_copied": sens_copied,
    }


def _copy_sensitivities_from_model(db: Session, model: ModelRegistry) -> int:
    """
    Re-derive sensitivities from model blob by perturbation, then upsert
    into sensitivity_config table. Returns count of rows written.
    """
    if not model.model_blob:
        return 0

    data = pickle.loads(model.model_blob)
    model_set = FurnaceSoftSensorModels(name=model.model_name)
    model_set.models = data["models"]
    model_set.scalers = data["scalers"]
    model_set.feature_names = data["feature_names"]

    # Build a plausible base point from feature means embedded in the scaler
    scaler = model_set.scalers.get("X")
    if scaler is None:
        return 0

    base_point = dict(zip(model_set.feature_names, scaler.mean_))
    extracted = _extract_sensitivities(model_set, base_point)

    # Map extracted keys to sensitivity_config rows
    # e.g. "ethylene_yield_per_cot" → (technology, feed_type, "ethylene_yield", "per_cot_degC")
    count = 0
    now = datetime.now(timezone.utc)

    for key, value in extracted.items():
        # Parse key: "<param>_per_cot" or "<param>_per_ethane_pct" etc.
        if "_per_cot" in key:
            param = key.replace("_per_cot", "")
            sens_type = "per_cot_degC"
        elif "_per_shc_001" in key:
            param = key.replace("_per_shc_001", "")
            sens_type = "per_shc_001"
        elif "_per_ethane_pct" in key:
            param = key.replace("_per_ethane_pct", "")
            sens_type = "per_ethane_pct"
        elif "_per_thickness_05mm" in key:
            param = key.replace("_per_thickness_05mm", "")
            sens_type = "per_thickness_05mm"
        else:
            continue

        existing = db.query(SensitivityConfig).filter(
            SensitivityConfig.technology == model.technology,
            SensitivityConfig.feed_type == model.feed_type,
            SensitivityConfig.parameter == param,
            SensitivityConfig.sensitivity_type == sens_type,
        ).first()

        if existing:
            existing.value = value
            existing.source = "model"
            existing.updated_at = now
        else:
            db.add(SensitivityConfig(
                technology=model.technology,
                feed_type=model.feed_type,
                parameter=param,
                sensitivity_type=sens_type,
                value=value,
                source="model",
                updated_at=now,
            ))
        count += 1

    return count


def list_models(db: Session) -> list[dict]:
    """List all models with metrics and active status."""
    rows = db.query(ModelRegistry).order_by(ModelRegistry.trained_at.desc()).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "model_name": r.model_name,
            "technology": r.technology,
            "feed_type": r.feed_type,
            "target": r.target,
            "algorithm": r.algorithm or "GradientBoostingRegressor",
            "hyperparams": r.hyperparams,
            "metrics": r.metrics,
            "active": r.active,
            "trained_at": r.trained_at,
            "created_at": r.created_at,
        })
    return result
