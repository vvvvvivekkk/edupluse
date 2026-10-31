"""Rule-based intervention eligibility (Algorithm 2). No ML involved.

Rules are DATA, stored in system_config['eligibility_rules'] and editable by the administrator.
Each rule:
  {
    "id": "R1",
    "description": "...",
    "match": "all" | "any",
    "conditions": [ {"indicator": "<name>", "op": "<|<=|>|>=|==|!=|missing|present",
                     "value": <number|string>   OR   "ref": "<policy_config key>"} ],
    "interventions": ["targeted_material", ...]
  }
A rule whose conditions match makes its interventions eligible. Eligible set = union.

Indicators available to rules:
  state, topic_score, topic_mastery, attendance_pct, assignment_completion_pct,
  no_improvement_streak, latest_score

Exclusions (applied after the union):
  X1  An intervention type that produced 'No Improvement' in the student's most recent
      evaluated intervention is excluded while the no-improvement streak is active,
      unless removing it would leave the set empty.
  X2  Inactive intervention types are removed.

Fallback:
  F0  state == normal and no rule matched  -> empty set, "no intervention indicated".
  F1  state != normal and no rule matched  -> [targeted_practice, targeted_material]
      (the lowest-intensity academic supports), reason recorded as "fallback".
"""

DEFAULT_RULES = [
    {"id": "R1", "description": "Low assessment performance with weak topic mastery",
     "match": "all",
     "conditions": [{"indicator": "topic_score", "op": "<", "ref": "low_score_threshold"},
                    {"indicator": "topic_mastery", "op": "<", "ref": "weak_mastery_threshold"}],
     "interventions": ["targeted_material", "targeted_practice"]},
    {"id": "R1b", "description": "Low assessment performance, topic mastery not yet measured",
     "match": "all",
     "conditions": [{"indicator": "topic_score", "op": "<", "ref": "low_score_threshold"},
                    {"indicator": "topic_mastery", "op": "missing"}],
     "interventions": ["targeted_material", "targeted_practice"]},
    {"id": "R2", "description": "Low assessment performance with reasonable topic mastery",
     "match": "all",
     "conditions": [{"indicator": "topic_score", "op": "<", "ref": "low_score_threshold"},
                    {"indicator": "topic_mastery", "op": ">=", "ref": "weak_mastery_threshold"}],
     "interventions": ["targeted_practice"]},
    {"id": "R3", "description": "Low engagement or incomplete assignments",
     "match": "any",
     "conditions": [{"indicator": "attendance_pct", "op": "<", "ref": "low_attendance_threshold"},
                    {"indicator": "assignment_completion_pct", "op": "<", "ref": "low_completion_threshold"}],
     "interventions": ["study_plan"]},
    {"id": "R4", "description": "Repeated lack of improvement after suitable interventions",
     "match": "all",
     "conditions": [{"indicator": "no_improvement_streak", "op": ">=", "ref": "no_improvement_streak"}],
     "interventions": ["faculty_support", "targeted_material", "study_plan"]},
    {"id": "R5", "description": "High support need estimated by the model",
     "match": "all",
     "conditions": [{"indicator": "state", "op": "==", "value": "high_support_need"}],
     "interventions": ["faculty_support"]},
]

FALLBACK_ARMS = ["targeted_practice", "targeted_material"]
OPS = {"<", "<=", ">", ">=", "==", "!=", "missing", "present"}


class RuleConfigError(ValueError):
    pass


def validate_rules(rules: list[dict], known_arms: set[str]) -> None:
    if not isinstance(rules, list) or not rules:
        raise RuleConfigError("rules must be a non-empty list")
    ids = set()
    for r in rules:
        for key in ("id", "conditions", "interventions"):
            if key not in r:
                raise RuleConfigError(f"rule missing '{key}': {r}")
        if r["id"] in ids:
            raise RuleConfigError(f"duplicate rule id {r['id']}")
        ids.add(r["id"])
        if r.get("match", "all") not in ("all", "any"):
            raise RuleConfigError(f"rule {r['id']}: match must be 'all' or 'any'")
        for c in r["conditions"]:
            if c.get("op") not in OPS:
                raise RuleConfigError(f"rule {r['id']}: bad op {c.get('op')}")
            if c["op"] not in ("missing", "present") and "value" not in c and "ref" not in c:
                raise RuleConfigError(f"rule {r['id']}: condition needs 'value' or 'ref'")
        unknown = set(r["interventions"]) - known_arms
        if unknown:
            raise RuleConfigError(f"rule {r['id']}: unknown interventions {sorted(unknown)}")


def _check(cond: dict, ctx: dict, cfg: dict) -> bool:
    val = ctx.get(cond["indicator"])
    op = cond["op"]
    if op == "missing":
        return val is None
    if op == "present":
        return val is not None
    if val is None:
        return False  # an unknown indicator never satisfies a numeric comparison
    target = cfg[cond["ref"]] if "ref" in cond else cond["value"]
    return {"<": val < target, "<=": val <= target, ">": val > target, ">=": val >= target,
            "==": val == target, "!=": val != target}[op]


def evaluate_eligibility(ctx: dict, rules: list[dict], cfg: dict, active_arms: set[str],
                         last_failed_arm: str | None = None) -> dict:
    """Returns {"eligible": [...], "reasons": {arm: [rule descriptions]}, "matched_rules": [...],
                "exclusions": [...], "fallback": str|None}"""
    reasons: dict[str, list[str]] = {}
    matched = []
    for rule in rules:
        checks = [_check(c, ctx, cfg) for c in rule["conditions"]]
        ok = all(checks) if rule.get("match", "all") == "all" else any(checks)
        if ok:
            matched.append(rule["id"])
            for arm in rule["interventions"]:
                reasons.setdefault(arm, []).append(f"{rule['id']}: {rule['description']}")

    exclusions = []
    for arm in list(reasons):
        if arm not in active_arms:
            reasons.pop(arm)
            exclusions.append(f"X2: {arm} is inactive")
    if (last_failed_arm and last_failed_arm in reasons and len(reasons) > 1
            and ctx.get("no_improvement_streak", 0) > 0):
        reasons.pop(last_failed_arm)
        exclusions.append(f"X1: {last_failed_arm} just produced No Improvement")

    fallback = None
    if not reasons:
        if ctx.get("state") == "normal":
            fallback = "F0: state is Normal and no rule matched - no intervention indicated"
        else:
            fallback = "F1: no rule matched for a non-Normal state - lowest-intensity supports offered"
            for arm in FALLBACK_ARMS:
                if arm in active_arms:
                    reasons[arm] = [fallback]
    order = ["targeted_material", "targeted_practice", "study_plan", "faculty_support"]
    eligible = sorted(reasons, key=lambda a: order.index(a) if a in order else 99)
    return {"eligible": eligible, "reasons": reasons, "matched_rules": matched,
            "exclusions": exclusions, "fallback": fallback}
