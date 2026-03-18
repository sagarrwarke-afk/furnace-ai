"""
Model training service: benchmarks multiple algorithms, trains production
soft-sensor models, pickles to model_registry, and extracts sensitivities.

Supports: Ridge, RandomForest, GradientBoosting, XGBoost, LightGBM.
Uses per-coil prediction: simulation data is per-coil, furnace-level
predictions divide feed by num_coils and aggregate (TMT=MAX, yield=MEAN).
"""

import io
import pickle
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.engine.model_benchmark import (
    ModelBenchmark,
    BASE_FEATURES,
    TARGETS,
)
from app.models.furnace import ModelRegistry, SensitivityConfig, AuditLog, FurnaceConfig, CoilSnapshot


# Targets we extract sensitivities for
SENSITIVITY_TARGETS = ["yield_c2h4", "propylene", "conversion", "tmt", "coking_rate"]

# Maps engine target names -> sensitivity_config parameter names
TARGET_TO_PARAM = {
    "yield_c2h4": "ethylene_yield",
    "propylene": "propylene",
    "conversion": "conversion",
    "tmt": "tmt",
    "coking_rate": "coking_rate",
}


def _build_base_point(df: pd.DataFrame) -> dict:
    """Return the median of each feature column as the base operating point."""
    return {col: float(df[col].median()) for col in BASE_FEATURES if col in df.columns}


