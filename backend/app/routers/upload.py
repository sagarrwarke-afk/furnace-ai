from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.furnace import UploadHistory, FurnaceSnapshot, CoilSnapshot

router = APIRouter(prefix="/api", tags=["upload"])

# Columns present on every row (per-coil CSV: one row per coil)
COIL_COLUMNS = [
    "furnace_id", "coil", "feed", "cot", "shc", "cop", "cit",
    "thickness", "delta_hours",
]

# Furnace-level columns (repeated on each coil row, taken from first coil)
FURNACE_COLUMNS = [
    "tmt_max", "yield", "conversion", "coking_rate", "propylene",
    "feed_valve_pct", "fgv_pct", "damper_pct", "sec",
    "run_days_elapsed", "run_days_total", "status",
    "feed_ethane_pct", "feed_propane_pct",
]

# Legacy format (one row per furnace) required columns
LEGACY_REQUIRED_COLUMNS = [
    "furnace_id", "feed_rate", "cot", "shc", "cop", "cit", "tmt_max",
    "yield", "conversion", "coking_rate", "propylene", "feed_valve_pct",
    "fgv_pct", "damper_pct", "sec", "run_days_elapsed", "run_days_total",
    "status", "feed_ethane_pct", "feed_propane_pct",
]

# All columns in the new per-coil template
TEMPLATE_COLUMNS = COIL_COLUMNS + FURNACE_COLUMNS


def _is_per_coil_format(df: pd.DataFrame) -> bool:
    """Detect whether the CSV uses per-coil format (has 'coil' column)."""
    return "coil" in df.columns


@router.post("/upload")
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    contents = file.file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")

    now = datetime.now(timezone.utc)

    if _is_per_coil_format(df):
        return _upload_per_coil(df, file.filename, now, db)
    else:
        return _upload_legacy(df, file.filename, now, db)


def _upload_per_coil(
    df: pd.DataFrame, filename: str, now: datetime, db: Session,
) -> dict:
    """Handle per-coil CSV format (one row per coil)."""
    # Validate required coil columns
    missing = [c for c in COIL_COLUMNS if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing coil columns: {', '.join(missing)}",
        )

    # Validate furnace-level columns
    missing_furnace = [c for c in FURNACE_COLUMNS if c not in df.columns]
    if missing_furnace:
        raise HTTPException(
            status_code=400,
            detail=f"Missing furnace columns: {', '.join(missing_furnace)}",
        )

    # Create upload record
    upload = UploadHistory(
        filename=filename,
        uploaded_by="user",
        uploaded_at=now,
        row_count=len(df),
        validation_ok=True,
        snapshot_ts=now,
    )
    db.add(upload)
    db.flush()

    # Group by furnace_id
    grouped = df.groupby("furnace_id", sort=False)
    furnaces_inserted = 0
    coils_inserted = 0

    for fid, group in grouped:
        first_row = group.iloc[0]

        # Aggregate feed_rate as sum of per-coil feeds
        total_feed = group["feed"].sum()

        # Insert furnace-level snapshot (from first coil row + aggregated feed)
        snap = FurnaceSnapshot(
            upload_id=upload.id,
            snapshot_ts=now,
            furnace_id=str(fid),
            feed_rate=float(total_feed),
            cot=_num_row(first_row, "cot"),
            shc=_num_row(first_row, "shc"),
            cop=_num_row(first_row, "cop"),
            cit=_num_row(first_row, "cit"),
            tmt_max=_num_row(first_row, "tmt_max"),
            yield_=_num_row(first_row, "yield"),
            conversion=_num_row(first_row, "conversion"),
            coking_rate=_num_row(first_row, "coking_rate"),
            propylene=_num_row(first_row, "propylene"),
            feed_valve_pct=_num_row(first_row, "feed_valve_pct"),
            fgv_pct=_num_row(first_row, "fgv_pct"),
            damper_pct=_num_row(first_row, "damper_pct"),
            sec=_num_row(first_row, "sec"),
            run_days_elapsed=_int_row(first_row, "run_days_elapsed"),
            run_days_total=_int_row(first_row, "run_days_total"),
            status=str(first_row.get("status", "unknown")),
            feed_ethane_pct=_num_row(first_row, "feed_ethane_pct"),
            feed_propane_pct=_num_row(first_row, "feed_propane_pct"),
        )
        db.add(snap)
        furnaces_inserted += 1

        # Insert per-coil snapshots
        for _, row in group.iterrows():
            coil = CoilSnapshot(
                upload_id=upload.id,
                snapshot_ts=now,
                furnace_id=str(fid),
                coil_number=int(row["coil"]),
                feed=_num_row(row, "feed"),
                cot=_num_row(row, "cot"),
                shc=_num_row(row, "shc"),
                cop=_num_row(row, "cop"),
                cit=_num_row(row, "cit"),
                thickness=_num_row(row, "thickness"),
                delta_hours=_num_row(row, "delta_hours"),
            )
            db.add(coil)
            coils_inserted += 1

    db.commit()

    preview = df.head(10).to_dict(orient="records")
    return {
        "upload_id": upload.id,
        "filename": filename,
        "format": "per_coil",
        "furnaces_inserted": furnaces_inserted,
        "coils_inserted": coils_inserted,
        "rows_inserted": furnaces_inserted,
        "uploaded_at": now.isoformat(),
        "preview": preview,
    }


