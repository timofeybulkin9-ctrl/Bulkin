import math

import pandas as pd

from core.demand import _erlang_c, build_profile, erlang_c_agents, service_level


def _pw_reference(n, a):
    """Независимая запись формулы Erlang C через факториалы (ручной расчёт)."""
    s = sum(a ** k / math.factorial(k) for k in range(n))
    top = a ** n / math.factorial(n) * n / (n - a)
    return top / (s + top)


def test_t5_profile_average():  # T5
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(["2025-03-03 10:00", "2025-03-10 10:00"]),
        "calls": [10.0, 30.0], "aht_sec": [300.0, 100.0]})
    p = build_profile(df)
    row = p[(p.weekday == 0) & (p.hour == 10)].iloc[0]
    assert row.avg_calls == 20.0
    assert abs(row.avg_aht - 150.0) < 1e-9
    assert p[(p.weekday == 1)].avg_calls.sum() == 0  # во вторник данных нет


def test_t6_zero_calls_zero_agents():  # T6
    assert erlang_c_agents(0, 300) == 0


def test_t7_monotonic():  # T7
    prev = 0
    for calls in range(0, 301, 10):
        cur = erlang_c_agents(calls, 280)
        assert cur >= prev
        prev = cur


def test_t8_erlang_matches_manual_formula():  # T8
    for n, a in [(11, 10.0), (12, 10.0), (15, 10.0), (5, 3.5)]:
        assert abs(_erlang_c(n, a) - _pw_reference(n, a)) < 1e-9


def test_t8_agents_is_minimal():  # T8
    calls, aht = 120, 300  # нагрузка 10 Эрланг
    n = erlang_c_agents(calls, aht, sl_target=0.8, answer_sec=20, max_occupancy=1.0)
    a = calls * aht / 3600
    assert service_level(n, a, aht, 20) >= 0.8
    assert service_level(n - 1, a, aht, 20) < 0.8
