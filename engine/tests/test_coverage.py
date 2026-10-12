from datetime import date

from app.services.coverage import months


def test_months_cover_partial_period_bounds():
    assert months(date(2025, 7, 15), date(2026, 1, 3)) == [date(2025, m, 1) for m in range(7, 13)] + [date(2026, 1, 1)]


def test_single_month():
    assert months(date(2025, 2, 1), date(2025, 2, 28)) == [date(2025, 2, 1)]
