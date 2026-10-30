import pandas as pd

from core.kpi import compare_kpis, compute_kpis


def test_t13_kpis_manual_example():  # T13
    cov = pd.DataFrame({"required": [2, 2, 2, 2], "planned": [1, 2, 3, 4]})
    cov["gap"] = cov["required"] - cov["planned"]  # [1, 0, -1, -2]
    k = compute_kpis(cov, tolerance=0, hourly_rate=100, w_deficit=3, w_excess=1)
    assert k["deficit_hours_share"] == 0.25
    assert k["excess_hours_share"] == 0.5
    assert k["deficit_agent_hours"] == 1 and k["excess_agent_hours"] == 3
    assert abs(k["coverage_ratio"] - 7 / 8) < 1e-9
    assert k["idle_cost"] == 300
    assert k["objective"] == 6


def test_tolerance_reduces_excess():
    cov = pd.DataFrame({"required": [2, 2], "planned": [3, 4]})
    cov["gap"] = cov["required"] - cov["planned"]
    k = compute_kpis(cov, tolerance=1)
    assert k["excess_agent_hours"] == 1 and k["excess_hours_share"] == 0.5


def test_compare_table_shape():
    cov = pd.DataFrame({"required": [1], "planned": [1], "gap": [0]})
    k = compute_kpis(cov)
    table = compare_kpis(k, k)
    assert list(table.columns) == ["KPI", "Базовый", "Оптимизированный", "Изменение"]
    assert (table["Изменение"] == 0).all()
