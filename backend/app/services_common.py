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


def set_policy_config(db: Session, updates: dict, user_id: int | None) -> dict:
    cfg = get_policy_config(db)
    unknown = set(updates) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)}")
    new = {**cfg, **updates}
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
