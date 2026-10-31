import json

import pytest

from app.config import DEFAULT_CONFIG, MODEL_DIR
from app.engine.eligibility import DEFAULT_RULES, RuleConfigError, evaluate_eligibility, validate_rules
from app.ml.features import FeatureValidationError, validate_features
from app.ml.state_model import predict_state

ALL = {"targeted_material", "targeted_practice", "study_plan", "faculty_support"}


def ctx(**kw):
    base = {"state": "attention_needed", "topic_score": 80, "topic_mastery": 80, "attendance_pct": 90,
            "assignment_completion_pct": 90, "no_improvement_streak": 0}
    return {**base, **kw}


def elig(c, active=ALL, last_failed=None):
    return evaluate_eligibility(c, DEFAULT_RULES, DEFAULT_CONFIG, active, last_failed)


def test_low_score_weak_mastery():
    assert elig(ctx(topic_score=40, topic_mastery=40))["eligible"] == ["targeted_material", "targeted_practice"]


def test_low_score_reasonable_mastery():
    assert elig(ctx(topic_score=40, topic_mastery=70))["eligible"] == ["targeted_practice"]


def test_low_engagement():
    assert elig(ctx(attendance_pct=60))["eligible"] == ["study_plan"]
    assert elig(ctx(assignment_completion_pct=50))["eligible"] == ["study_plan"]


def test_repeated_no_improvement_adds_faculty_and_alternative():
    out = elig(ctx(topic_score=40, topic_mastery=70, no_improvement_streak=2), last_failed="targeted_practice")
    assert "faculty_support" in out["eligible"]
    assert "targeted_practice" not in out["eligible"]          # X1 exclusion of the arm that just failed
    assert any(e.startswith("X1") for e in out["exclusions"])


def test_missing_indicator_never_satisfies_comparison():
    out = elig(ctx(topic_score=None, topic_mastery=None))
    assert out["eligible"] == ["targeted_material", "targeted_practice"]  # F1 fallback, not a crash
    assert out["fallback"].startswith("F1")


def test_normal_state_no_intervention():
    out = elig(ctx(state="normal"))
    assert out["eligible"] == [] and out["fallback"].startswith("F0")


def test_inactive_types_removed():
    out = elig(ctx(topic_score=40, topic_mastery=40), active=ALL - {"targeted_material"})
    assert out["eligible"] == ["targeted_practice"]


def test_rule_validation():
    validate_rules(DEFAULT_RULES, ALL)
    with pytest.raises(RuleConfigError):
        validate_rules([{"id": "X", "conditions": [{"indicator": "a", "op": "~", "value": 1}],
                         "interventions": ["study_plan"]}], ALL)
    with pytest.raises(RuleConfigError):
        validate_rules([{"id": "X", "conditions": [], "interventions": ["teleport"]}], ALL)


# ---------------------------------------------------------------- model
def test_required_feature_missing_is_rejected():
    with pytest.raises(FeatureValidationError):
        validate_features({"latest_score": None, "attendance_pct": 80})


@pytest.mark.parametrize("bad", [120, -5, "80"])
def test_invalid_feature_values(bad):
    with pytest.raises(FeatureValidationError):
        validate_features({"latest_score": bad})


def test_prediction_reports_imputed_features():
    out = predict_state({"latest_score": 30, "avg_score": None, "attendance_pct": 60,
                         "assignment_completion_pct": None, "practice_accuracy_pct": 35, "previous_result_pct": 50})
    assert out["state"] in ("normal", "attention_needed", "high_support_need")
    assert set(out["imputed_features"]) == {"avg_score", "assignment_completion_pct"}
    assert abs(sum(out["probabilities"].values()) - 1) < 1e-3
    assert out["model_version"]


def test_monotone_sanity():
    weak = predict_state({"latest_score": 20, "avg_score": 25, "attendance_pct": 55, "assignment_completion_pct": 40,
                          "practice_accuracy_pct": 25, "previous_result_pct": 40})
    strong = predict_state({"latest_score": 92, "avg_score": 90, "attendance_pct": 97, "assignment_completion_pct": 100,
                            "practice_accuracy_pct": 90, "previous_result_pct": 88})
    assert weak["state"] == "high_support_need" and strong["state"] == "normal"


def test_model_card_has_separate_test_evaluation():
    card = json.loads((MODEL_DIR / "model_card.json").read_text())
    ds = card["dataset"]
    assert ds["train_size"] + ds["test_size"] == ds["n_students"]
    for k in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "roc_auc_ovr_macro", "confusion_matrix"):
        assert k in card["test_metrics"]
    assert "SYNTHETIC" in ds["source"]
    # RF should beat the majority baseline by a clear margin in CV
    sel = card["model_selection_cv"]
    assert sel["random_forest"]["cv_f1_macro_mean"] > sel["majority_baseline"]["cv_f1_macro_mean"] + 0.3
