"""HTTP routes. Thin: convert the request to a domain Payment, call the scorer, convert back."""
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from card_fraud.api.schemas import (
    HealthResponse,
    ModelInfoResponse,
    PaymentRequest,
    ReasonOut,
    ScoreResponse,
)
from card_fraud.domain.payment import V_NAMES, Payment
from card_fraud.service.ports import ModelCard
from card_fraud.service.scorer import FraudScorer

router = APIRouter()


def get_scorer(request: Request) -> FraudScorer:
    """Dependency-injection seam: tests replace this one function to use a fake model."""
    scorer = getattr(request.app.state, "scorer", None)
    if scorer is None:  # start-up incomplete or failed
        raise HTTPException(status_code=503, detail="Model not ready", headers={"Retry-After": "5"})
    return scorer


def get_model_card(request: Request) -> ModelCard:
    card = getattr(request.app.state, "model_card", None)
    if card is None:
        raise HTTPException(status_code=503, detail="Model not ready", headers={"Retry-After": "5"})
    return card


@router.post("/score", response_model=ScoreResponse)
def score(body: PaymentRequest, request: Request, response: Response,
          scorer: Annotated[FraudScorer, Depends(get_scorer)]):
    # Plain `def`: scoring is CPU work, so FastAPI runs it in a worker thread.
    payment = Payment(
        time_seconds=body.Time,
        amount=body.Amount,
        v=tuple(getattr(body, name) for name in V_NAMES),
        payment_id=body.payment_id,
    )
    result = scorer.assess(payment)
    response.headers["X-Model-Version"] = result.model_version
    return ScoreResponse(
        payment_id=result.payment_id,
        fraud_score=round(result.fraud_score, 6),
        decision=result.decision,
        review_threshold=result.policy.review_threshold,
        block_threshold=result.policy.block_threshold,
        model_version=result.model_version,
        reasons=[
            ReasonOut(input=r.input_name, value=round(r.value, 6), typical=round(r.typical, 6),
                      score_if_typical=round(r.score_if_typical, 6), drop=round(r.drop, 6))
            for r in result.reasons
        ],
        trace_id=request.state.trace_id,
    )


@router.get("/model", response_model=ModelInfoResponse)
def model_info(scorer: Annotated[FraudScorer, Depends(get_scorer)],
               card: Annotated[ModelCard, Depends(get_model_card)]):
    """What model is running, its thresholds, and how well it did on the test payments."""
    return ModelInfoResponse(
        model_version=card.model_version,
        review_threshold=scorer.policy.review_threshold,
        block_threshold=scorer.policy.block_threshold,
        inputs=list(card.feature_names),
        test_metrics={k: float(v) for k, v in card.test_metrics.items()},
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    """Liveness: the process is up. No model check, no I/O."""
    return HealthResponse(status="ok", git_sha=request.app.state.settings.git_sha)


@router.get("/ready")
def ready(request: Request):
    """Readiness: safe to receive traffic, because the model is loaded."""
    if getattr(request.app.state, "scorer", None) is None:
        raise HTTPException(status_code=503, detail="warming up", headers={"Retry-After": "5"})
    return {"status": "ready", "checked_at": datetime.now(UTC)}
