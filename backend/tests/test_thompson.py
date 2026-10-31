from collections import Counter

import numpy as np
import pytest

from app.engine.thompson import DIM, ArmParams, NoEligibleArmError, build_context, select_arm

ARMS = ["targeted_material", "targeted_practice", "study_plan", "faculty_support"]


def priors(lam=1.0):
    return {a: ArmParams.prior(DIM, lam) for a in ARMS}


def ctx():
    return build_context({"latest_score": 40, "attendance_pct": 70, "assignment_completion_pct": 60,
                          "practice_accuracy_pct": 50}, "attention_needed", 0)


def test_context_vector_shape_and_scaling():
    x = ctx()
    assert x.shape == (DIM,)
    assert x[0] == 1.0 and x[1] == pytest.approx(0.4) and x[5] == 1.0 and x[6] == 0.0
    assert np.all((x >= 0) & (x <= 1))


def test_missing_context_uses_fallback_not_zero():
    x = build_context({"latest_score": 40}, "normal", 0, fallback={"attendance_pct": 80})
    assert x[2] == pytest.approx(0.8)


def test_never_selects_ineligible():
    rng = np.random.default_rng(0)
    eligible = ["targeted_practice", "study_plan"]
    picks = Counter(select_arm(priors(), eligible, ctx(), 0.5, rng)[0] for _ in range(500))
    assert set(picks) <= set(eligible)
    assert len(picks) == 2  # with flat priors both eligible arms get explored


def test_empty_eligible_raises():
    with pytest.raises(NoEligibleArmError):
        select_arm(priors(), [], ctx(), 0.5, np.random.default_rng(0))


def test_update_matches_formula():
    p = ArmParams.prior(DIM, 2.0)
    x, r = ctx(), 0.4
    q = p.updated(x, r)
    np.testing.assert_allclose(q.A, 2.0 * np.eye(DIM) + np.outer(x, x))
    np.testing.assert_allclose(q.b, r * x)
    assert q.n == 1 and p.n == 0  # original untouched (immutable versions)


def test_posterior_converges_to_true_parameters():
    rng = np.random.default_rng(1)
    theta = rng.normal(0, 0.3, DIM)
    p = ArmParams.prior(DIM, 1.0)
    for _ in range(3000):
        x = np.r_[1.0, rng.random(4), np.eye(3)[rng.integers(3)][1:], rng.integers(0, 4) / 3]
        p = p.updated(x, float(x @ theta + rng.normal(0, 0.1)))
    mu, cov = p.posterior(0.5)
    np.testing.assert_allclose(mu, theta, atol=0.06)
    assert np.all(np.diag(cov) < 0.01)  # uncertainty shrinks with data


def test_exploitation_after_evidence():
    """If one arm has repeatedly earned high reward and another low, the good arm dominates."""
    rng = np.random.default_rng(2)
    params = priors()
    x = ctx()
    for _ in range(40):
        params["targeted_practice"] = params["targeted_practice"].updated(x, 0.8)
        params["study_plan"] = params["study_plan"].updated(x, -0.3)
    picks = Counter(select_arm(params, ["targeted_practice", "study_plan"], x, 0.5, rng)[0] for _ in range(300))
    assert picks["targeted_practice"] > 290


def test_exploration_of_uncertain_arm():
    """An unobserved arm still gets chosen sometimes against a moderately good, well-known arm."""
    rng = np.random.default_rng(3)
    params = priors()
    x = ctx()
    for _ in range(40):
        params["targeted_practice"] = params["targeted_practice"].updated(x, 0.1)
    picks = Counter(select_arm(params, ["targeted_practice", "targeted_material"], x, 0.5, rng)[0]
                    for _ in range(500))
    assert 20 < picks["targeted_material"] < 480


def test_same_seed_reproduces_selection():
    a = select_arm(priors(), ARMS, ctx(), 0.5, np.random.default_rng(123))
    b = select_arm(priors(), ARMS, ctx(), 0.5, np.random.default_rng(123))
    assert a == b
