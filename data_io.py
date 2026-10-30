"""Загрузка и проверка CSV с историей нагрузки."""
import io

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "calls", "aht_sec"]


class DataError(ValueError):
    """Ошибка во входных данных; текст сообщения показывается пользователю."""


def _lines(index_values, limit: int = 5) -> str:
    """Номера строк файла (с учётом заголовка) для сообщения об ошибке."""
    nums = [int(i) + 2 for i in list(index_values)[:limit]]
    text = ", ".join(str(n) for n in nums)
    return text + (" и др." if len(index_values) > limit else "")


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Проверяет таблицу и возвращает очищенную копию с правильными типами."""
    if df is None or len(df) == 0:
        raise DataError("Файл пустой: нет ни одной строки данных.")

    data = df.copy()
    data.columns = [str(c).strip().lower() for c in data.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
    if missing:
        raise DataError(
            "Не хватает колонок: " + ", ".join(missing)
            + ". Нужны: " + ", ".join(REQUIRED_COLUMNS) + "."
        )

    ts = pd.to_datetime(data["timestamp"], errors="coerce")
    bad = data.index[ts.isna()]
    if len(bad):
        raise DataError(f"Не удалось распознать дату и время в строках: {_lines(bad)}.")

    calls = pd.to_numeric(data["calls"], errors="coerce")
    bad = data.index[calls.isna() | (calls < 0)]
    if len(bad):
        raise DataError(
            f"Число обращений (calls) должно быть числом не меньше 0. Строки: {_lines(bad)}."
        )

    aht = pd.to_numeric(data["aht_sec"], errors="coerce")
    bad = data.index[aht.isna() | (aht <= 0)]
    if len(bad):
        raise DataError(
            f"Длительность обработки (aht_sec) должна быть числом больше 0. Строки: {_lines(bad)}."
        )

    data["timestamp"] = ts
    data["calls"] = calls.astype(float)
    data["aht_sec"] = aht.astype(float)
    return data.sort_values("timestamp").reset_index(drop=True)


def load_csv(source) -> pd.DataFrame:
    """Читает CSV из пути или файлового объекта и проверяет его."""
    try:
        if hasattr(source, "read"):
            raw = source.read()
        else:
            with open(source, "rb") as fh:
                raw = fh.read()
        if isinstance(raw, bytes):
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1251")
        else:
            text = raw
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
    except pd.errors.EmptyDataError:
        raise DataError("Файл пустой.")
    except DataError:
        raise
    except Exception as exc:  # непонятный формат файла
        raise DataError(f"Не удалось прочитать файл как CSV: {exc}")
    return validate(df)
