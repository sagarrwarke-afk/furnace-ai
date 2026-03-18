"""
Service layer for fleet optimization.

Reads furnace snapshots, config, sensitivities, economics, and constraints
from DB, builds the fleet dict expected by FleetOptimizer, runs the engine,
and persists results.

When an active ML model exists for a furnace's (technology, feed_type),
the what-if simulator uses model.predict_furnace() for per-coil prediction
instead of fixed sensitivities.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.furnace import (
    UploadHistory, FurnaceSnapshot, FurnaceConfig,
    SensitivityConfig, EconomicParam, ConstraintLimit,
    CrossFeedConfig, DownstreamStatus, OptimizerResult,
)
from app.engine.furnace_runlength_forecasting import (
    FleetOptimizer, EconomicGainsCalculator,
)
from app.engine.model_benchmark import ModelBenchmark
from app.services.training import load_active_models


def _f(v) -> float:
    """Convert Numeric/Decimal to float, defaulting to 0."""
    if v is None:
        return 0.0
    return float(v)


def resolve_upload_id(upload_id: str | int, db: Session) -> int:
    if str(upload_id) == "latest":
        latest = (
            db.query(UploadHistory)
            .order_by(UploadHistory.uploaded_at.desc())
            .first()
        )
        if not latest:
            raise ValueError("No uploads found")
        return latest.id
    return int(upload_id)


def load_economic_params(db: Session) -> dict:
    """Load economic params from DB into a dict keyed by param_name."""
    rows = db.query(EconomicParam).all()
    return {r.param_name: _f(r.value) for r in rows}


def load_constraints(db: Session) -> dict:
    """Load constraint limits from DB."""
    rows = db.query(ConstraintLimit).all()
    return {r.constraint_name: _f(r.limit_value) for r in rows}


def load_sensitivities(db: Session) -> dict:
    """
    Load sensitivity_config rows into nested dict:
    {(technology, feed_type): {parameter: value}}
    """
    rows = db.query(SensitivityConfig).all()
    result = {}
    for r in rows:
        key = (r.technology, r.feed_type, r.sensitivity_type)
        if key not in result:
            result[key] = {}
        result[key][r.parameter] = _f(r.value)
    return result


def load_cross_feed(db: Session) -> dict:
    """Load cross-feed fractions from DB."""
    rows = db.query(CrossFeedConfig).all()
    return {
        r.source_type: {
            "ethane_frac": _f(r.ethane_frac),
            "propane_frac": _f(r.propane_frac),
            "other_frac": _f(r.other_frac),
        }
        for r in rows
    }


def build_fleet_dict(
    snapshots: list[FurnaceSnapshot],
    configs: dict[str, FurnaceConfig],
) -> dict:
    """
    Convert DB rows into the fleet dict format expected by FleetOptimizer.

    The engine expects per-furnace dicts with keys:
    fr, cot, shc, yield, conv, prop_yld, sec, runDays, runTotal,
    tmtMax, fgv, feed, tech, status, feed_ethane_pct, feed_propane_pct, etc.
    """
    fleet = {}
    for s in snapshots:
        fid = s.furnace_id
        cfg = configs.get(fid)
        status_raw = (s.status or "").lower()

        # Skip decoke furnaces
        if "decoke" in status_raw:
            continue

        # Determine online status for the engine
        if "protect" in status_raw:
            engine_status = "online"
        elif "online" in status_raw:
            engine_status = "online"
        else:
            continue

        tech = cfg.technology if cfg else "Lummus"
        feed_type = cfg.feed_type if cfg else (
            "Ethane" if _f(s.feed_ethane_pct) > 50 else "Propane"
        )

        # Average coke thickness across coils
        thicknesses = [
            _f(s.coke_thickness_1), _f(s.coke_thickness_2),
            _f(s.coke_thickness_3), _f(s.coke_thickness_4),
            _f(s.coke_thickness_5), _f(s.coke_thickness_6),
            _f(s.coke_thickness_7), _f(s.coke_thickness_8),
        ]
        avg_thickness = sum(thicknesses) / max(len([t for t in thicknesses if t > 0]), 1)

        fleet[fid] = {
            "fr": _f(s.feed_rate),
            "cot": _f(s.cot),
            "shc": _f(s.shc),
            "cop": _f(s.cop),
            "cit": _f(s.cit),
            "yield": _f(s.yield_),
            "conv": _f(s.conversion),
            "prop_yld": _f(s.propylene),
            "sec": _f(s.sec),
            "runDays": s.run_days_elapsed or 0,
            "runTotal": s.run_days_total or 120,
            "tmtMax": _f(s.tmt_max),
            "fgv": _f(s.fgv_pct),
            "feed_valve_pct": _f(s.feed_valve_pct),
            "damper_pct": _f(s.damper_pct),
            "feed": feed_type,
            "tech": tech,
            "status": engine_status,
            "feed_ethane_pct": _f(s.feed_ethane_pct),
            "feed_propane_pct": _f(s.feed_propane_pct),
            "thickness": avg_thickness,
            "coking_rate": _f(s.coking_rate),
        }
    return fleet


def run_optimizer(
    db: Session,
    upload_id: str | int = "latest",
    delta_fresh_ethane: float = 0.0,
    delta_fresh_propane: float = 0.0,
    ethane_feed_purity: float = 92.0,
    propane_feed_purity: float = 85.0,
    c2_splitter_load: float = 82.0,
) -> dict:
    """
    Main entry point: load data from DB, run FleetOptimizer, save results.
    Returns the full optimizer response dict.
    """
    uid = resolve_upload_id(upload_id, db)

    # Load snapshots
    snapshots = (
        db.query(FurnaceSnapshot)
        .filter(FurnaceSnapshot.upload_id == uid)
        .order_by(FurnaceSnapshot.furnace_id)
        .all()
    )
    if not snapshots:
        raise ValueError(f"No snapshot data for upload {uid}")

    # Load configs
    configs = {c.furnace_id: c for c in db.query(FurnaceConfig).all()}

    # Build fleet dict
    fleet = build_fleet_dict(snapshots, configs)
    if not fleet:
        raise ValueError("No online furnaces found in snapshot")

    # Load economics from DB
    econ_params = load_economic_params(db)
    econ = EconomicGainsCalculator(
        ethylene_price=econ_params.get("ethylene_price", 1050),
        propylene_price=econ_params.get("propylene_price", 900),
        fuel_gas_cost=econ_params.get("fuel_gas_cost", 8.5),
        feed_cost_ethane=econ_params.get("ethane_feed_cost", 350),
        feed_cost_propane=econ_params.get("propane_feed_cost", 320),
        decoke_cost=econ_params.get("decoke_cost", 150000),
        decoke_downtime_days=econ_params.get("decoke_downtime", 3),
    )

    # Load active ML models (if any) for model-based predictions
    active_models = load_active_models(db)

    # Build optimizer
    optimizer = FleetOptimizer(
        econ=econ,
        soft_sensor_models=active_models if active_models else None,
        ethane_feed_purity=ethane_feed_purity,
        propane_feed_purity=propane_feed_purity,
    )

    # Run optimization
    delta_fresh = {"Ethane": delta_fresh_ethane, "Propane": delta_fresh_propane}
    result = optimizer.optimize(fleet, delta_fresh=delta_fresh, c2_current=c2_splitter_load)

    # Enrich per-furnace results with furnace metadata
    per_furnace_enriched = {}
    for fid, actions in result["furnaces"].items():
        f = fleet[fid]
        cfg = configs.get(fid)
        per_furnace_enriched[fid] = {
            **actions,
            "furnace_id": fid,
            "technology": f["tech"],
            "feed_type": f["feed"],
            "baseline_feed": f["fr"],
            "baseline_cot": f["cot"],
            "baseline_shc": f["shc"],
            "baseline_yield": f["yield"],
            "baseline_conv": f["conv"],
            "baseline_tmt": f["tmtMax"],
            "run_days_elapsed": f["runDays"],
            "status": (
                "protect" if (f["runDays"] < 60 or f["tmtMax"] > 1060) else "healthy"
            ),
            "role": (
                "protect" if (f["runDays"] < 60 or f["tmtMax"] > 1060) else
                "push" if actions.get("dc", 0) > 0 else
                "absorb" if actions.get("dFeed", 0) > 0.01 else
                "hold"
            ),
        }

    fleet_totals = result["totals"]

    # Persist to DB
    opt_record = OptimizerResult(
        snapshot_id=uid,
        run_at=datetime.now(timezone.utc),
        delta_feed_eth=delta_fresh_ethane,
        delta_feed_prop=delta_fresh_propane,
        ethane_purity=ethane_feed_purity,
        propane_purity=propane_feed_purity,
        per_furnace=per_furnace_enriched,
        fleet_totals=fleet_totals,
        config_used={
            "economics": econ_params,
            "c2_splitter_load": c2_splitter_load,
        },
    )
    db.add(opt_record)
    db.commit()
    db.refresh(opt_record)

    return {
        "run_id": opt_record.id,
        "snapshot_id": uid,
        "run_at": opt_record.run_at.isoformat(),
        "inputs": {
            "delta_fresh_ethane": delta_fresh_ethane,
            "delta_fresh_propane": delta_fresh_propane,
            "ethane_feed_purity": ethane_feed_purity,
            "propane_feed_purity": propane_feed_purity,
            "c2_splitter_load": c2_splitter_load,
        },
        "per_furnace": per_furnace_enriched,
        "fleet_totals": fleet_totals,
    }


def run_whatif(
    db: Session,
    furnace_id: str,
    upload_id: str | int = "latest",
    delta_cot: float = 0.0,
    delta_shc: float = 0.0,
    delta_feed: float = 0.0,
    ethane_feed_purity: float = 92.0,
    propane_feed_purity: float = 85.0,
) -> dict:
    """
    Single-furnace what-if simulation.

    When an active ML model exists for this furnace's (technology, feed_type),
    uses ModelBenchmark.predict_furnace() for per-coil prediction.
    Otherwise falls back to sensitivity-based linear deltas.
    """
    uid = resolve_upload_id(upload_id, db)

    snap = (
        db.query(FurnaceSnapshot)
        .filter(
            FurnaceSnapshot.upload_id == uid,
            FurnaceSnapshot.furnace_id == furnace_id,
        )
        .first()
    )
    if not snap:
        raise ValueError(f"Furnace {furnace_id} not found in upload {uid}")

    cfg = db.query(FurnaceConfig).filter(
        FurnaceConfig.furnace_id == furnace_id
    ).first()

    tech = cfg.technology if cfg else "Lummus"
    feed_type = cfg.feed_type if cfg else (
        "Ethane" if _f(snap.feed_ethane_pct) > 50 else "Propane"
    )
    num_coils = cfg.num_coils if cfg else 8

    # Baseline values (from DCS / uploaded data)
    base_feed = _f(snap.feed_rate)
    base_cot = _f(snap.cot)
    base_shc = _f(snap.shc)
    base_sec = _f(snap.sec)
    base_run = snap.run_days_total or 120
    eth_pct = _f(snap.feed_ethane_pct)
    prop_pct = _f(snap.feed_propane_pct)

    # New operating conditions
    new_cot = base_cot + delta_cot
    new_shc = base_shc + delta_shc
    new_feed = base_feed + delta_feed

    # Per-coil thicknesses
    coil_thicknesses = [
        _f(snap.coke_thickness_1), _f(snap.coke_thickness_2),
        _f(snap.coke_thickness_3), _f(snap.coke_thickness_4),
        _f(snap.coke_thickness_5), _f(snap.coke_thickness_6),
        _f(snap.coke_thickness_7), _f(snap.coke_thickness_8),
    ][:num_coils]

    # Try model-based prediction
    active_models = load_active_models(db)
    model_key = (tech, feed_type)
    prediction_source = "sensitivity"

    if model_key in active_models:
        model_dict = active_models[model_key]
        try:
            # Baseline: predict from CURRENT X values (model-calculated)
            baseline_pred = ModelBenchmark.predict_furnace(
                model_dict=model_dict,
                furnace_feed_rate=base_feed,
                cot=base_cot,
                shc=base_shc,
                cop=_f(snap.cop),
                cit=_f(snap.cit),
                feed_ethane_pct=eth_pct,
                feed_propane_pct=prop_pct,
                coil_thicknesses=coil_thicknesses,
                num_coils=num_coils,
            )

            # Predicted: with adjusted operating conditions
            new_pred = ModelBenchmark.predict_furnace(
                model_dict=model_dict,
                furnace_feed_rate=new_feed,
                cot=new_cot,
                shc=new_shc,
                cop=_f(snap.cop),
                cit=_f(snap.cit),
                feed_ethane_pct=eth_pct,
                feed_propane_pct=prop_pct,
                coil_thicknesses=coil_thicknesses,
                num_coils=num_coils,
            )

            # Model-predicted baseline and new values
            base_yield = baseline_pred.get("yield_c2h4", _f(snap.yield_))
            base_conv = baseline_pred.get("conversion", _f(snap.conversion))
            base_prop = baseline_pred.get("propylene", _f(snap.propylene))
            base_tmt = baseline_pred.get("tmt", _f(snap.tmt_max))
            base_coking = baseline_pred.get("coking_rate", _f(snap.coking_rate))

            new_yield = new_pred.get("yield_c2h4", base_yield)
            new_conv = new_pred.get("conversion", base_conv)
            new_prop = new_pred.get("propylene", base_prop)
            new_tmt = new_pred.get("tmt", base_tmt)
            new_coking = new_pred.get("coking_rate", base_coking)

            # Run length still via sensitivity (models don't predict run_days)
            optimizer = FleetOptimizer(
                ethane_feed_purity=ethane_feed_purity,
                propane_feed_purity=propane_feed_purity,
            )
            furnace_dict = {
                "feed": feed_type, "tech": tech,
                "feed_ethane_pct": eth_pct,
            }
            sens = optimizer.get_sens(furnace_dict)
            new_run = max(30, round(base_run + delta_cot * sens["run_cot"]
                                    + (delta_shc * 100) * sens["run_shc"]))
            new_sec = base_sec + delta_cot * 0.02 - delta_shc * 5

            prediction_source = "model"
            algorithm_name = model_dict.get("algorithm", "Unknown")

        except Exception:
            # Fall through to sensitivity-based prediction on any error
            prediction_source = "sensitivity"
            active_models = {}  # force fallback below

    if prediction_source == "sensitivity":
        # Fallback: sensitivity-based linear deltas (original logic)
        optimizer = FleetOptimizer(
            ethane_feed_purity=ethane_feed_purity,
            propane_feed_purity=propane_feed_purity,
        )
        furnace_dict = {
            "feed": feed_type, "tech": tech,
            "feed_ethane_pct": eth_pct,
        }
        sens = optimizer.get_sens(furnace_dict)

        base_yield = _f(snap.yield_)
        base_conv = _f(snap.conversion)
        base_prop = _f(snap.propylene)
        base_tmt = _f(snap.tmt_max)
        base_coking = _f(snap.coking_rate)

        new_yield = base_yield + delta_cot * sens["yld_cot"]
        new_conv = base_conv + delta_cot * sens["conv_cot"]
        new_prop = base_prop + delta_cot * sens["prop_cot"]
        new_tmt = base_tmt + delta_cot * sens["tmt_cot"]
        new_sec = base_sec + delta_cot * 0.02 - delta_shc * 5
        new_run = max(30, round(base_run + delta_cot * sens["run_cot"]
                                + (delta_shc * 100) * sens["run_shc"]))
        new_coking = base_coking + delta_cot * sens["coking_cot"]
        algorithm_name = None

    # Economics comparison
    econ_params = load_economic_params(db)
    econ = EconomicGainsCalculator(
        ethylene_price=econ_params.get("ethylene_price", 1050),
        propylene_price=econ_params.get("propylene_price", 900),
        fuel_gas_cost=econ_params.get("fuel_gas_cost", 8.5),
        feed_cost_ethane=econ_params.get("ethane_feed_cost", 350),
        feed_cost_propane=econ_params.get("propane_feed_cost", 320),
        decoke_cost=econ_params.get("decoke_cost", 150000),
        decoke_downtime_days=econ_params.get("decoke_downtime", 3),
    )

    base_econ = econ.calc_furnace_economics(
        base_feed, base_yield, base_prop, base_sec, base_run, feed_type
    )
    new_econ = econ.calc_furnace_economics(
        new_feed, new_yield, new_prop, new_sec, new_run, feed_type
    )

    profit_delta = round(new_econ["net_margin_M"] - base_econ["net_margin_M"], 3)

    # Constraint checks
    constraints = load_constraints(db)
    tmt_warn = constraints.get("tmt_warning", 1060)
    tmt_alarm = constraints.get("tmt_alarm", 1075)

    return {
        "furnace_id": furnace_id,
        "technology": tech,
        "feed_type": feed_type,
        "prediction_source": prediction_source,
        "algorithm": algorithm_name,
        "inputs": {
            "delta_cot": delta_cot,
            "delta_shc": delta_shc,
            "delta_feed": delta_feed,
        },
        "baseline": {
            "feed_rate": base_feed,
            "cot": base_cot,
            "shc": base_shc,
            "yield": round(base_yield, 2),
            "conversion": round(base_conv, 2),
            "propylene": round(base_prop, 2),
            "tmt_max": round(base_tmt, 1),
            "sec": base_sec,
            "run_days": base_run,
            "coking_rate": round(base_coking, 3),
            "net_margin_M": base_econ["net_margin_M"],
        },
        "predicted": {
            "feed_rate": round(new_feed, 2),
            "cot": round(new_cot, 2),
            "shc": round(new_shc, 3),
            "yield": round(new_yield, 2),
            "conversion": round(new_conv, 2),
            "propylene": round(new_prop, 2),
            "tmt_max": round(new_tmt, 1),
            "sec": round(new_sec, 3),
            "run_days": new_run,
            "coking_rate": round(new_coking, 3),
            "net_margin_M": new_econ["net_margin_M"],
        },
        "deltas": {
            "yield": round(new_yield - base_yield, 3),
            "conversion": round(new_conv - base_conv, 3),
            "propylene": round(new_prop - base_prop, 3),
            "tmt_max": round(new_tmt - base_tmt, 1),
            "run_days": new_run - base_run,
            "profit_M": profit_delta,
            "ethylene_tpy": round(
                new_econ["annual_ethylene_tons"] - base_econ["annual_ethylene_tons"], 1
            ),
        },
        "warnings": {
            "tmt_warning": new_tmt > tmt_warn,
            "tmt_alarm": new_tmt > tmt_alarm,
        },
        "sensitivities_used": sens if prediction_source == "sensitivity" else None,
    }
