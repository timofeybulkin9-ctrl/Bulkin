"""Настройки по умолчанию, дни недели, часы работы и типовые смены."""
from dataclasses import dataclass

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


@dataclass(frozen=True)
class Shift:
    """Шаблон смены: название, час начала и длительность (часы)."""
    name: str
    start: int
    length: int = 8

    @property
    def end(self) -> int:
        return self.start + self.length

    @property
    def hours(self) -> range:
        """Часы, которые покрывает смена (начало включительно, конец нет)."""
        return range(self.start, self.end)

    def label(self) -> str:
        return f"{self.name} {self.start:02d}:00–{self.end:02d}:00"


# Часы работы контакт-центра: (первый час, час закрытия). [Синтетика]
OPERATING_HOURS = {
    0: (8, 22), 1: (8, 22), 2: (8, 22), 3: (8, 22), 4: (8, 22),  # Пн–Пт
    5: (9, 18), 6: (9, 18),                                      # Сб, Вс (сокращённо)
}

# Типовые смены по 8 часов, без перерывов.
SHIFTS = (
    Shift("Утро", 8),
    Shift("Ранний", 9),
    Shift("День", 10),
    Shift("Вечер", 14),
)

# Две «типовые» смены, на которых строится базовый (плоский) график.
BASELINE_SHIFT_NAMES = ("Утро", "Вечер")

DEFAULTS = {
    "n_agents": 30,          # операторов в штате
    "max_days": 5,           # рабочих дней на оператора в неделю
    "sl_target": 0.80,       # доля обращений, отвеченных вовремя
    "answer_sec": 20,        # «вовремя» = за 20 секунд
    "max_occupancy": 0.85,   # максимальная загрузка оператора
    "w_deficit": 3.0,        # штраф за 1 операторо-час дефицита
    "w_excess": 1.0,         # штраф за 1 операторо-час избытка
    "tolerance": 0,          # допуск избытка, операторов
    "hourly_rate": 0.0,      # ставка операторо-часа для стоимости простоя
    "time_limit": 30,        # лимит времени решателя, секунды
    "min_rest_hours": 11,    # отдых между сменами при назначении людей
}


def operating_hours(day: int) -> range:
    start, end = OPERATING_HOURS[day]
    return range(start, end)


def is_shift_allowed(shift: Shift, day: int) -> bool:
    """Смена допустима в день, только если целиком лежит в часах работы."""
    start, end = OPERATING_HOURS[day]
    return shift.start >= start and shift.end <= end


def allowed_shifts(day: int, shifts=SHIFTS) -> list:
    return [s for s in shifts if is_shift_allowed(s, day)]