def _extract_sensitivities_from_model_dict(
    model_dict: dict,
    base_point: dict,
) -> dict[str, float]:
    """
    Extract sensitivities by perturbation using the new model_dict format.
    """
    sensitivities = {}

    base_pred = ModelBenchmark.predict(model_dict, base_point)

    # --- COT perturbation (+1 deg C) ---
    perturbed = {**base_point, "cot": base_point["cot"] + 1.0}
    pert_pred = ModelBenchmark.predict(model_dict, perturbed)

    for target in SENSITIVITY_TARGETS:
        if target in base_pred and target in pert_pred:
            delta = pert_pred[target] - base_pred[target]
            param_name = TARGET_TO_PARAM[target]
            sensitivities[f"{param_name}_per_cot"] = round(delta, 4)

    # --- SHC perturbation (+0.01) ---
    perturbed_shc = {**base_point, "shc": base_point["shc"] + 0.01}
    shc_pred = ModelBenchmark.predict(model_dict, perturbed_shc)

    if "coking_rate" in base_pred and "coking_rate" in shc_pred:
        delta_coking = shc_pred["coking_rate"] - base_pred["coking_rate"]
        sensitivities["coking_rate_per_shc_001"] = round(delta_coking, 4)

    # --- Feed ethane perturbation (+1%) ---
    if "feed_ethane_pct" in base_point:
        perturbed_eth = {
            **base_point,
            "feed_ethane_pct": base_point["feed_ethane_pct"] + 1.0,
            "feed_propane_pct": base_point.get("feed_propane_pct", 0) - 1.0,
        }
        eth_pred = ModelBenchmark.predict(model_dict, perturbed_eth)
        for target in SENSITIVITY_TARGETS:
            if target in base_pred and target in eth_pred:
                delta = eth_pred[target] - base_pred[target]
                param_name = TARGET_TO_PARAM[target]
                sensitivities[f"{param_name}_per_ethane_pct"] = round(delta, 4)

    # --- Thickness perturbation (+0.5 mm) ---
    if "thickness" in base_point:
        perturbed_thick = {**base_point, "thickness": base_point["thickness"] + 0.5}
        thick_pred = ModelBenchmark.predict(model_dict, perturbed_thick)
        for target in ["coking_rate", "tmt"]:
            if target in base_pred and target in thick_pred:
                delta = thick_pred[target] - base_pred[target]
                param_name = TARGET_TO_PARAM[target]
                sensitivities[f"{param_name}_per_thickness_05mm"] = round(delta, 4)

    return sensitivities


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Accept both the dedicated training CSV format AND the standard operating
    data upload template, renaming columns as needed.
    """
    df = df.copy()

    col_map = {
        "feed_rate": "feed",
        "tmt_max": "tmt",
    }
    for src, dst in col_map.items():
        if src in df.columns and dst not in df.columns:
            df.rename(columns={src: dst}, inplace=True)

    if "yield" in df.columns and "yield_c2h4" not in df.columns:
        df.rename(columns={"yield": "yield_c2h4"}, inplace=True)

    if "thickness" not in df.columns:
        thick_cols = [c for c in df.columns if c.startswith("coke_thickness_")]
        if thick_cols:
            df["thickness"] = df[thick_cols].mean(axis=1)

    drop_cols = [
        "timestamp", "furnace_id", "status",
        "feed_valve_pct", "fgv_pct", "damper_pct",
        "run_days_elapsed", "run_days_total", "sec",
    ]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    return df


# ---------------------------------------------------------------------------
# Benchmark models (compare algorithms)
# ---------------------------------------------------------------------------

def benchmark_models(
    db: Session,
    csv_bytes: bytes,
    technology: str,
    feed_type: str,
    selected_algorithms: list[str],
) -> dict:
    """
    Benchmark user-selected algorithms on the provided CSV data.
    Returns comparison metrics + recommendation.
    """
    df = pd.read_csv(io.BytesIO(csv_bytes))
    df = _normalise_columns(df)

    if len(df) < 50:
        raise ValueError(
            f"CSV has only {len(df)} rows -- need at least 50 to benchmark."
        )

    # Run benchmark
    bench_results = ModelBenchmark.run_benchmark(df, selected_algorithms)

    # Run interpolation test
    interp_results = ModelBenchmark.run_interpolation_test(df, selected_algorithms)

    # Grid analysis
    grid = ModelBenchmark.analyze_grid(df)

    # Recommendation
    recommended, reason, scores = ModelBenchmark.recommend(bench_results, interp_results)

    # Build response
    algorithms_list = []
    for algo_name in selected_algorithms:
        algo_metrics = bench_results.get(algo_name, {})
        interp = interp_results.get(algo_name, {})

        algorithms_list.append({
            "algorithm": algo_name,
            "metrics": algo_metrics,
            "interpolation_r2": interp.get("mean_r2"),
            "interpolation_mape": interp.get("mean_mape"),
            "overall_score": scores.get(algo_name, 0.0),
            "recommended": algo_name == recommended,
            "recommendation_reason": reason if algo_name == recommended else None,
        })

    # Sort by score descending
    algorithms_list.sort(key=lambda x: x["overall_score"], reverse=True)

    return {
        "technology": technology,
        "feed_type": feed_type,
        "n_rows": len(df),
        "selected_algorithms": selected_algorithms,
        "algorithms": algorithms_list,
        "recommended_algorithm": recommended,
        "recommendation_reason": reason,
        "grid_analysis": grid,
    }


# ---------------------------------------------------------------------------
# Train production model
# ---------------------------------------------------------------------------

def train_model(
    db: Session,
    csv_bytes: bytes,
    technology: str,
    feed_type: str,
    algorithm: str = "Ridge",
) -> dict:
    """
    Train a production soft-sensor model using the specified algorithm.
    Pickles to model_registry, extracts sensitivities.
    """
    df = pd.read_csv(io.BytesIO(csv_bytes))
    df = _normalise_columns(df)

    if len(df) < 50:
        raise ValueError(
            f"CSV has only {len(df)} data rows -- need at least 50 rows to train."
        )

    # Train production model
    model_dict = ModelBenchmark.train_production_model(df, algorithm)

    if not model_dict["models"]:
        raise ValueError("No targets had sufficient data to train.")

    # Pickle entire model_dict as one blob
    blob = pickle.dumps(model_dict)

    now = datetime.now(timezone.utc)
    model_name = f"{technology}-{feed_type}"
    model_ids = []

    for target, model in model_dict["models"].items():
        metrics = model_dict["metrics"].get(target, {})
        reg = ModelRegistry(
            model_name=model_name,
            technology=technology,
            feed_type=feed_type,
            target=target,
            algorithm=algorithm,
            hyperparams={"algorithm": algorithm},
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
    extracted_sens = _extract_sensitivities_from_model_dict(model_dict, base_point)

    # Audit
    db.add(AuditLog(
        action="model_trained",
        entity_type="model_registry",
        entity_id=str(model_ids),
        details={
            "technology": technology,
            "feed_type": feed_type,
            "algorithm": algorithm,
            "targets": list(model_dict["models"].keys()),
            "extracted_sensitivities": extracted_sens,
        },
    ))
    db.commit()

    # Build response metrics
    resp_metrics = {}
    for target, m in model_dict["metrics"].items():
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
        "algorithm": algorithm,
        "targets_trained": list(model_dict["models"].keys()),
        "metrics": resp_metrics,
        "extracted_sensitivities": extracted_sens,
    }


# ---------------------------------------------------------------------------
# Activate model
# ---------------------------------------------------------------------------

def activate_model(db: Session, model_id: int) -> dict:
    """
    Activate a model: sets active=True, deactivates others for same
    (technology, feed_type, target), and copies extracted sensitivities.
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

    sens_copied = _copy_sensitivities_from_model(db, model)

    db.add(AuditLog(
        action="model_activated",
        entity_type="model_registry",
        entity_id=str(model_id),
        details={
            "technology": model.technology,
            "feed_type": model.feed_type,
            "target": model.target,
            "algorithm": model.algorithm,
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
    """Re-derive sensitivities from model blob, upsert to sensitivity_config."""
    if not model.model_blob:
        return 0

    model_dict = pickle.loads(model.model_blob)

    # Build base point from scaler means
    scaler = model_dict.get("scaler")
    feature_names = model_dict.get("feature_names", [])
    base_features = model_dict.get("base_features", BASE_FEATURES)

    if scaler is None:
        return 0

    # Use scaler means for base features only
    base_point = {}
    for i, fname in enumerate(feature_names):
        if fname in base_features and i < len(scaler.mean_):
            base_point[fname] = float(scaler.mean_[i])

    # Fill any missing base features
    for bf in base_features:
        if bf not in base_point:
            base_point[bf] = 0.0

    extracted = _extract_sensitivities_from_model_dict(model_dict, base_point)

    count = 0
    now = datetime.now(timezone.utc)

    for key, value in extracted.items():
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


# ---------------------------------------------------------------------------
# Load active models (for optimizer/whatif/fleet)
# ---------------------------------------------------------------------------

def load_active_models(db: Session) -> dict[tuple[str, str], dict]:
    """
    Load active models from model_registry, grouped by (technology, feed_type).
    Returns {(tech, feed_type): unpickled_model_dict}.

    Only loads one blob per (tech, feed_type) since all targets share the same blob.
    """
    rows = db.query(ModelRegistry).filter(ModelRegistry.active == True).all()  # noqa: E712

    loaded = {}
    for r in rows:
        key = (r.technology, r.feed_type)
        if key in loaded:
            continue  # already loaded this tech+feed combo
        if not r.model_blob:
            continue
        try:
            model_dict = pickle.loads(r.model_blob)
            loaded[key] = model_dict
        except Exception:
            continue

    return loaded


# ---------------------------------------------------------------------------
# Load per-coil data from DB
# ---------------------------------------------------------------------------

def _load_coil_data(
    db: Session, upload_id: int, furnace_id: str,
) -> list[dict]:
    """
    Load per-coil X variables from coil_snapshot table.
    Returns list of dicts with keys: coil, feed, cot, shc, cop, cit, thickness, delta_hours.
    Returns empty list if no coil data exists (legacy upload).
    """
    rows = (
        db.query(CoilSnapshot)
        .filter(
            CoilSnapshot.upload_id == upload_id,
            CoilSnapshot.furnace_id == furnace_id,
        )
        .order_by(CoilSnapshot.coil_number)
        .all()
    )
    return [
        {
            "coil": r.coil_number,
            "feed": float(r.feed or 0),
            "cot": float(r.cot or 0),
            "shc": float(r.shc or 0),
            "cop": float(r.cop or 0),
            "cit": float(r.cit or 0),
            "thickness": float(r.thickness or 0),
            "delta_hours": float(r.delta_hours or 0),
        }
        for r in rows
    ]


def _coil_data_or_legacy(
    db: Session, upload_id: int, snap, num_coils: int,
) -> tuple[list[dict], float]:
    """
    Try loading per-coil data from coil_snapshot. If none exists (legacy upload),
    build coil_data from furnace snapshot with uniform X variables.
    Returns (coil_data, delta_hours).
    """
    coil_data = _load_coil_data(db, upload_id, snap.furnace_id)
    if coil_data:
        # Use max delta_hours across coils (should be same for all)
        delta_hours = max(cd.get("delta_hours", 0) for cd in coil_data)
        return coil_data, delta_hours

    # Legacy fallback: uniform X variables, thickness from coke_thickness_1..8
    feed_per_coil = float(snap.feed_rate or 0) / max(num_coils, 1)
    thicknesses = [
        float(snap.coke_thickness_1 or 0), float(snap.coke_thickness_2 or 0),
        float(snap.coke_thickness_3 or 0), float(snap.coke_thickness_4 or 0),
        float(snap.coke_thickness_5 or 0), float(snap.coke_thickness_6 or 0),
        float(snap.coke_thickness_7 or 0), float(snap.coke_thickness_8 or 0),
    ][:num_coils]

    coil_data = []
    for i, thick in enumerate(thicknesses):
        coil_data.append({
            "coil": i + 1,
            "feed": feed_per_coil,
            "cot": float(snap.cot or 0),
            "shc": float(snap.shc or 0),
            "cop": float(snap.cop or 0),
            "cit": float(snap.cit or 0),
            "thickness": thick,
            "delta_hours": 0.0,
        })
    return coil_data, 0.0


# ---------------------------------------------------------------------------
# Predict fleet values (model-calculated actuals)
# ---------------------------------------------------------------------------


def _get_coking_factor(db: Session, technology: str, feed_type: str) -> float:
    """Load coking factor from sensitivity_config table for thickness evolution."""
    row = db.query(SensitivityConfig).filter(
        SensitivityConfig.technology == technology,
        SensitivityConfig.feed_type == feed_type,
        SensitivityConfig.parameter == "coking_factor",
        SensitivityConfig.sensitivity_type == "thickness_evolution",
    ).first()
    return float(row.value) if row else 1.0


def predict_fleet_values(
    db: Session,
    snapshots: list,
    configs: dict,
    active_models: dict | None = None,
) -> dict[str, dict]:
    """
    For each furnace, use active model to predict soft sensor values
    from per-coil X inputs (feed, cot, shc, cop, cit, thickness, compositions).

    Returns {furnace_id: {yield_c2h4, tmt, coking_rate, conversion, propylene}}.
    """
    if active_models is None:
        active_models = load_active_models(db)

    if not active_models:
        return {}

    predictions = {}
    for s in snapshots:
        fid = s.furnace_id
        status_raw = (s.status or "").lower()
        if "decoke" in status_raw:
            continue

        cfg = configs.get(fid)
        tech = cfg.technology if cfg else "Lummus"
        feed_type = cfg.feed_type if cfg else (
            "Ethane" if float(s.feed_ethane_pct or 0) > 50 else "Propane"
        )
        num_coils = cfg.num_coils if cfg else 8

        key = (tech, feed_type)
        if key not in active_models:
            continue

        model_dict = active_models[key]

        # Load per-coil data (or build from legacy snapshot)
        coil_data, delta_hours = _coil_data_or_legacy(db, s.upload_id, s, num_coils)
        coking_factor = _get_coking_factor(db, tech, feed_type)

        try:
            pred = ModelBenchmark.predict_furnace(
                model_dict=model_dict,
                coil_data=coil_data,
                feed_ethane_pct=float(s.feed_ethane_pct or 0),
                feed_propane_pct=float(s.feed_propane_pct or 0),
                delta_hours=delta_hours,
                coking_factor=coking_factor,
            )
            # Remove per_coil detail for fleet-level response
            pred_summary = {k: v for k, v in pred.items() if k not in ("per_coil", "computed_thicknesses")}
            pred_summary["algorithm"] = model_dict.get("algorithm", "Unknown")
            predictions[fid] = pred_summary
        except Exception:
            continue

    return predictions


# ---------------------------------------------------------------------------
# Predict single furnace (for furnace detail page)
# ---------------------------------------------------------------------------

def predict_single_furnace(
    db: Session,
    snap,
    cfg,
) -> dict | None:
    """
    Predict soft sensor values for a single furnace using the active ML model.

    Returns prediction dict with per_coil detail and algorithm name,
    or None if no active model for this furnace's (technology, feed_type).
    """
    active_models = load_active_models(db)
    if not active_models:
        return None

    tech = cfg.technology if cfg else "Lummus"
    feed_type = cfg.feed_type if cfg else (
        "Ethane" if float(snap.feed_ethane_pct or 0) > 50 else "Propane"
    )
    num_coils = cfg.num_coils if cfg else 8

    key = (tech, feed_type)
    if key not in active_models:
        return None

    model_dict = active_models[key]

    # Load per-coil data (or build from legacy snapshot)
    coil_data, delta_hours = _coil_data_or_legacy(db, snap.upload_id, snap, num_coils)
    coking_factor = _get_coking_factor(db, tech, feed_type)

    try:
        pred = ModelBenchmark.predict_furnace(
            model_dict=model_dict,
            coil_data=coil_data,
            feed_ethane_pct=float(snap.feed_ethane_pct or 0),
            feed_propane_pct=float(snap.feed_propane_pct or 0),
            delta_hours=delta_hours,
            coking_factor=coking_factor,
        )
        pred["algorithm"] = model_dict.get("algorithm", "Unknown")
        return pred
    except Exception:
        return None


# ---------------------------------------------------------------------------
# List models
# ---------------------------------------------------------------------------

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
