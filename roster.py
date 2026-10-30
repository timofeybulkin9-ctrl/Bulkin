"""Назначение конкретных сотрудников на смены (FR9)."""
import pandas as pd

from .config import DEFAULTS, SHIFTS, WEEKDAYS


def _rest_ok(prev_shift, shift, min_rest: int) -> bool:
    """Отдых между вчерашней и сегодняшней сменой не меньше min_rest часов."""
    if prev_shift is None:
        return True
    return (24 - prev_shift.end) + shift.start >= min_rest


def assign_roster(schedule: pd.DataFrame, n_agents: int, max_days: int = 5,
                  min_rest: int = DEFAULTS["min_rest_hours"], shifts=SHIFTS):
    """Раздаёт смены по именам. Возвращает (таблица назначений, список незакрытых смен).

    Правила: один человек одна смена в день, не больше max_days дней в неделю,
    между сменами не меньше min_rest часов (вечерняя 22:00 не идёт перед утренней 08:00).
    Нагрузка выравнивается: выбираем тех, кто работал меньше всех.
    """
    by_name = {s.name: s for s in shifts}
    employees = [f"Оператор {i:02d}" for i in range(1, int(n_agents) + 1)]
    worked = {e: 0 for e in employees}
    assigned = {}  # (сотрудник, день) -> смена
    unfilled = []

    for day in range(7):
        todo = []
        day_rows = schedule[schedule["weekday"] == day]
        for row in day_rows.itertuples(index=False):
            todo += [by_name[row.shift]] * int(row.agents)
        todo.sort(key=lambda s: s.start)  # сначала ранние: у них больше всего ограничений
        for shift in todo:
            candidates = [e for e in employees
                          if (e, day) not in assigned and worked[e] < max_days
                          and _rest_ok(assigned.get((e, day - 1)), shift, min_rest)]
            if not candidates:
                unfilled.append((day, shift.name))
                continue
            chosen = min(candidates, key=lambda e: (worked[e], e))
            assigned[(chosen, day)] = shift
            worked[chosen] += 1

    rows = [(e, d, WEEKDAYS[d], s.name, s.start, s.end) for (e, d), s in assigned.items()]
    roster = pd.DataFrame(rows, columns=["employee", "weekday", "weekday_name", "shift", "start", "end"])
    roster = roster.sort_values(["employee", "weekday"]).reset_index(drop=True)
    return roster, unfilled


def roster_matrix(roster: pd.DataFrame, n_agents: int) -> pd.DataFrame:
    """Таблица «сотрудник × день недели» с названиями смен ('—' = выходной)."""
    employees = [f"Оператор {i:02d}" for i in range(1, int(n_agents) + 1)]
    matrix = pd.DataFrame("—", index=employees, columns=WEEKDAYS)
    for row in roster.itertuples(index=False):
        matrix.loc[row.employee, row.weekday_name] = row.shift
    matrix.index.name = "Сотрудник"
    return matrix
