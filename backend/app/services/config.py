"""Economics and constraints config CRUD with audit logging."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.furnace import EconomicParam, ConstraintLimit, AuditLog


# ---------- Economics ----------

def get_economics(db: Session) -> list[dict]:
    rows = db.query(EconomicParam).order_by(EconomicParam.param_name).all()
    return [
        {
            "id": r.id,
            "param_name": r.param_name,
            "value": float(r.value),
            "unit": r.unit,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


def update_economics(db: Session, params: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    updated = []

    for p in params:
        row = db.query(EconomicParam).filter(
            EconomicParam.param_name == p["param_name"]
        ).first()
        if not row:
            raise ValueError(f"Economic param '{p['param_name']}' not found")

        old_value = float(row.value)
        row.value = p["value"]
        row.updated_at = now

        db.add(AuditLog(
            action="economic_param_updated",
            entity_type="economic_params",
            entity_id=str(row.id),
            details={
                "param_name": row.param_name,
                "old_value": old_value,
                "new_value": p["value"],
            },
        ))

        updated.append({
            "id": row.id,
            "param_name": row.param_name,
            "value": float(row.value),
            "unit": row.unit,
            "updated_at": now,
        })

    db.commit()
    return updated


# ---------- Constraints ----------

def get_constraints(db: Session) -> list[dict]:
    rows = db.query(ConstraintLimit).order_by(ConstraintLimit.constraint_name).all()
    return [
        {
            "id": r.id,
            "constraint_name": r.constraint_name,
            "limit_value": float(r.limit_value),
            "unit": r.unit,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


def update_constraints(db: Session, constraints: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    updated = []

    for c in constraints:
        row = db.query(ConstraintLimit).filter(
            ConstraintLimit.constraint_name == c["constraint_name"]
        ).first()
        if not row:
            raise ValueError(f"Constraint '{c['constraint_name']}' not found")

        old_value = float(row.limit_value)
        row.limit_value = c["limit_value"]
        row.updated_at = now

        db.add(AuditLog(
            action="constraint_updated",
            entity_type="constraint_limits",
            entity_id=str(row.id),
            details={
                "constraint_name": row.constraint_name,
                "old_value": old_value,
                "new_value": c["limit_value"],
            },
        ))

        updated.append({
            "id": row.id,
            "constraint_name": row.constraint_name,
            "limit_value": float(row.limit_value),
            "unit": row.unit,
            "updated_at": now,
        })

    db.commit()
    return updated
