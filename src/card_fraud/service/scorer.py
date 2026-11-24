"""Use case: assess one payment (score, decide, explain).

Notice what is ABSENT: no FastAPI, no scikit-learn, no file paths, no environment variables.
"""
from collections.abc import Mapping

from card_fraud.domain.assessment import AlertPolicy, Assessment
from card_fraud.domain.payment import FEATURE_NAMES, Payment
from card_fraud.service.ports import ScoringModel
from card_fraud.service.reasons import what_if_typical


class FraudScorer:
    def __init__(
        self,
        model: ScoringModel,
        typical_values: Mapping[str, float],
        policy: AlertPolicy,
        top_reasons: int = 3,
    ) -> None:
        missing = [name for name in FEATURE_NAMES if name not in typical_values]
        if missing:
            raise ValueError(f"typical values missing for: {missing}")
        self.model = model
        self.typical_values = dict(typical_values)
        self.policy = policy
        self.top_reasons = top_reasons

    def assess(self, payment: Payment) -> Assessment:
        features = payment.to_features()                      # domain: inputs
        score, reasons = what_if_typical(                     # model, through the port
            self.model, features, self.typical_values)
        return Assessment(
            payment_id=payment.payment_id,
            fraud_score=score,
            decision=self.policy.decide(score),               # domain: business rule
            policy=self.policy,
            model_version=self.model.model_version,
            reasons=tuple(reasons[: self.top_reasons]),
        )
