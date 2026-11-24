"""What the service needs from the outside world, described as small interfaces ("ports").

The service knows ONLY these shapes. scikit-learn, joblib and JSON files live in adapters/.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class ScoringModel(Protocol):
    """Anything that can give fraud scores to rows of model inputs.

    Implementations: SklearnScoringModel (real), a fake model in tests, a remote model later.
    """

    model_version: str

    def predict_scores(self, rows: Sequence[Mapping[str, float]]) -> list[float]:
        """One fraud score between 0 and 1 for each row, in the same order."""
        ...


@dataclass(frozen=True)
class ModelCard:
    """The facts saved next to the model during training (artifacts/model_info.json)."""

    model_version: str
    feature_names: tuple[str, ...]
    threshold: float  # the "review" threshold chosen on the validation payments
    typical_values: Mapping[str, float]  # median of each input among normal payments
    test_metrics: Mapping[str, float]
