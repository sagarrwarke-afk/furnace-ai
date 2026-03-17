"""Sensitivity config CRUD with audit logging."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.furnace import SensitivityConfig, AuditLog


def get_all_sensitivities(db: Session) -> list[dict]:
    """Return all sensitivities grouped by (technology, feed_type)."""
    rows = db.query(SensitivityConfig).order_by(
        SensitivityConfig.technology,
        SensitivityConfig.feed_type,
        SensitivityConfig.parameter,
    ).all()

    groups: dict[tuple, list] = {}
    for r in rows:
        key = (r.technology, r.feed_type)
        groups.setdefault(key, []).append({
            "id": r.id,
            "technology": r.technology,
            "feed_type": r.feed_type,
            "parameter": r.parameter,
            "sensitivity_type": r.sensitivity_type,
            "value": float(r.value),
            "unit": r.unit,
            "source": r.source,
            "updated_at": r.updated_at,
        })

    return [
        {"technology": k[0], "feed_type": k[1], "sensitivities": v}
        for k, v in groups.items()
    ]


def update_sensitivity(db: Session, sens_id: int, new_value: float) -> dict:
    """Update a single sensitivity value and log to audit."""
    row = db.query(SensitivityConfig).filter(SensitivityConfig.id == sens_id).first()
    if not row:
        raise ValueError(f"Sensitivity {sens_id} not found")

    old_value = float(row.value)
    now = datetime.now(timezone.utc)

    row.value = new_value
    row.source = "manual"
    row.updated_at = now

    db.add(AuditLog(
        action="sensitivity_updated",
        entity_type="sensitivity_config",
        entity_id=str(sens_id),
        details={
            "technology": row.technology,
            "feed_type": row.feed_type,
            "parameter": row.parameter,
            "sensitivity_type": row.sensitivity_type,
            "old_value": old_value,
            "new_value": new_value,
        },
    ))
    db.commit()

    return {
        "id": row.id,
        "parameter": row.parameter,
        "old_value": old_value,
        "new_value": new_value,
        "updated_at": now,
    }
