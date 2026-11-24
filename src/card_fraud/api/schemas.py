"""Wire contract: the shapes clients send and receive. Keep them stable.

These models exist for the outside world. Routes convert them to domain objects in two lines;
they never travel inward.
"""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from card_fraud.domain.assessment import Decision

# strict=True: a number must be a JSON number ("250" and true are rejected).
# allow_inf_nan=False: no NaN or infinity.
AnonymousInput = Annotated[float, Field(strict=True, allow_inf_nan=False,
                                        description="Anonymous bank input (meaning not published)")]


class PaymentRequest(BaseModel):
    """One card payment, in the dataset's own column names."""

    model_config = ConfigDict(extra="forbid")  # an unknown field is a typo or a probe: reject it

    payment_id: str | None = Field(None, max_length=64, examples=["PAY-2026-00042"],
                                   description="Your own reference, echoed back. Optional.")
    Time: float = Field(strict=True, allow_inf_nan=False, ge=0, le=10_000_000,
                        description="Seconds since the first payment in the data file")
    Amount: float = Field(strict=True, allow_inf_nan=False, ge=0, le=1_000_000,
                          description="Amount paid (the dataset does not name the currency)")
    V1: AnonymousInput
    V2: AnonymousInput
    V3: AnonymousInput
    V4: AnonymousInput
    V5: AnonymousInput
    V6: AnonymousInput
    V7: AnonymousInput
    V8: AnonymousInput
    V9: AnonymousInput
    V10: AnonymousInput
    V11: AnonymousInput
    V12: AnonymousInput
    V13: AnonymousInput
    V14: AnonymousInput
    V15: AnonymousInput
    V16: AnonymousInput
    V17: AnonymousInput
    V18: AnonymousInput
    V19: AnonymousInput
    V20: AnonymousInput
    V21: AnonymousInput
    V22: AnonymousInput
    V23: AnonymousInput
    V24: AnonymousInput
    V25: AnonymousInput
    V26: AnonymousInput
    V27: AnonymousInput
    V28: AnonymousInput


class ReasonOut(BaseModel):
    input: str = Field(description="Input name, for example V14")
    value: float
    typical: float = Field(description="Its usual value among normal payments")
    score_if_typical: float = Field(description="The fraud score if this input alone were typical")
    drop: float = Field(description="How much the score falls: bigger means a stronger reason")


class ScoreResponse(BaseModel):
    payment_id: str | None
    fraud_score: float = Field(ge=0, le=1)
    decision: Decision
    review_threshold: float
    block_threshold: float
    model_version: str
    reasons: list[ReasonOut]
    trace_id: str


class ModelInfoResponse(BaseModel):
    model_version: str
    review_threshold: float
    block_threshold: float
    inputs: list[str]
    test_metrics: dict[str, float]


class HealthResponse(BaseModel):
    status: str
    git_sha: str
