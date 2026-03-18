from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.furnace import UploadHistory, FurnaceSnapshot, FurnaceConfig
from app.services.training import load_active_models, predict_fleet_values

router = APIRouter(prefix="/api", tags=["fleet"])


def _resolve_upload_id(upload_id: str, db: Session) -> int:
    if upload_id == "latest":
        latest = (
            db.query(UploadHistory)
            .order_by(UploadHistory.uploaded_at.desc())
            .first()
        )
        if not latest:
            raise HTTPException(status_code=404, detail="No uploads found")
        return latest.id
    try:
        return int(upload_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="upload_id must be 'latest' or an integer")


def _snap_to_dict(s: FurnaceSnapshot, config: FurnaceConfig | None = None) -> dict:
    d = {
        "furnace_id": s.furnace_id,
        "feed_rate": _f(s.feed_rate),
        "cot": _f(s.cot),
        "shc": _f(s.shc),
        "cop": _f(s.cop),
        "cit": _f(s.cit),
        "tmt_max": _f(s.tmt_max),
        "yield": _f(s.yield_),
        "conversion": _f(s.conversion),
        "coking_rate": _f(s.coking_rate),
        "propylene": _f(s.propylene),
        "feed_valve_pct": _f(s.feed_valve_pct),
        "fgv_pct": _f(s.fgv_pct),
        "damper_pct": _f(s.damper_pct),
        "sec": _f(s.sec),
        "run_days_elapsed": s.run_days_elapsed,
        "run_days_total": s.run_days_total,
        "status": s.status,
        "feed_ethane_pct": _f(s.feed_ethane_pct),
        "feed_propane_pct": _f(s.feed_propane_pct),
    }
    if config:
        d["technology"] = config.technology
        d["feed_type"] = config.feed_type
        d["design_capacity"] = _f(config.design_capacity)
    return d


@router.get("/fleet")
def fleet_overview(
    upload_id: str = Query("latest"),
    db: Session = Depends(get_db),
):
    uid = _resolve_upload_id(upload_id, db)

    snapshots = (
        db.query(FurnaceSnapshot)
        .filter(FurnaceSnapshot.upload_id == uid)
        .order_by(FurnaceSnapshot.furnace_id)
        .all()
    )
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshot data for this upload")

    # Load furnace configs for technology/feed_type info
    configs = {c.furnace_id: c for c in db.query(FurnaceConfig).all()}

    # Load model predictions (if active models exist)
    try:
        active_models = load_active_models(db)
        model_predictions = predict_fleet_values(
            db, snapshots, configs, active_models
        ) if active_models else {}
    except Exception:
        model_predictions = {}

    ethane_furnaces = []
    propane_furnaces = []
    total_feed = 0.0
    total_ethylene = 0.0
    total_propylene = 0.0
    online_count = 0
    protect_count = 0
    decoke_count = 0

    for s in snapshots:
        cfg = configs.get(s.furnace_id)
        entry = _snap_to_dict(s, cfg)
        feed_type = cfg.feed_type if cfg else ("Ethane" if _f(s.feed_ethane_pct) and _f(s.feed_ethane_pct) > 50 else "Propane")

        # Ranking score: ethylene production = feed_rate * yield / 100
        feed = _f(s.feed_rate) or 0
        yld = _f(s.yield_) or 0
        entry["ethylene_tph"] = round(feed * yld / 100, 2)
        entry["propylene_tph"] = round(feed * (_f(s.propylene) or 0) / 100, 2)

        # Add model-predicted values (calculated from X inputs by soft sensor model)
        fid = s.furnace_id
        if fid in model_predictions:
            mp = model_predictions[fid]
            entry["model_predicted"] = {
                "yield": round(mp.get("yield_c2h4", 0), 2),
                "tmt": round(mp.get("tmt", 0), 1),
                "coking_rate": round(mp.get("coking_rate", 0), 3),
                "conversion": round(mp.get("conversion", 0), 2),
                "propylene": round(mp.get("propylene", 0), 2),
            }
        else:
            entry["model_predicted"] = None

        if feed_type == "Ethane":
            ethane_furnaces.append(entry)
        else:
            propane_furnaces.append(entry)

        total_feed += feed
        total_ethylene += entry["ethylene_tph"]
        total_propylene += entry["propylene_tph"]

        status = (s.status or "").lower()
        if "decoke" in status:
            decoke_count += 1
        elif "protect" in status:
            protect_count += 1
            online_count += 1
        elif "online" in status:
            online_count += 1

    # Rank each group by ethylene production descending
    ethane_furnaces.sort(key=lambda x: x["ethylene_tph"], reverse=True)
    propane_furnaces.sort(key=lambda x: x["ethylene_tph"], reverse=True)

    for i, f in enumerate(ethane_furnaces, 1):
        f["rank"] = i
    for i, f in enumerate(propane_furnaces, 1):
        f["rank"] = i

    return {
        "upload_id": uid,
        "has_active_models": bool(model_predictions),
        "kpis": {
            "total_feed_tph": round(total_feed, 2),
            "total_ethylene_tph": round(total_ethylene, 2),
            "total_propylene_tph": round(total_propylene, 2),
            "online_count": online_count,
            "protect_count": protect_count,
            "decoke_count": decoke_count,
            "total_furnaces": len(snapshots),
        },
        "ethane_furnaces": ethane_furnaces,
        "propane_furnaces": propane_furnaces,
    }


@router.get("/furnace/{furnace_id}")
def furnace_detail(
    furnace_id: str,
    upload_id: str = Query("latest"),
    db: Session = Depends(get_db),
):
    uid = _resolve_upload_id(upload_id, db)

    snap = (
        db.query(FurnaceSnapshot)
        .filter(
            FurnaceSnapshot.upload_id == uid,
            FurnaceSnapshot.furnace_id == furnace_id,
        )
        .first()
    )
    if not snap:
        raise HTTPException(status_code=404, detail=f"Furnace {furnace_id} not found in upload {uid}")

    cfg = db.query(FurnaceConfig).filter(FurnaceConfig.furnace_id == furnace_id).first()
    result = _snap_to_dict(snap, cfg)

    # Add coil thickness data
    result["coke_thickness"] = [
        _f(snap.coke_thickness_1), _f(snap.coke_thickness_2),
        _f(snap.coke_thickness_3), _f(snap.coke_thickness_4),
        _f(snap.coke_thickness_5), _f(snap.coke_thickness_6),
        _f(snap.coke_thickness_7), _f(snap.coke_thickness_8),
    ]

    # Constraint status
    result["constraints"] = {
        "feed_valve": {"value": _f(snap.feed_valve_pct), "limit": 85.0, "ok": (_f(snap.feed_valve_pct) or 0) <= 85.0},
        "fgv": {"value": _f(snap.fgv_pct), "limit": 85.0, "ok": (_f(snap.fgv_pct) or 0) <= 85.0},
        "damper": {"value": _f(snap.damper_pct), "limit": 88.0, "ok": (_f(snap.damper_pct) or 0) <= 88.0},
        "tmt_max": {"value": _f(snap.tmt_max), "alarm": 1075.0, "warning": 1060.0,
                     "ok": (_f(snap.tmt_max) or 0) <= 1060.0},
    }

    return result


def _f(v) -> float | None:
    if v is None:
        return None
    return float(v)
