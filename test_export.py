import io

import openpyxl

from core.config import WEEKDAYS
from core.export import pivot_to_schedule, schedule_pivot, to_csv_bytes, to_excel_bytes
from core.optimizer import optimize_schedule
from tests.helpers import make_demand


def test_t14_excel_and_csv_export():  # T14
    schedule, _ = optimize_schedule(make_demand(), 30, method="greedy")
    pivot = schedule_pivot(schedule)
    assert list(pivot.columns) == WEEKDAYS
    wb = openpyxl.load_workbook(io.BytesIO(to_excel_bytes({"График": pivot})))
    assert "График" in wb.sheetnames
    assert "Пн" in [c.value for c in wb["График"][1]]
    assert to_csv_bytes(pivot).startswith(b"\xef\xbb\xbf")


def test_pivot_roundtrip():
    schedule, _ = optimize_schedule(make_demand(), 30, method="greedy")
    back = pivot_to_schedule(schedule_pivot(schedule))
    merged = schedule.merge(back, on=["weekday", "shift"], suffixes=("_a", "_b"))
    assert (merged["agents_a"] == merged["agents_b"]).all()
