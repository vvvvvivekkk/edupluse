# Simulation results (NOT real-world evidence)

30 runs x 600 rounds, same students, eligibility rules and hidden reward model for every policy. Hidden reward model is described in `backend/scripts/simulate.py`.

| Policy | Mean reward | Mean reward (last 100) | Cumulative regret (mean ± sd) | Ineligible picks |
|---|---|---|---|---|
| linear_thompson | 0.2606 | 0.2734 | 24.3 ± 3.36 | 0 |
| random_eligible | 0.2272 | 0.2311 | 46.36 ± 1.69 | 0 |
| fixed_rule | 0.1853 | 0.1869 | 72.53 ± 3.11 | 0 |

Regret = (best eligible expected reward) − (expected reward of chosen arm), summed over rounds. Lower is better.

Interpretation: under this assumed model the adaptive policy learns which eligible intervention suits which context and accumulates less regret than the baselines. Whether the assumed model resembles real students is unknown; this only verifies that the implementation learns and adapts as designed.
