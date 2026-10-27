from collections.abc import Sequence
from math import sqrt

from app.models import AccuracyMetrics


def calculate_metrics(pairs: Sequence[tuple[float, float]]) -> AccuracyMetrics:
    if not pairs:
        return AccuracyMetrics(mae_mw=None, rmse_mw=None, mbe_mw=None, matched_intervals=0)

    errors = [forecast - actual for forecast, actual in pairs]
    return AccuracyMetrics(
        mae_mw=sum(abs(error) for error in errors) / len(errors),
        rmse_mw=sqrt(sum(error * error for error in errors) / len(errors)),
        mbe_mw=sum(errors) / len(errors),
        matched_intervals=len(errors),
    )
