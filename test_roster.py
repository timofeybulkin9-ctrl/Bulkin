from core.config import SHIFTS
from core.optimizer import optimize_schedule
from core.roster import assign_roster, roster_matrix
from tests.helpers import make_demand

N = 30


def _roster():
    schedule, _ = optimize_schedule(make_demand(), N, method="greedy")
    roster, unfilled = assign_roster(schedule, N)
    return schedule, roster, unfilled


def test_t10_max_5_days_and_one_shift_per_day():  # T10
    _, roster, _ = _roster()
    assert roster.groupby("employee").size().max() <= 5
    assert roster.groupby(["employee", "weekday"]).size().max() == 1


def test_t16_rest_between_shifts():  # T16
    _, roster, _ = _roster()
    ends = {s.name: s.end for s in SHIFTS}
    starts = {s.name: s.start for s in SHIFTS}
    by_key = {(r.employee, r.weekday): r.shift for r in roster.itertuples()}
    for (emp, day), name in by_key.items():
        nxt = by_key.get((emp, day + 1))
        if nxt:
            assert (24 - ends[name]) + starts[nxt] >= 11  # нет «22:00 → 08:00»


def test_roster_matches_schedule_counts():
    schedule, roster, unfilled = _roster()
    assert unfilled == []
    assert len(roster) == schedule["agents"].sum()
    assert roster_matrix(roster, N).shape == (N, 7)
