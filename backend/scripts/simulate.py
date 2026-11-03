"""SIMULATION study: linear Thompson sampling vs. baseline policies (brief section 12).

    python -m scripts.simulate        -> writes ../docs/simulation_results.json and .md

All three policies use the SAME eligibility rules, the SAME simulated students and the SAME
hidden reward model, so the comparison is like-for-like. The hidden reward model is an
assumption invented for testing (documented below); results show the algorithm behaves as
intended under these conditions. THEY ARE NOT EVIDENCE OF REAL-WORLD EFFECTIVENESS.

Hidden expected reward (each in context of a student; s = topic score/100, m = practice accuracy/100,
att = attendance/100, comp = completion/100, hs = 1 if high-support state):
    targeted_material : 0.05 + 0.45*(1-m)
    targeted_practice : 0.05 + 0.50*m*(1-s)
    study_plan        : -0.10 + 0.60*(1-att) + 0.40*(1-comp)
    faculty_support   : 0.05 + 0.30*hs + 0.15*streak/3
Observed reward = expected + N(0, 0.25), clipped to [-1, 1].
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DEFAULT_CONFIG  # noqa: E402
from app.engine.eligibility import DEFAULT_RULES, evaluate_eligibility  # noqa: E402
from app.engine.thompson import DIM, ArmParams, build_context, select_arm  # noqa: E402
from app.ml.state_model import predict_state  # noqa: E402
from app.ml.synthetic import generate_students  # noqa: E402

ARMS = ["targeted_material", "targeted_practice", "study_plan", "faculty_support"]
FIXED_PRIORITY = ["targeted_practice", "targeted_material", "study_plan", "faculty_support"]
NOISE_SD = 0.25
RUNS, ROUNDS = 30, 600


def true_reward(arm, c):
    s, m = c["topic_score"] / 100, (c["topic_mastery"] if c["topic_mastery"] is not None else 50) / 100
    att, comp = c["attendance_pct"] / 100, c["assignment_completion_pct"] / 100
    hs = 1.0 if c["state"] == "high_support_need" else 0.0
    return {"targeted_material": 0.05 + 0.45 * (1 - m),
            "targeted_practice": 0.05 + 0.50 * m * (1 - s),
            "study_plan": -0.10 + 0.60 * (1 - att) + 0.40 * (1 - comp),
            "faculty_support": 0.05 + 0.30 * hs + 0.15 * c["no_improvement_streak"] / 3}[arm]


def build_pool(n=1500, seed=11):
    df = generate_students(n, seed=seed)
    pool, rng = [], np.random.default_rng(seed)
    for _, r in df.iterrows():
        f = {k: (None if v != v else float(v)) for k, v in r.items()
             if k in ("latest_score", "avg_score", "attendance_pct", "assignment_completion_pct",
                      "practice_accuracy_pct", "previous_result_pct")}
        st = predict_state(f)["state"]
        if st == "normal":
            continue
        c = {"state": st, "latest_score": f["latest_score"], "topic_score": f["latest_score"],
             "topic_mastery": f["practice_accuracy_pct"],
             "attendance_pct": f["attendance_pct"] if f["attendance_pct"] is not None else 82.0,
             "assignment_completion_pct": f["assignment_completion_pct"] if f["assignment_completion_pct"] is not None else 78.0,
             "practice_accuracy_pct": f["practice_accuracy_pct"], "no_improvement_streak": int(rng.integers(0, 3))}
        e = evaluate_eligibility(c, DEFAULT_RULES, DEFAULT_CONFIG, set(ARMS))
        if e["eligible"]:
            pool.append((c, e["eligible"]))
    return pool


def run(policy, pool, seed):
    rng = np.random.default_rng(seed)
    params = {a: ArmParams.prior(DIM, DEFAULT_CONFIG["lints_lambda"]) for a in ARMS}
    rewards, regrets, violations = [], [], 0
    for t in range(ROUNDS):
        c, eligible = pool[rng.integers(len(pool))]
        x = build_context(c, c["state"], c["no_improvement_streak"])
        if policy == "linear_thompson":
            arm, _ = select_arm(params, eligible, x, DEFAULT_CONFIG["lints_v"], rng)
        elif policy == "random_eligible":
            arm = eligible[rng.integers(len(eligible))]
        else:
            arm = next(a for a in FIXED_PRIORITY if a in eligible)
        violations += arm not in eligible
        mu = true_reward(arm, c)
        r = float(np.clip(mu + rng.normal(0, NOISE_SD), -1, 1))
        best = max(true_reward(a, c) for a in eligible)
        rewards.append(r)
        regrets.append(best - mu)
        if policy == "linear_thompson":
            params[arm] = params[arm].updated(x, r)
    return np.array(rewards), np.cumsum(regrets), violations


def main():
    pool = build_pool()
    out = {"disclaimer": "SIMULATION RESULTS under an assumed reward model - not real-world evidence.",
           "runs": RUNS, "rounds_per_run": ROUNDS, "noise_sd": NOISE_SD, "pool_size": len(pool), "policies": {}}
    for policy in ("linear_thompson", "random_eligible", "fixed_rule"):
        R, G, V = [], [], 0
        for k in range(RUNS):
            r, g, v = run(policy, pool, seed=1000 + k)
            R.append(r)
            G.append(g)
            V += v
        R, G = np.array(R), np.array(G)
        out["policies"][policy] = {
            "mean_reward_all_rounds": round(float(R.mean()), 4),
            "mean_reward_last_100_rounds": round(float(R[:, -100:].mean()), 4),
            "final_cumulative_regret_mean": round(float(G[:, -1].mean()), 2),
            "final_cumulative_regret_sd": round(float(G[:, -1].std()), 2),
            "ineligible_selections": int(V),
            "regret_curve_every_50": [round(float(G[:, i].mean()), 2) for i in range(49, ROUNDS, 50)],
        }
    docs = Path(__file__).resolve().parent.parent.parent / "docs"
    (docs / "simulation_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["# Simulation results (NOT real-world evidence)", "",
             f"{RUNS} runs x {ROUNDS} rounds, same students, eligibility rules and hidden reward model for every policy. "
             "Hidden reward model is described in `backend/scripts/simulate.py`.", "",
             "| Policy | Mean reward | Mean reward (last 100) | Cumulative regret (mean ± sd) | Ineligible picks |",
             "|---|---|---|---|---|"]
    for p, m in out["policies"].items():
        lines.append(f"| {p} | {m['mean_reward_all_rounds']} | {m['mean_reward_last_100_rounds']} | "
                     f"{m['final_cumulative_regret_mean']} ± {m['final_cumulative_regret_sd']} | {m['ineligible_selections']} |")
    lines += ["", "Regret = (best eligible expected reward) − (expected reward of chosen arm), summed over rounds. Lower is better.",
              "", "Interpretation: under this assumed model the adaptive policy learns which eligible intervention suits which "
              "context and accumulates less regret than the baselines. Whether the assumed model resembles real students is "
              "unknown; this only verifies that the implementation learns and adapts as designed."]
    (docs / "simulation_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    print("\n".join(lines))


if __name__ == "__main__":
    main()
