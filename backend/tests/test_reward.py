import pytest

from app.engine import reward as rw


def test_learning_gain_basic():
    assert rw.learning_gain(40, 70) == pytest.approx(0.5)   # (70-40)/(100-40)
    assert rw.learning_gain(50, 50) == 0.0
    assert rw.learning_gain(80, 60) == pytest.approx(-1.0)   # (60-80)/20 = -1


def test_learning_gain_is_clipped():
    assert rw.learning_gain(90, 10) == -1.0                  # raw -8, clipped


def test_learning_gain_pre_100_edge_case():
    assert rw.learning_gain(100, 100) == 0.0                 # formula undefined -> no gain possible
    assert rw.learning_gain(100, 80) == pytest.approx(-0.2)  # drop from ceiling penalised


@pytest.mark.parametrize("pre,post", [(-1, 50), (50, 101), (None, 50), (50, None)])
def test_learning_gain_rejects_incomparable(pre, post):
    with pytest.raises(rw.ComparabilityError):
        rw.learning_gain(pre, post)


def test_engagement_uses_only_common_components():
    pre = {"attendance_pct": 60, "assignment_completion_pct": 50, "practice_activity_pct": 25}
    post = {"attendance_pct": None, "assignment_completion_pct": None, "practice_activity_pct": 75}
    e, used = rw.engagement_change(pre, post)
    assert used == ["practice_activity_pct"]
    assert e == pytest.approx(0.5)


def test_engagement_missing_returns_none():
    e, used = rw.engagement_change({"attendance_pct": None}, {"attendance_pct": 80})
    assert e is None and used == []


def test_combined_reward_and_fallback():
    r, a = rw.combined_reward(0.5, 0.1, 0.7)
    assert r == pytest.approx(0.7 * 0.5 + 0.3 * 0.1) and a == 0.7
    r, a = rw.combined_reward(0.5, None, 0.7)               # e missing -> r = g
    assert r == 0.5 and a == 1.0
    with pytest.raises(ValueError):
        rw.combined_reward(0.5, 0.1, 1.5)


@pytest.mark.parametrize("r,cat", [(0.30, "positive"), (0.9, "positive"), (0.29, "partial"),
                                   (0.05, "partial"), (0.049, "no_improvement"), (-0.5, "no_improvement")])
def test_classification_thresholds(r, cat):
    assert rw.classify(r, 0.30, 0.05) == cat
