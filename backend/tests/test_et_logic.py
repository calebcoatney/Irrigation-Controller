import pytest
from et_logic import update_deficit, compute_duration_seconds


def test_update_deficit_basic():
    result = update_deficit(0.0, et_mm=5.0, precip_mm=0.0, et_coefficient=0.8)
    assert result == pytest.approx(4.0)


def test_update_deficit_rain_reduces_deficit():
    result = update_deficit(3.0, et_mm=5.0, precip_mm=6.0, et_coefficient=0.8)
    assert result == pytest.approx(1.0)


def test_update_deficit_never_negative():
    result = update_deficit(0.0, et_mm=2.0, precip_mm=10.0, et_coefficient=0.8)
    assert result == 0.0


def test_update_deficit_accumulates_over_days():
    deficit = 0.0
    deficit = update_deficit(deficit, et_mm=6.0, precip_mm=0.0, et_coefficient=0.8)
    deficit = update_deficit(deficit, et_mm=6.0, precip_mm=2.0, et_coefficient=0.8)
    assert deficit == pytest.approx(7.6)


def test_compute_duration_basic():
    result = compute_duration_seconds(
        deficit_mm=10.0,
        application_rate_mm_per_min=2.0,
        max_duration_seconds=1800,
    )
    assert result == 300


def test_compute_duration_capped_by_max():
    result = compute_duration_seconds(
        deficit_mm=100.0,
        application_rate_mm_per_min=2.0,
        max_duration_seconds=600,
    )
    assert result == 600


def test_compute_duration_zero_rate_returns_max():
    result = compute_duration_seconds(
        deficit_mm=10.0,
        application_rate_mm_per_min=0.0,
        max_duration_seconds=900,
    )
    assert result == 900
