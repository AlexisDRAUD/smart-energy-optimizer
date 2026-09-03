from __future__ import annotations

from app.core.contract import utc_iso
from app.db.models.alert import Alert
from app.db.models.prediction import Prediction
from app.db.models.site import Site
from app.db.models.user import User


def site_response(site: Site) -> dict[str, object]:
    return {
        "site_id": site.site_id,
        "site_type": site.site_type,
        "site_name": site.site_name,
        "location": site.location,
        "capacity_kw": site.capacity_kw,
        "status": site.status,
        "last_seen_at": utc_iso(site.last_seen_at),
    }


def alert_response(alert: Alert) -> dict[str, object]:
    return {
        "id": alert.id,
        "site_id": alert.site_id,
        "detected_at": utc_iso(alert.detected_at),
        "type": alert.type,
        "severity": alert.severity,
        "message": alert.message,
        "value": alert.value,
        "threshold_value": alert.threshold_value,
        "status": alert.status,
        "acknowledged_at": utc_iso(alert.acknowledged_at),
    }


def prediction_response(prediction: Prediction) -> dict[str, object]:
    return {
        "site_id": prediction.site_id,
        "predicted_at": utc_iso(prediction.predicted_at),
        "target_at": utc_iso(prediction.target_at),
        "horizon_minutes": prediction.horizon_minutes,
        "predicted_kwh": prediction.predicted_kwh,
        "model_version": prediction.model_version,
        "actual_kwh": prediction.actual_kwh,
        "absolute_error": prediction.absolute_error,
    }


def user_response(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": utc_iso(user.created_at),
    }
