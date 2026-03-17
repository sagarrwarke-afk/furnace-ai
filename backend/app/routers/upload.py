from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.furnace import UploadHistory, FurnaceSnapshot

router = APIRouter(prefix="/api", tags=["upload"])

REQUIRED_COLUMNS = [
    "furnace_id", "feed_rate", "cot", "shc", "cop", "cit", "tmt_max",
    "yield", "conversion", "coking_rate", "propylene", "feed_valve_pct",
    "fgv_pct", "damper_pct", "sec", "run_days_elapsed", "run_days_total",
    "status", "feed_ethane_pct", "feed_propane_pct",
]


@router.post("/upload")
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    contents = file.file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")

    # Validate columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing columns: {', '.join(missing)}",
        )

    now = datetime.now(timezone.utc)

    # Create upload record
    upload = UploadHistory(
        filename=file.filename,
        uploaded_by="user",
        uploaded_at=now,
        row_count=len(df),
        validation_ok=True,
        snapshot_ts=now,
    )
    db.add(upload)
    db.flush()  # get upload.id

    # Insert snapshot rows
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

    db.commit()

    # Build preview
    preview = df.head(10).to_dict(orient="records")
    return {
        "upload_id": upload.id,
        "filename": file.filename,
        "rows_inserted": rows_inserted,
        "uploaded_at": now.isoformat(),
        "preview": preview,
    }


@router.get("/upload/template")
def download_template():
    df = pd.DataFrame(columns=REQUIRED_COLUMNS)
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
