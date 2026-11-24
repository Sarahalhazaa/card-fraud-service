"""Domain: the fraud team's rule, and what the service answers.

Thresholds are BUSINESS decisions, not model decisions: a risk officer can read this file.
"""
from dataclasses import dataclass
from enum import StrEnum


class Decision(StrEnum):
    ALLOW = "allow"    # let the payment through
    REVIEW = "review"  # send to the fraud team for a check (the notebook's "ALERT")
    BLOCK = "block"    # stop the payment, then a person checks it


@dataclass(frozen=True)
class AlertPolicy:
    review_threshold: float
    block_threshold: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.review_threshold <= self.block_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= review <= block <= 1")

    def decide(self, fraud_score: float) -> Decision:
        if fraud_score >= self.block_threshold:
            return Decision.BLOCK
        if fraud_score >= self.review_threshold:
            return Decision.REVIEW
        return Decision.ALLOW


@dataclass(frozen=True)
class Reason:
    """One input and how much the score falls if that input alone were typical."""

    input_name: str
    value: float
    typical: float
    score_if_typical: float
    drop: float


@dataclass(frozen=True)
class Assessment:
    payment_id: str | None
    fraud_score: float
    decision: Decision
    policy: AlertPolicy
    model_version: str
    reasons: tuple[Reason, ...]
