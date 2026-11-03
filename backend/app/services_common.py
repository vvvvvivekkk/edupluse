"""Small shared services: audit logging and runtime configuration."""
from sqlalchemy.orm import Session

from . import models
from .config import DEFAULT_CONFIG

ELIGIBILITY_RULES_KEY = "eligibility_rules"
POLICY_CONFIG_KEY = "policy_config"


def audit(db: Session, user_id: int | None, action: str, entity: str, entity_id=None, details=None):
    db.add(models.AuditLog(user_id=user_id, action=action, entity=entity,
                           entity_id=None if entity_id is None else str(entity_id),
                           details=details or {}))


def get_policy_config(db: Session) -> dict:
    row = db.get(models.SystemConfig, POLICY_CONFIG_KEY)
    cfg = dict(DEFAULT_CONFIG)
    if row:
        cfg.update(row.value)
    return cfg


INTEGER_KEYS = {"no_improvement_streak", "engagement_window_days"}
PERCENT_KEYS = {"low_score_threshold", "weak_mastery_threshold", "low_attendance_threshold",
                "low_completion_threshold"}


def _clean_value(key: str, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise ValueError(f"{key} must be a number")
    if key in INTEGER_KEYS:
        if value != int(value) or value < 1:
            raise ValueError(f"{key} must be a whole number of at least 1")
        return int(value)
    if key in PERCENT_KEYS and not 0 <= value <= 100:
        raise ValueError(f"{key} is a percentage and must be between 0 and 100")
    if key in ("positive_threshold", "partial_threshold") and not -1 <= value <= 1:
        raise ValueError(f"{key} applies to a reward in [-1, 1] and must be within that range")
    return float(value)


def set_policy_config(db: Session, updates: dict, user_id: int | None) -> dict:
    cfg = get_policy_config(db)
    unknown = set(updates) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)}")
    new = {**cfg, **{k: _clean_value(k, v) for k, v in updates.items()}}
    if not 0.0 <= float(new["reward_alpha"]) <= 1.0:
        raise ValueError("reward_alpha must be between 0 and 1")
    if not new["partial_threshold"] < new["positive_threshold"]:
        raise ValueError("partial_threshold must be lower than positive_threshold")
    if new["lints_lambda"] <= 0 or new["lints_v"] <= 0:
        raise ValueError("lints_lambda and lints_v must be positive")
    row = db.get(models.SystemConfig, POLICY_CONFIG_KEY)
    if row:
        row.value = new
        row.updated_by = user_id
    else:
        db.add(models.SystemConfig(key=POLICY_CONFIG_KEY, value=new, updated_by=user_id))
    audit(db, user_id, "update_config", "system_config", POLICY_CONFIG_KEY,
          {"before": cfg, "after": new})
    return new
