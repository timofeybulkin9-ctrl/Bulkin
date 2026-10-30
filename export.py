"""Преобразование таблиц для показа и выгрузка в CSV/Excel."""
import io

import pandas as pd

from .config import SHIFTS, WEEKDAYS


def schedule_pivot(schedule: pd.DataFrame, shifts=SHIFTS) -> pd.DataFrame:
    """Таблица «смена × день недели» с числом операторов."""
    pivot = schedule.pivot_table(index="shift", columns="weekday", values="agents",
                                 aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=range(7), fill_value=0)
    order = [s.name for s in shifts if s.name in pivot.index]
    pivot = pivot.loc[order]
    pivot.columns = WEEKDAYS
    pivot.index.name = "Смена"
    return pivot.astype(int)


def pivot_to_schedule(pivot: pd.DataFrame) -> pd.DataFrame:
    """Обратное преобразование (после ручной правки таблицы)."""
    rows = []
    for name, row in pivot.iterrows():
        for i, day_name in enumerate(WEEKDAYS):
            rows.append((i, name, row[day_name]))
    out = pd.DataFrame(rows, columns=["weekday", "shift", "agents"])
    out["agents"] = pd.to_numeric(out["agents"], errors="coerce").fillna(-1)
    return out


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV в кодировке utf-8-sig: русский текст корректно открывается в Excel."""
    return df.to_csv(index=True).encode("utf-8-sig")


def to_excel_bytes(sheets: dict) -> bytes:
    """Excel-файл из словаря {название листа: таблица}."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=True)
    return buf.getvalue()
