import time

import pytest

from core.baseline import build_baseline
from core.config import SHIFTS
from core.kpi import compute_coverage, compute_kpis
from core.optimizer import optimize_schedule, validate_schedule
from tests.helpers import make_demand

N = 30


def _objective(schedule, demand):
    return compute_kpis(compute_coverage(schedule, demand))["objective"]


def test_t9_constraints_greedy():  # T9
    demand = make_demand()
    schedule, info = optimize_schedule(demand, N, method="greedy")
    assert validate_schedule(schedule, N) == []
    assert info["total_shifts"] <= N * 5
    assert schedule.groupby("weekday")["agents"].sum().max() <= N


def test_t9_constraints_pulp():  # T9
    pytest.importorskip("pulp")
    demand = make_demand()
    schedule, info = optimize_schedule(demand, N, method="pulp")
    assert validate_schedule(schedule, N) == []
    assert info["method"].startswith("PuLP")


def test_t9_validate_detects_violation():
    demand = make_demand()
    schedule, _ = optimize_schedule(demand, N, method="greedy")
    schedule.loc[0, "agents"] = N + 5
    assert validate_schedule(schedule, N) != []


def test_t11_greedy_better_than_baseline():  # T11
    demand = make_demand()
    schedule, info = optimize_schedule(demand, N, method="greedy")
    base = build_baseline(info["total_shifts"], N)
    opt_k = compute_kpis(compute_coverage(schedule, demand))
    base_k = compute_kpis(compute_coverage(base, demand))
    assert opt_k["objective"] <= base_k["objective"]
    assert opt_k["deficit_agent_hours"] <= base_k["deficit_agent_hours"]
    assert opt_k["coverage_ratio"] >= base_k["coverage_ratio"]


def test_t11_pulp_not_worse_than_baseline_or_greedy():  # T11
    pytest.importorskip("pulp")
    demand = make_demand()
    exact, info = optimize_schedule(demand, N, method="pulp")
    greedy, _ = optimize_schedule(demand, N, method="greedy")
    base = build_baseline(info["total_shifts"], N)
    assert _objective(exact, demand) <= _objective(base, demand) + 1e-6
    assert _objective(exact, demand) <= _objective(greedy, demand) + 1e-6


def test_t12_greedy_deficit_not_worse_than_empty_plan():  # T12
    demand = make_demand()
    schedule, _ = optimize_schedule(demand, N, method="greedy")
    cov = compute_coverage(schedule, demand)
    assert cov["gap"].clip(lower=0).sum() < demand["required_agents"].sum()
    assert (schedule["agents"] >= 0).all()


def test_zero_demand_gives_empty_schedule():
    demand = make_demand()
    demand["required_agents"] = 0
    schedule, info = optimize_schedule(demand, N, method="greedy")
    assert info["total_shifts"] == 0


def test_baseline_is_flat_and_same_volume():
    base = build_baseline(140, N)
    per_day = base.groupby("weekday")["agents"].sum()
    assert per_day.sum() == 140 and per_day.max() - per_day.min() <= 1
    assert validate_schedule(base, N) == []


def test_bad_params():
    demand = make_demand()
    with pytest.raises(ValueError):
        optimize_schedule(demand, 0)
    with pytest.raises(ValueError):
        optimize_schedule(demand, N, w_deficit=0)


def test_t15_speed_for_40_agents():  # T15
    demand = make_demand()
    started = time.time()
    optimize_schedule(demand, 40, method="auto", time_limit=30)
    assert time.time() - started < 40
