# Project journal

**Group:** ____ (agent: Claude, Opus 5.5)
**Track:** fraud
**Repository:** ____

---

## Stage 1: Clean architecture

**What we asked the agent**
I asked it to split the notebook into a domain (payment, score, threshold rule, reasons), services and adapters, with all settings in one place.

**What it built**
- `domain/`: the payment and its 30 model inputs, the hour-of-day rule, and the allow/review/block rule. Python standard library only.
- `service/`: `FraudScorer` and the "what if the value were typical?" explanation. It knows nothing about scikit-learn.
- `adapters/`: loading the model with scikit-learn and reading the data file.
- `config.py`: every setting, for both the service and training.
- `legacy/notebook_reference.py` and `scripts/check_golden.py`: the notebook's original answers, and the comparison against them.

**What we checked, and what we saw**
I ran `make reference`, then `make train`, then `make golden`. The threshold came out at 0.4, and the model caught 56 of the 75 frauds (65 alerts, 9 of them false alarms, and 19 frauds missed). Average precision was 0.789. The 5 sample payments gave exactly the same results as the notebook; for example, the notebook's last payment scored 0.998861 with V14 as the top reason in both.

Then I broke it on purpose. I changed `% 24` to `% 12` in `hour_of_day` and retrained, and the golden check failed on 9 numbers. For example, alerts went from 65 to 64, frauds caught from 56 to 55, and average precision became 0.795. I put the line back and the check passed again.

**What surprised us or went wrong**
The data download failed the first time with an SSL error (`CERTIFICATE_VERIFY_FAILED`), because Python on macOS could not find the system certificates. I did not turn off certificate checking. I pointed `SSL_CERT_FILE` at the certifi bundle instead, and it worked. I was also surprised that changing one number in the hour rule moved almost every golden number, so the check is clearly sensitive.

**How we would explain this stage to a colleague**
I separated the rules from the tools. The "hour from time" rule is written once, in the domain, and both training and the service use it, so they cannot disagree. The threshold is a business rule that changes through settings; it is not buried inside the model code. If the model changes, only one adapter file changes.

**Open questions**
The model misses about one fraud in every four (19 of 75). Do we accept that, or lower the threshold and live with more false alarms?

---

## Stage 2: FastAPI endpoint

**What we asked the agent**
I send one payment and get back the fraud score, the decision and the top reasons.

**What it built**
`api/schemas.py` (the shape of the request and the response), `api/routes.py` (`/v1/score`, `/v1/model`, `/v1/health` and `/v1/ready`), and `api/app.py` (loads the model once at start-up, adds a trace id, and gives every error the same shape).

**What we checked, and what we saw**
Valid request (`payloads/notebook_fraud.json`): 200, fraud score 0.998861, decision `block`, top reasons V14 (drop 0.85), V10 (0.72) and V4 (0.02). The score matches the notebook's.
Invalid request (`payloads/bad/missing_v14.json`): 422 `INVALID_REQUEST`, naming the field `V14` with "Field required". I also tried the other 5 bad files (empty body, negative amount, amount as text, unknown field, typo in `Amount`) and all got a 422 that names the field and never repeats the value I sent.
Readiness checks that the model is loaded; health only checks that the process is running. Both returned 200 once the service was up.

**What surprised us or went wrong**
The `typo_amount.json` request gives two errors at once: `Amount` is missing and `amount` is not permitted. That is actually helpful, because it shows the typo. I also noticed that `/v1/health` stays 200 even if the model failed to load, which is why the container check uses `/v1/ready`.

**How we would explain this stage to a colleague**
The API is a door with clear rules. Any request that is incomplete or wrong is rejected with a 422 before it reaches the model, and the error message names the field without repeating its value. The decision has three outcomes: allow, review (the threshold from training) and block (a new business rule at 0.9, which can be changed in settings).

**Open questions**
Is 0.9 the right threshold for block? Who decides? The fraud team should decide, and I have not agreed 0.9 with them yet; I only know it is a new rule the notebook did not have.

---

## Stage 3: Container

**What we asked the agent**
I asked it to package the service with Docker so it runs the same way everywhere.

**What it built**
`requirements.lock` (26 libraries at fixed versions), a two-stage `Dockerfile`, a non-root user, a health check on `/v1/ready`, a `.dockerignore` and a `docker-compose.yml`.

**What we checked, and what we saw**
Image size 731 MB. The first build took 210 s (nothing cached). After changing one line of code, the rebuild took 1 s, because only the last small layer changed. The user is `appuser`, not root (`docker run --rm card-fraud-service:dev whoami`). The model sits inside the image at `/models/` (about 600 KB). I started the container and it reached `healthy` through the `/v1/ready` check, and a real request to `/v1/score` returned the same 0.998861 as before.

**What surprised us or went wrong**
The image is 731 MB, bigger than I expected for "small"; most of it is the scikit-learn, pandas and numpy libraries. Also, `make image` failed at first because the folder was not a git repository and it calls `git rev-parse`; I built with the default `GIT_SHA=dev` instead.

**How we would explain this stage to a colleague**
The image holds everything the service needs: Python 3.12, the locked libraries, the model and the code. I ordered the layers from slowest-changing to fastest-changing, so editing the code rebuilds only a small layer. It contains no secrets and runs as a normal user.

**Open questions**
Can we make the image smaller, for example by dropping pandas from the runtime if only training needs it?
