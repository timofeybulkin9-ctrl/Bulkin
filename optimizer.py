"""Построение недельного графика: точный метод (PuLP) и запасной жадный алгоритм.

Задача простыми словами. Для каждого дня и каждой смены выбираем целое число
операторов x. В каждый час сравниваем «сколько вышло» и «сколько нужно»:
  недостача  = дефицит, избыток = лишние люди.
Минимизируем: вес_дефицита * сумма_дефицита + вес_избытка * сумма_избытка.
Ограничения: в день не больше n_agents смен (один человек одна смена),
за неделю не больше n_agents * max_days смен (не больше max_days дней на человека).
"""
import time

import pandas as pd

from .config import SHIFTS, allowed_shifts, is_shift_allowed


class OptimizationError(RuntimeError):
    """Решатель не смог построить график."""


def _check_params(n_agents, max_days, w_deficit, w_excess, tolerance, time_limit):
    if int(n_agents) < 1:
        raise ValueError("Число операторов должно быть не меньше 1.")
    if not 1 <= int(max_days) <= 7:
        raise ValueError("Рабочих дней в неделю: от 1 до 7.")
    if w_deficit <= 0 or w_excess <= 0:
        raise ValueError("Веса штрафов должны быть больше 0.")
    if tolerance < 0:
        raise ValueError("Допуск избытка не может быть отрицательным.")
    if time_limit <= 0:
        raise ValueError("Лимит времени должен быть больше 0.")


def _to_schedule(counts: dict) -> pd.DataFrame:
    rows = [(d, name, int(v)) for (d, name), v in counts.items()]
    return pd.DataFrame(rows, columns=["weekday", "shift", "agents"]).sort_values(
        ["weekday", "shift"]).reset_index(drop=True)


def _solve_pulp(req, n_agents, max_days, w_def, w_exc, tol, time_limit, shifts) -> dict:
    import pulp  # импорт внутри функции: без PuLP работает жадный алгоритм

    prob = pulp.LpProblem("shift_plan", pulp.LpMinimize)
    x = {}
    for day in range(7):
        for i, s in enumerate(allowed_shifts(day, shifts)):
            x[(day, s.name)] = pulp.LpVariable(f"x_{day}_{i}", lowBound=0, upBound=n_agents,
                                               cat="Integer")
    deficit = {k: pulp.LpVariable(f"def_{k[0]}_{k[1]}", lowBound=0) for k in req}
    excess = {k: pulp.LpVariable(f"exc_{k[0]}_{k[1]}", lowBound=0) for k in req}

    prob += pulp.lpSum(w_def * deficit[k] + w_exc * excess[k] for k in req)

    for (day, hour), need in req.items():
        planned = pulp.lpSum(x[(day, s.name)] for s in allowed_shifts(day, shifts)
                             if hour in s.hours)
        prob += deficit[(day, hour)] >= need - planned
        prob += excess[(day, hour)] >= planned - need - tol
    for day in range(7):
        prob += pulp.lpSum(x[(day, s.name)] for s in allowed_shifts(day, shifts)) <= n_agents
    prob += pulp.lpSum(x.values()) <= n_agents * max_days

    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))
    status = pulp.LpStatus[prob.status]
    if status != "Optimal" or any(v.value() is None for v in x.values()):
        raise OptimizationError(f"Решатель вернул статус: {status}")
    return {k: int(round(v.value())) for k, v in x.items()}


