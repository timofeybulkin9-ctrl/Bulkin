"""Общие функции для тестов."""
from core.data_gen import generate_demo
from core.demand import build_profile, compute_demand


def make_demand(weeks: int = 4, seed: int = 42):
    return compute_demand(build_profile(generate_demo(weeks=weeks, seed=seed)))
