"""Покрытие нагрузки планом и расчёт KPI."""
import pandas as pd

from .config import DEFAULTS, SHIFTS


def compute_coverage(schedule: pd.DataFrame, demand: pd.DataFrame, shifts=SHIFTS) -> pd.DataFrame:
    """Для каждого часа: сколько нужно, сколько запланировано и разница.

    gap = required - planned: положительное значение это дефицит, отрицательное это избыток.
    """
    by_name = {s.name: s for s in shifts}
    planned = {}
    for row in schedule.itertuples(index=False):
        if row.agents <= 0:
            continue
        for hour in by_name[row.shift].hours:
            key = (int(row.weekday), hour)
            planned[key] = planned.get(key, 0) + int(row.agents)

    cov = demand[["weekday", "hour", "required_agents"]].rename(
        columns={"required_agents": "required"}).copy()
    cov["planned"] = [planned.get((int(d), int(h)), 0) for d, h in zip(cov["weekday"], cov["hour"])]
    cov["gap"] = cov["required"] - cov["planned"]
    return cov.reset_index(drop=True)


def compute_kpis(cov: pd.DataFrame, tolerance: int = 0, hourly_rate: float = 0.0,
                 w_deficit: float = DEFAULTS["w_deficit"], w_excess: float = DEFAULTS["w_excess"]) -> dict:
    """KPI по таблице покрытия (формулы из раздела 14 бизнес-постановки)."""
    total_hours = len(cov)
    gap = cov["gap"]
    deficit_ah = float(gap.clip(lower=0).sum())
    excess_ah = float((-gap - tolerance).clip(lower=0).sum())
    required_total = float(cov["required"].sum())
    covered = float(cov[["planned", "required"]].min(axis=1).sum())
    return {
        "deficit_hours_share": float((gap > 0).sum() / total_hours) if total_hours else 0.0,
        "excess_hours_share": float((gap < -tolerance).sum() / total_hours) if total_hours else 0.0,
        "coverage_ratio": covered / required_total if required_total > 0 else 1.0,
        "deficit_agent_hours": deficit_ah,
        "excess_agent_hours": excess_ah,
        "idle_cost": excess_ah * hourly_rate,
        "planned_agent_hours": float(cov["planned"].sum()),
        "objective": w_deficit * deficit_ah + w_excess * excess_ah,
    }


KPI_LABELS = [
    ("deficit_hours_share", "Доля часов дефицита", "%"),
    ("excess_hours_share", "Доля часов избытка", "%"),
    ("coverage_ratio", "Покрытие нагрузки", "%"),
    ("deficit_agent_hours", "Операторо-часы дефицита", "ч"),
    ("excess_agent_hours", "Операторо-часы избытка", "ч"),
    ("planned_agent_hours", "Всего операторо-часов в плане", "ч"),
    ("idle_cost", "Условная стоимость простоя", "руб."),
    ("objective", "Целевая функция (штраф)", ""),
]


def compare_kpis(base: dict, opt: dict) -> pd.DataFrame:
    """Таблица «базовый график и оптимизированный» с изменением."""
    rows = []
    for key, label, unit in KPI_LABELS:
        b, o = base[key], opt[key]
        if unit == "%":
            b, o = b * 100, o * 100
        rows.append({"KPI": label + (f", {unit}" if unit else ""),
                     "Базовый": round(b, 2), "Оптимизированный": round(o, 2),
                     "Изменение": round(o - b, 2)})
    return pd.DataFrame(rows)
