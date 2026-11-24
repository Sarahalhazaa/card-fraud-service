"""Domain: what a card payment is, and how it becomes model inputs.

Rules for every file in domain/:
- standard library only (no pandas, no scikit-learn, no FastAPI)
- no files, no network, no printing
"""
import math
from dataclasses import dataclass

V_NAMES: tuple[str, ...] = tuple(f"V{i}" for i in range(1, 29))
FEATURE_NAMES: tuple[str, ...] = (*V_NAMES, "Amount", "hour")
SECONDS_PER_HOUR = 3600


def hour_of_day(time_seconds):
    """Turn "seconds since the first payment in the file" into the hour of the day.

    The ONE place this rule lives. Training calls it on a whole pandas column and the
    service calls it on one number, so training and serving can never disagree.
    """
    return (time_seconds // SECONDS_PER_HOUR) % 24


@dataclass(frozen=True)
class Payment:
    """One card payment, in the format of the dataset."""

    time_seconds: float
    amount: float
    v: tuple[float, ...]  # V1 .. V28, in order
    payment_id: str | None = None

    def __post_init__(self) -> None:
        if len(self.v) != len(V_NAMES):
            raise ValueError(f"a payment needs {len(V_NAMES)} V values, got {len(self.v)}")
        values = (self.time_seconds, self.amount, *self.v)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("payment values must be finite numbers")
        if self.amount < 0:
            raise ValueError("amount cannot be negative")
        if self.time_seconds < 0:
            raise ValueError("time cannot be negative")

    def to_features(self) -> dict[str, float]:
        """The model inputs, by name, exactly as in training."""
        features = dict(zip(V_NAMES, self.v, strict=True))
        features["Amount"] = self.amount
        features["hour"] = float(hour_of_day(self.time_seconds))
        return features
