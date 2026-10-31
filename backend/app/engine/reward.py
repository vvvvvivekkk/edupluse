"""Response evaluation: normalised learning gain, engagement change, combined reward, category.

    g = (post - pre) / (100 - pre)        for pre < 100
    pre == 100 (formula undefined):  g = 0 if post == 100 else (post - 100) / 100
      -> a student already at ceiling cannot show gain; any drop is penalised proportionally.
    g is clipped to [-1, 1] (a large drop from a low pre-score can be < -1 otherwise).

    e = mean_k (C_post,k - C_pre,k) / 100 over engagement components k (attendance %, assignment
      completion %, practice activity %) that are measured in BOTH the pre window
      [assigned - W, assigned] and the post window [assigned, follow-up]; clipped to [-1, 1].
      If no component is comparable, e is undefined and the reward falls back to r = g
      (recorded in the evidence as alpha_effective = 1).

    r = alpha * g + (1 - alpha) * e       r in [-1, 1] because g, e in [-1, 1] and 0 <= alpha <= 1

Categories (configurable thresholds, defaults):
    r >= 0.30            Positive
    0.05 <= r < 0.30     Partial
    r < 0.05             No Improvement

Note: r is a proposed engineering measure, not a validated measure of learning.
"""


class ComparabilityError(ValueError):
    pass


def learning_gain(pre: float, post: float) -> float:
    for name, v in (("pre", pre), ("post", post)):
        if v is None or not 0 <= v <= 100:
            raise ComparabilityError(f"{name}-intervention score must be within 0-100, got {v!r}")
    if pre >= 100:
        g = 0.0 if post >= 100 else (post - 100.0) / 100.0
    else:
        g = (post - pre) / (100.0 - pre)
    return max(-1.0, min(1.0, g))


def engagement_change(pre_components: dict, post_components: dict) -> tuple[float | None, list[str]]:
    """e = mean over components present in BOTH windows of (post - pre) / 100, clipped to [-1, 1].
    Returns (e, components_used). e is None when no component is comparable."""
    common = [k for k, v in (pre_components or {}).items()
              if v is not None and (post_components or {}).get(k) is not None]
    if not common:
        return None, []
    e = sum((post_components[k] - pre_components[k]) / 100.0 for k in common) / len(common)
    return max(-1.0, min(1.0, e)), common


def combined_reward(g: float, e: float | None, alpha: float) -> tuple[float, float]:
    """Returns (reward, alpha_effective)."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    if e is None:
        return g, 1.0
    return alpha * g + (1.0 - alpha) * e, alpha


def classify(reward: float, positive_threshold: float, partial_threshold: float) -> str:
    if reward >= positive_threshold:
        return "positive"
    if reward >= partial_threshold:
        return "partial"
    return "no_improvement"


CATEGORY_LABELS = {"positive": "Positive", "partial": "Partial", "no_improvement": "No Improvement"}
