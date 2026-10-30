"""Базовый («плоский») график: те же смены, поровну каждый день."""
import pandas as pd

from .config import BASELINE_SHIFT_NAMES, SHIFTS, allowed_shifts


def build_baseline(total_shifts: int, n_agents: int, shifts=SHIFTS,
                   baseline_names=BASELINE_SHIFT_NAMES) -> pd.DataFrame:
    """Раскладывает total_shifts смен поровну по 7 дням и по типовым сменам.

    Так работает руководитель без расчёта: каждый день одно и то же число людей,
    поровну на утро и вечер. В выходные, где типовых смен нет, берутся доступные.
    """
    if total_shifts < 0 or n_agents < 1:
        raise ValueError("Некорректные параметры базового графика.")
    per_day, extra = divmod(int(total_shifts), 7)
    rows = []
    for day in range(7):
        day_total = min(per_day + (1 if day < extra else 0), n_agents)
        day_shifts = allowed_shifts(day, shifts)
        chosen = [s for s in day_shifts if s.name in baseline_names] or day_shifts
        counts = {s.name: 0 for s in day_shifts}
        if chosen:
            share, rest = divmod(day_total, len(chosen))
            for i, s in enumerate(chosen):
                counts[s.name] = share + (1 if i < rest else 0)
        for s in day_shifts:
            rows.append((day, s.name, counts[s.name]))
    return pd.DataFrame(rows, columns=["weekday", "shift", "agents"])
