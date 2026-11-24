"""The ONLY file of the service that imports scikit-learn, joblib or pandas.

To swap the model (ONNX, a remote model server), add a sibling adapter and change one line
in the composition root. Nothing in domain/ or service/ changes.

SECURITY: a .joblib file is a pickle, and loading a pickle can run any code inside it.
Only load model files from a place you control.
"""
import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn

from card_fraud.service.ports import ModelCard

log = logging.getLogger(__name__)


class SklearnScoringModel:
    def __init__(self, estimator: Any, feature_names: Sequence[str], model_version: str) -> None:
        self._estimator = estimator
        self._feature_names = list(feature_names)
        self.model_version = model_version

    def predict_scores(self, rows: Sequence[Mapping[str, float]]) -> list[float]:
        frame = pd.DataFrame(list(rows), columns=self._feature_names)
        return [float(p) for p in self._estimator.predict_proba(frame)[:, 1]]


def load_model_card(info_path: Path) -> ModelCard:
    info = json.loads(Path(info_path).read_text(encoding="utf-8"))
    return ModelCard(
        model_version=info["model_version"],
        feature_names=tuple(info["features"]),
        threshold=float(info["threshold"]),
        typical_values={k: float(v) for k, v in info["typical_values"].items()},
        test_metrics=info.get("test_metrics", {}),
    )


def load_sklearn_model(model_path: Path, info_path: Path) -> tuple[SklearnScoringModel, ModelCard]:
    """Explicit, failable loading: called by an entry point at start-up, never at import."""
    card = load_model_card(info_path)
    info = json.loads(Path(info_path).read_text(encoding="utf-8"))
    trained_with = info.get("scikit_learn_version")
    if trained_with and trained_with != sklearn.__version__:
        log.warning("model trained with scikit-learn %s but running %s: scores may differ",
                    trained_with, sklearn.__version__)
    estimator = joblib.load(model_path)
    known = list(getattr(estimator, "feature_names_in_", card.feature_names))
    if known != list(card.feature_names):
        raise ValueError("model_info.json features do not match the model's inputs")
    return SklearnScoringModel(estimator, card.feature_names, card.model_version), card
