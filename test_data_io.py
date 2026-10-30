import io

import pytest

from core.data_io import DataError, load_csv

GOOD = "timestamp,calls,aht_sec\n2025-03-03 10:00,42,280\n2025-03-03 11:00,50,300\n"


def test_t1_valid_csv_loads():  # T1
    df = load_csv(io.StringIO(GOOD))
    assert len(df) == 2 and df["calls"].iloc[0] == 42


def test_t1_semicolon_separator_and_bytes():
    df = load_csv(io.BytesIO(GOOD.replace(",", ";").encode("utf-8")))
    assert len(df) == 2


def test_t2_missing_column():  # T2
    with pytest.raises(DataError) as e:
        load_csv(io.StringIO("timestamp,calls\n2025-03-03 10:00,42\n"))
    assert "aht_sec" in str(e.value)


def test_t3_negative_calls_reports_line():  # T3
    bad = "timestamp,calls,aht_sec\n2025-03-03 10:00,-5,280\n"
    with pytest.raises(DataError) as e:
        load_csv(io.StringIO(bad))
    assert "2" in str(e.value)


def test_t3_empty_value_and_bad_date():  # T3
    with pytest.raises(DataError):
        load_csv(io.StringIO("timestamp,calls,aht_sec\n2025-03-03 10:00,,280\n"))
    with pytest.raises(DataError):
        load_csv(io.StringIO("timestamp,calls,aht_sec\nне дата,5,280\n"))
    with pytest.raises(DataError):
        load_csv(io.StringIO("timestamp,calls,aht_sec\n2025-03-03 10:00,5,0\n"))


def test_empty_file():
    with pytest.raises(DataError):
        load_csv(io.StringIO(""))