def _solve_greedy(req, n_agents, max_days, w_def, w_exc, tol, shifts) -> dict:
    """Жадный алгоритм: пока это выгодно, добавляем смену с наибольшим выигрышем."""
    counts = {(d, s.name): 0 for d in range(7) for s in allowed_shifts(d, shifts)}
    by_name = {s.name: s for s in shifts}
    planned = {k: 0 for k in req}
    day_total = {d: 0 for d in range(7)}
    total, cap = 0, n_agents * max_days
    while total < cap:
        best, best_delta = None, 0.0
        for (day, name) in counts:
            if day_total[day] >= n_agents:
                continue
            delta = 0.0
            for hour in by_name[name].hours:
                if (day, hour) not in req:
                    continue
                need, have = req[(day, hour)], planned[(day, hour)]
                if have < need:
                    delta -= w_def      # закрываем 1 час дефицита
                elif have >= need + tol:
                    delta += w_exc      # добавляем 1 час избытка
            if delta < best_delta - 1e-12:
                best, best_delta = (day, name), delta
        if best is None:
            break
        day, name = best
        counts[best] += 1
        day_total[day] += 1
        total += 1
        for hour in by_name[name].hours:
            if (day, hour) in planned:
                planned[(day, hour)] += 1
    return counts


def optimize_schedule(demand: pd.DataFrame, n_agents: int, max_days: int = 5,
                      w_deficit: float = 3.0, w_excess: float = 1.0, tolerance: int = 0,
                      time_limit: float = 30, shifts=SHIFTS, method: str = "auto"):
    """Строит недельный график. Возвращает (таблица weekday/shift/agents, info).

    method: "auto" (PuLP, при неудаче жадный), "pulp" или "greedy".
    """
    _check_params(n_agents, max_days, w_deficit, w_excess, tolerance, time_limit)
    if method not in ("auto", "pulp", "greedy"):
        raise ValueError("method должен быть 'auto', 'pulp' или 'greedy'.")
    if demand is None or len(demand) == 0:
        raise ValueError("Нет данных о потребности.")

    req = {(int(d), int(h)): int(r)
           for d, h, r in zip(demand["weekday"], demand["hour"], demand["required_agents"])}
    n_agents, max_days = int(n_agents), int(max_days)
    started = time.time()
    info = {"method": None, "note": ""}
    counts = None

    if method in ("auto", "pulp"):
        try:
            counts = _solve_pulp(req, n_agents, max_days, w_deficit, w_excess, tolerance,
                                 time_limit, shifts)
            info["method"] = "PuLP (точный)"
        except Exception as exc:  # нет PuLP, решатель упал или не нашёл решение
            if method == "pulp":
                raise OptimizationError(str(exc))
            info["note"] = f"PuLP недоступен или не справился ({exc}); использован жадный алгоритм."
    if counts is None:
        counts = _solve_greedy(req, n_agents, max_days, w_deficit, w_excess, tolerance, shifts)
        info["method"] = "Жадный алгоритм"

    schedule = _to_schedule(counts)
    info["seconds"] = round(time.time() - started, 2)
    info["total_shifts"] = int(schedule["agents"].sum())
    return schedule, info


def validate_schedule(schedule: pd.DataFrame, n_agents: int, max_days: int = 5,
                      shifts=SHIFTS) -> list:
    """Проверка графика на ограничения. Пустой список означает, что нарушений нет."""
    errors = []
    names = {s.name: s for s in shifts}
    for row in schedule.itertuples(index=False):
        if row.agents < 0 or int(row.agents) != row.agents:
            errors.append(f"Число операторов должно быть целым неотрицательным ({row.shift}, день {row.weekday + 1}).")
        if row.shift not in names:
            errors.append(f"Неизвестная смена: {row.shift}.")
        elif row.agents > 0 and not is_shift_allowed(names[row.shift], int(row.weekday)):
            errors.append(f"Смена «{row.shift}» выходит за часы работы в день {int(row.weekday) + 1}.")
    per_day = schedule.groupby("weekday")["agents"].sum()
    for day, total in per_day.items():
        if total > n_agents:
            errors.append(f"В день {int(day) + 1} смен больше, чем операторов ({int(total)} > {n_agents}).")
    if schedule["agents"].sum() > n_agents * max_days:
        errors.append(f"Всего смен больше допустимого: {int(schedule['agents'].sum())} > {n_agents * max_days}.")
    return errors
