"""Генератор СИНТЕТИЧЕСКИХ данных для демонстрации (не реальные данные компании)."""
import numpy as np
import pandas as pd

from .config import operating_hours

# Относительная интенсивность звонков по часам (пик утром и вечером).
_HOUR_PATTERN = {
    8: 0.35, 9: 0.60, 10: 0.85, 11: 1.00, 12: 0.80, 13: 0.70, 14: 0.75,
    15: 0.80, 16: 0.75, 17: 0.85, 18: 0.95, 19: 0.70, 20: 0.50, 21: 0.35,
}
# Множитель по дням недели: понедельник самый загруженный, выходные спокойнее.
_DAY_FACTOR = {0: 1.15, 1: 1.00, 2: 0.95, 3: 0.95, 4: 0.90, 5: 0.45, 6: 0.35}
PEAK_CALLS_PER_HOUR = 170
BASE_AHT_SEC = 280


def generate_demo(weeks: int = 8, seed: int = 42, start: str = "2025-03-03") -> pd.DataFrame:
    """Почасовая история звонков за N недель. Одинаковый seed даёт одинаковый результат."""
    if weeks < 1:
        raise ValueError("Число недель должно быть не меньше 1.")
    rng = np.random.default_rng(seed)
    first_day = pd.Timestamp(start).normalize()
    rows = []
    for offset in range(weeks * 7):
        day = first_day + pd.Timedelta(days=offset)
        wd = day.weekday()
        for hour in operating_hours(wd):
            mean_calls = PEAK_CALLS_PER_HOUR * _HOUR_PATTERN[hour] * _DAY_FACTOR[wd]
            calls = int(rng.poisson(mean_calls))
            aht = float(np.clip(rng.normal(BASE_AHT_SEC, 25), 150, 500))
            rows.append((day + pd.Timedelta(hours=hour), calls, round(aht, 1), "synthetic"))
    return pd.DataFrame(rows, columns=["timestamp", "calls", "aht_sec", "source"])


if __name__ == "__main__":
    import os

    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "demo_calls.csv")
    generate_demo().to_csv(path, index=False)
    print("Демо-данные (синтетика) сохранены:", path)
