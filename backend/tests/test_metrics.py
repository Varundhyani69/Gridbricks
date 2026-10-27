from math import sqrt

import pytest

from app.analytics.metrics import calculate_metrics


def test_perfect_forecasts_have_zero_error_metrics() -> None:
    metrics = calculate_metrics([(100, 100), (250, 250)])

    assert metrics.mae_mw == 0
    assert metrics.rmse_mw == 0
    assert metrics.mbe_mw == 0
    assert metrics.matched_intervals == 2


def test_metrics_use_forecast_minus_actual_sign_convention() -> None:
    overforecast = calculate_metrics([(120, 100), (130, 100)])
    underforecast = calculate_metrics([(80, 100), (90, 100)])

    assert overforecast.mbe_mw == 25
    assert underforecast.mbe_mw == -15


def test_mae_and_rmse_match_hand_calculated_example() -> None:
    metrics = calculate_metrics([(12, 10), (6, 10)])

    assert metrics.mae_mw == 3
    assert metrics.rmse_mw == pytest.approx(sqrt(10))
    assert metrics.mbe_mw == -1
    assert metrics.matched_intervals == 2


def test_empty_matched_sample_has_null_metrics() -> None:
    metrics = calculate_metrics([])

    assert metrics.mae_mw is None
    assert metrics.rmse_mw is None
    assert metrics.mbe_mw is None
    assert metrics.matched_intervals == 0
