# Card fraud scoring service

SDA-AIE-113 final project, fraud track. The notebook `tracks/fraud/notebook.ipynb` reorganised
into a service: clean architecture (stage 1), a FastAPI endpoint (stage 2) and a container
(stage 3).

> Teaching model trained on two days of 2013 data. It misses about one fraud in four. Never use
> it to block cards or accuse anyone without a human check.

## Run it (macOS / Linux)

```bash
python3 -m venv .venv && source .venv/bin/activate
make install          # the project and dev tools
make reference        # once: the notebook's own code saves its answers in golden/ (downloads 150 MB)
make train            # the new code trains the model into artifacts/
make golden           # proof: the new code gives the notebook's answers
make score            # score the notebook's example payment from the command line
make run              # API on http://localhost:8000/docs
```

In the container:

```bash
make lock             # only when dependencies change
make image            # build card-fraud-service:dev
make up               # start it with Docker Compose, wait for (healthy) in: docker compose ps
make smoke            # ready + one real request
make down
```

## Folder tree

```
src/card_fraud/
├── domain/              the words and rules of the problem. Standard library only.
│   ├── payment.py         a payment, its 30 model inputs, the hour-of-day rule
│   └── assessment.py      allow / review / block rule, a reason, the answer
├── service/             the job "assess one payment". Knows no library and no file.
│   ├── ports.py           what the service needs: a ScoringModel, a ModelCard
│   ├── reasons.py         the notebook's "what if typical?" explanation
│   └── scorer.py          FraudScorer: inputs -> score -> decision -> top reasons
├── adapters/            the tools. The only place scikit-learn, joblib and files appear.
│   ├── sklearn_model.py   loads artifacts/ and scores rows with scikit-learn
│   └── payments_csv.py    downloads and reads the training CSV
├── training/pipeline.py the notebook's training steps as small functions
├── api/                 entry point 1: the web (schemas, routes, app)
├── train.py             entry point 2: python -m card_fraud.train
├── score_one.py         entry point 3: python -m card_fraud.score_one payment.json
├── composition.py       the one place concrete classes are wired together
└── config.py            ALL settings (service and training), from env variables or .env
legacy/notebook_reference.py   the notebook's code, kept only to produce the golden answers
scripts/check_golden.py        compares the new code with those answers
golden/                        the notebook's answers for 5 payments and its test numbers
artifacts/                     the trained model and model_info.json (small, committed)
payloads/                      example requests, good and bad
```

**Import directions** (inner parts never import outer parts):

```
api, train.py, score_one.py  ->  composition  ->  adapters  ->  service  ->  domain
training/pipeline.py  ->  domain (the hour rule and input order: no training/serving skew)
```

**Which file changes if…**

| Change | File |
|---|---|
| a new model (ONNX, a model server) | a new adapter + one line in `composition.py` |
| a new data source | `adapters/payments_csv.py` |
| the fraud team's thresholds | `configs/*.env` or `FRAUD_*` env variables (no code) |
| the meaning of "review" or "block" | `domain/assessment.py` |
| the request shape | `api/schemas.py` |

## The API

| Endpoint | What it does |
|---|---|
| `POST /v1/score` | one payment in; fraud score, decision and top reasons out |
| `GET /v1/model` | model version, thresholds, test results |
| `GET /v1/health` | liveness: the process is up (no model check) |
| `GET /v1/ready` | readiness: the model is loaded (the container healthcheck uses this) |

Decisions: `allow` below the review threshold; `review` (send to the fraud team) from the
threshold chosen in training (0.4 in the notebook); `block` from 0.9. **The block threshold is a
new business rule the notebook does not have**: agree on it with the fraud team and change it in
`configs/dev.env`.

Bad requests (missing V14, negative amount, a number sent as text, an unknown field) get
`422 {"error": {"code": "INVALID_REQUEST", ...}}`, naming the field but never echoing its value.

## Choices worth explaining

- **The model lives inside the image.** It is small (about 600 KB), so one image = one model
  version, and rolling back is one command. `artifacts/` is committed for the same reason; the
  150 MB dataset is not.
- **`/ready`, not `/health`, for the healthcheck**, so the container is "healthy" only once the
  model is loaded.
- **The healthcheck uses Python**, so the image needs no `curl`.
- **26 locked libraries** (no `fastapi[standard]`): a smaller image.
