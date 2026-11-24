"""Composition root: the one place where concrete classes are wired together.

Both entry points (the API and the command line) build the scorer here, so they always
behave the same. To replace the model, change the adapter used in this function.
"""
from card_fraud.adapters.sklearn_model import load_sklearn_model
from card_fraud.config import ServiceSettings
from card_fraud.domain.assessment import AlertPolicy
from card_fraud.service.ports import ModelCard
from card_fraud.service.scorer import FraudScorer


def build_scorer(settings: ServiceSettings) -> tuple[FraudScorer, ModelCard]:
    model, card = load_sklearn_model(settings.model_path, settings.model_info_path)
    review = settings.review_threshold if settings.review_threshold is not None else card.threshold
    policy = AlertPolicy(review_threshold=review, block_threshold=settings.block_threshold)
    scorer = FraudScorer(model, card.typical_values, policy, top_reasons=settings.top_reasons)
    return scorer, card
