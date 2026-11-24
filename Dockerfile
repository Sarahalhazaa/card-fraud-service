# ---------- Stage 1: builder (thrown away after the build) ----------
FROM python:3.12-slim AS builder

# Install the locked libraries into their own folder. If a library ever needs compiling,
# install build tools HERE: nothing from this stage reaches the final image except /opt/venv.
COPY requirements.lock .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.lock

# ---------- Stage 2: runtime (what we ship) ----------
FROM python:3.12-slim AS runtime

# A normal user: the first thing any security review checks
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

# Order = slow and stable first, fast and changing last (layer cache)
# 1) Libraries: hundreds of MB, change rarely
COPY --from=builder /opt/venv /opt/venv
# 2) Model and its facts: change when we retrain, not on every commit
COPY artifacts/fraud_model.joblib artifacts/model_info.json /models/
# 3) Our code: a few KB, changes every commit, so it goes LAST
COPY src/ /app/src

ARG GIT_SHA=dev
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 \
    FRAUD_MODEL_PATH=/models/fraud_model.joblib \
    FRAUD_MODEL_INFO_PATH=/models/model_info.json \
    FRAUD_GIT_SHA=$GIT_SHA

USER appuser
EXPOSE 8000

# Healthcheck on READINESS (model loaded), using Python itself: no curl needed in the image
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/ready', timeout=2)"]

# Exec form: uvicorn is process 1, receives the stop signal, and shuts down cleanly
CMD ["uvicorn", "card_fraud.api.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
