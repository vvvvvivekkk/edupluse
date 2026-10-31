"""Linear Thompson Sampling (disjoint model, one linear reward model per intervention arm).

Model, for arm k and context vector x in R^d:
    reward = x . theta_k + noise

Prior:        theta_k ~ N(0, (v^2 / lambda) I)
Sufficient statistics per arm (after n observations (x_i, r_i)):
    A_k = lambda * I + sum_i x_i x_i^T          (d x d, precision matrix up to v^2)
    b_k = sum_i r_i x_i                          (d)
Posterior:    theta_k ~ N( mu_k = A_k^{-1} b_k ,  v^2 * A_k^{-1} )

Selection (one round):
    for each ELIGIBLE arm k: draw theta~_k from its posterior, score_k = x . theta~_k
    choose argmax_k score_k
    -> arms with few observations have wide posteriors, so they sometimes draw high scores
       (exploration); arms with consistently high observed reward have high mu_k (exploitation).

Update (after reward r for chosen arm k with context x):
    A_k <- A_k + x x^T ;  b_k <- b_k + r x
Only the chosen arm is updated. Ineligible arms are never scored.

Reference: Agrawal & Goyal (2013), "Thompson Sampling for Contextual Bandits with Linear Payoffs".
"""
from dataclasses import dataclass

import numpy as np

# Context vector definition (d = 8). All continuous values scaled to [0, 1].
CONTEXT_FEATURES = [
    "bias",                      # constant 1.0
    "latest_score",
    "attendance_pct",
    "assignment_completion_pct",
    "practice_accuracy_pct",
    "state_attention_needed",    # one-hot of the RF state (normal is the reference level)
    "state_high_support_need",
    "prior_no_improvement",      # min(streak, 3) / 3
]
DIM = len(CONTEXT_FEATURES)


def build_context(features: dict, state: str, no_improvement_streak: int,
                  fallback: dict | None = None) -> np.ndarray:
    """Map raw indicators to the context vector. Missing values use `fallback` (training medians)."""
    fallback = fallback or {}

    def pct(name):
        v = features.get(name)
        if v is None:
            v = fallback.get(name, 50.0)
        return float(v) / 100.0

    return np.array([
        1.0,
        pct("latest_score"),
        pct("attendance_pct"),
        pct("assignment_completion_pct"),
        pct("practice_accuracy_pct"),
        1.0 if state == "attention_needed" else 0.0,
        1.0 if state == "high_support_need" else 0.0,
        min(no_improvement_streak, 3) / 3.0,
    ], dtype=float)


@dataclass
class ArmParams:
    A: np.ndarray
    b: np.ndarray
    n: int = 0

    @classmethod
    def prior(cls, dim: int, lam: float) -> "ArmParams":
        return cls(A=lam * np.eye(dim), b=np.zeros(dim), n=0)

    def posterior(self, v: float):
        A_inv = np.linalg.inv(self.A)
        mu = A_inv @ self.b
        cov = (v ** 2) * A_inv
        cov = (cov + cov.T) / 2.0  # enforce exact symmetry for the sampler
        return mu, cov

    def updated(self, x: np.ndarray, r: float) -> "ArmParams":
        return ArmParams(A=self.A + np.outer(x, x), b=self.b + r * x, n=self.n + 1)

    def to_json(self):
        return {"A": self.A.tolist(), "b": self.b.tolist(), "n": self.n}


class NoEligibleArmError(ValueError):
    pass


def select_arm(params: dict[str, ArmParams], eligible: list[str], x: np.ndarray, v: float,
               rng: np.random.Generator) -> tuple[str, dict]:
    """Return (chosen_arm, details). `params` holds every arm; only `eligible` arms are scored."""
    if not eligible:
        raise NoEligibleArmError("No eligible interventions to choose from")
    details = {}
    for arm in eligible:
        if arm not in params:
            raise KeyError(f"No policy parameters for arm '{arm}'")
        mu, cov = params[arm].posterior(v)
        theta = rng.multivariate_normal(mu, cov, method="cholesky")
        details[arm] = {
            "sampled_score": round(float(x @ theta), 6),
            "posterior_mean_score": round(float(x @ mu), 6),
            "posterior_sd_score": round(float(np.sqrt(max(x @ cov @ x, 0.0))), 6),
            "n_observations": params[arm].n,
        }
    chosen = max(eligible, key=lambda a: details[a]["sampled_score"])
    return chosen, details