def _upload_legacy(
    df: pd.DataFrame, filename: str, now: datetime, db: Session,
) -> dict:
    """Handle legacy CSV format (one row per furnace)."""
    missing = [c for c in LEGACY_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {', '.join(missing)}",
        )

    upload = UploadHistory(
        filename=filename,
        uploaded_by="user",
        uploaded_at=now,
        row_count=len(df),
        validation_ok=True,
        snapshot_ts=now,
    )
    db.add(upload)
    db.flush()

    rows_inserted = 0
    for _, row in df.iterrows():
        snap = FurnaceSnapshot(
            upload_id=upload.id,
            snapshot_ts=now,
            furnace_id=str(row["furnace_id"]),
            feed_rate=_num(row, "feed_rate"),
            cot=_num(row, "cot"),
            shc=_num(row, "shc"),
            cop=_num(row, "cop"),
            cit=_num(row, "cit"),
            tmt_max=_num(row, "tmt_max"),
            yield_=_num(row, "yield"),
            conversion=_num(row, "conversion"),
            coking_rate=_num(row, "coking_rate"),
            propylene=_num(row, "propylene"),
            feed_valve_pct=_num(row, "feed_valve_pct"),
            fgv_pct=_num(row, "fgv_pct"),
            damper_pct=_num(row, "damper_pct"),
            sec=_num(row, "sec"),
            run_days_elapsed=_int(row, "run_days_elapsed"),
            run_days_total=_int(row, "run_days_total"),
            status=str(row.get("status", "unknown")),
            feed_ethane_pct=_num(row, "feed_ethane_pct"),
            feed_propane_pct=_num(row, "feed_propane_pct"),
        )
        db.add(snap)
        rows_inserted += 1

        # Parse optional coil thickness columns (coke_thickness_1..8)
        for i in range(1, 9):
            col = f"coke_thickness_{i}"
            if col in row.index:
                setattr(snap, col, _num(row, col))

    db.commit()

    preview = df.head(10).to_dict(orient="records")
    return {
        "upload_id": upload.id,
        "filename": filename,
        "format": "legacy",
        "rows_inserted": rows_inserted,
        "uploaded_at": now.isoformat(),
        "preview": preview,
    }


@router.get("/upload/template")
def download_template():
    """Download per-coil CSV template."""
    df = pd.DataFrame(columns=TEMPLATE_COLUMNS)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=furnace_template.csv"},
    )


@router.get("/snapshots")
def list_snapshots(db: Session = Depends(get_db)):
    uploads = (
        db.query(UploadHistory)
        .order_by(UploadHistory.uploaded_at.desc())
        .all()
    )
    return [
        {
            "upload_id": u.id,
            "filename": u.filename,
            "uploaded_by": u.uploaded_by,
            "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
            "row_count": u.row_count,
            "validation_ok": u.validation_ok,
        }
        for u in uploads
    ]


def _num(row, col):
    v = row.get(col)
    if pd.isna(v):
        return None
    return float(v)


def _int(row, col):
    v = row.get(col)
    if pd.isna(v):
        return None
    return int(v)


def _num_row(row, col):
    """Extract numeric value from a pandas Series row."""
    v = row.get(col) if hasattr(row, 'get') else row[col] if col in row.index else None
    if v is None or pd.isna(v):
        return None
    return float(v)


def _int_row(row, col):
    """Extract integer value from a pandas Series row."""
    v = row.get(col) if hasattr(row, 'get') else row[col] if col in row.index else None
    if v is None or pd.isna(v):
        return None
    return int(v)
