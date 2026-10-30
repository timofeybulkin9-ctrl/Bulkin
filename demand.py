"""Профиль нагрузки «день недели × час» и расчёт необходимого числа операторов."""
import math

import pandas as pd

from .config import operating_hours


def build_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Среднее число обращений и средняя длительность по каждой ячейке «день × час».

    Часы без записей считаются как 0 обращений.
    """
    d = df.copy()
    d["date"] = d["timestamp"].dt.normalize()
    d["hour"] = d["timestamp"].dt.hour
    d["weekday"] = d["timestamp"].dt.weekday
    d["work"] = d["calls"] * d["aht_sec"]

    dates_per_weekday = d.groupby("weekday")["date"].nunique()
    sums = d.groupby(["weekday", "hour"], as_index=False).agg(
        calls=("calls", "sum"), work=("work", "sum")
    )

    total_calls = d["calls"].sum()
    overall_aht = d["work"].sum() / total_calls if total_calls > 0 else 300.0

    rows = []
    lookup = {(int(r.weekday), int(r.hour)): r for r in sums.itertuples(index=False)}
    for wd in range(7):
        n_dates = int(dates_per_weekday.get(wd, 0))
        for hour in operating_hours(wd):
            rec = lookup.get((wd, hour))
            if rec is None or n_dates == 0 or rec.calls <= 0:
                rows.append((wd, hour, 0.0, overall_aht))
            else:
                rows.append((wd, hour, rec.calls / n_dates, rec.work / rec.calls))
    return pd.DataFrame(rows, columns=["weekday", "hour", "avg_calls", "avg_aht"])


def _erlang_c(n: int, a: float) -> float:
    """Вероятность ожидания в очереди (формула Erlang C). Требует n > a."""
    b = 1.0  # Erlang B считаем итеративно, это численно устойчиво
    for k in range(1, n + 1):
        b = a * b / (k + a * b)
    return n * b / (n - a * (1 - b))


def service_level(n: int, a: float, aht_sec: float, answer_sec: float) -> float:
    """Доля обращений, отвеченных за answer_sec секунд, при n операторах."""
    if a <= 0:
        return 1.0
    if n <= a:
        return 0.0
    pw = _erlang_c(n, a)
    return 1 - pw * math.exp(-(n - a) * answer_sec / aht_sec)


def erlang_c_agents(calls_per_hour: float, aht_sec: float, sl_target: float = 0.80,
                    answer_sec: float = 20, max_occupancy: float = 0.85) -> int:
    """Минимум операторов, при которых выполнены цель по уровню сервиса и лимит загрузки."""
    if calls_per_hour < 0 or aht_sec <= 0:
        raise ValueError("Число обращений не может быть отрицательным, длительность должна быть > 0.")
    if not 0 < sl_target <= 1 or not 0 < max_occupancy <= 1:
        raise ValueError("Уровень сервиса и загрузка должны быть в диапазоне (0; 1].")
    if calls_per_hour == 0:
        return 0
    a = calls_per_hour * aht_sec / 3600.0  # нагрузка в Эрлангах (операторо-часов в час)
    n = max(1, int(math.floor(a)) + 1)
    for _ in range(10000):
        if n > a and a / n <= max_occupancy and service_level(n, a, aht_sec, answer_sec) >= sl_target:
            return n
        n += 1
    raise RuntimeError("Не удалось подобрать число операторов.")


def simple_agents(calls_per_hour: float, aht_sec: float, max_occupancy: float = 0.85) -> int:
    """Упрощённый расчёт: нагрузка в часах, делённая на допустимую загрузку, вверх."""
    if calls_per_hour < 0 or aht_sec <= 0 or not 0 < max_occupancy <= 1:
        raise ValueError("Некорректные параметры расчёта.")
    if calls_per_hour == 0:
        return 0
    return int(math.ceil(calls_per_hour * aht_sec / 3600.0 / max_occupancy))


def compute_demand(profile: pd.DataFrame, method: str = "erlang", sl_target: float = 0.80,
                   answer_sec: float = 20, max_occupancy: float = 0.85) -> pd.DataFrame:
    """Добавляет к профилю колонку required_agents."""
    if method not in ("erlang", "simple"):
        raise ValueError("method должен быть 'erlang' или 'simple'.")
    out = profile.copy()
    if method == "erlang":
        req = [erlang_c_agents(c, t, sl_target, answer_sec, max_occupancy)
               for c, t in zip(out["avg_calls"], out["avg_aht"])]
    else:
        req = [simple_agents(c, t, max_occupancy) for c, t in zip(out["avg_calls"], out["avg_aht"])]
    out["required_agents"] = req
    return out
