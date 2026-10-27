import os
from datetime import time
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
ELEXON_API_BASE_URL = os.getenv("ELEXON_API_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
ELEXON_TIMEOUT_SECONDS = float(os.getenv("ELEXON_TIMEOUT_SECONDS", "20"))


def get_decision_cutoff() -> time:
    value = os.getenv("DECISION_CUTOFF_LOCAL", "10:00")
    if len(value) != 5 or value[2] != ":":
        raise ValueError("DECISION_CUTOFF_LOCAL must be a local time in HH:MM format")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("DECISION_CUTOFF_LOCAL must be a local time in HH:MM format") from exc
