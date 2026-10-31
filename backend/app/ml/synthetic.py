"""Synthetic student-record generator (DOCUMENTED rules - see docs/DATA_AND_MODEL.md).

Why it is not a trivial copy of a rule:
  Each synthetic student has two hidden (latent) traits: `ability` and `engagement`.
  The observable features are noisy measurements of those traits. The TARGET label is
  derived from a separate, hidden *end-of-term outcome* (also noisy), which the model never
  sees. So the classifier has to infer a future outcome from noisy present indicators,
  rather than re-discovering the exact formula that produced its inputs.

  Results obtained on this data are SYNTHETIC-DATA EVALUATION ONLY and do not establish
  real-world predictive accuracy.
"""
import numpy as np
import pandas as pd

from .features import FEATURE_NAMES

LABELS = ["normal", "attention_needed", "high_support_need"]

# Target-label definition (end-of-term outcome score, 0-100):
#   outcome >= 60          -> normal
#   45 <= outcome < 60     -> attention_needed
#   outcome < 45           -> high_support_need
OUTCOME_NORMAL_MIN = 60.0
OUTCOME_ATTENTION_MIN = 45.0
MISSING_RATE = 0.08  # probability each optional feature is missing (MCAR)


def label_from_outcome(outcome: float) -> str:
    if outcome >= OUTCOME_NORMAL_MIN:
        return "normal"
    if outcome >= OUTCOME_ATTENTION_MIN:
        return "attention_needed"
    return "high_support_need"


def generate_students(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ability = rng.normal(0, 1, n)
    engagement = 0.4 * ability + np.sqrt(1 - 0.16) * rng.normal(0, 1, n)  # corr ~0.4

    def clip(x):
        return np.clip(x, 0, 100)

    previous = clip(65 + 12 * ability + rng.normal(0, 8, n))
    avg_score = clip(62 + 14 * ability + 4 * engagement + rng.normal(0, 7, n))
    latest = clip(avg_score + rng.normal(0, 9, n))
    attendance = clip(82 + 9 * engagement + rng.normal(0, 6, n))
    completion = clip(78 + 13 * engagement + 3 * ability + rng.normal(0, 9, n))
    practice = clip(60 + 13 * ability + 5 * engagement + rng.normal(0, 10, n))

    outcome = clip(58 + 13 * ability + 7 * engagement + rng.normal(0, 7, n))

    df = pd.DataFrame({
        "latest_score": latest.round(1),
        "avg_score": avg_score.round(1),
        "attendance_pct": attendance.round(1),
        "assignment_completion_pct": completion.round(1),
        "practice_accuracy_pct": practice.round(1),
        "previous_result_pct": previous.round(1),
    })
    # latest_score is a required feature, the others may be missing
    for col in FEATURE_NAMES:
        if col == "latest_score":
            continue
        mask = rng.random(n) < MISSING_RATE
        df.loc[mask, col] = np.nan
    df["outcome"] = outcome.round(1)
    df["label"] = [label_from_outcome(o) for o in outcome]
    # latent traits kept for the simulation study, never used as model inputs
    df["_ability"] = ability
    df["_engagement"] = engagement
    return df
