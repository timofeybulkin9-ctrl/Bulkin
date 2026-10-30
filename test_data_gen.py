from core.data_gen import generate_demo


def test_t4_reproducible_and_marked_synthetic():  # T4
    a, b = generate_demo(weeks=2, seed=1), generate_demo(weeks=2, seed=1)
    assert a.equals(b)
    assert (a["source"] == "synthetic").all()
    assert not a.equals(generate_demo(weeks=2, seed=2))
