import { useEffect, useState } from "react";
import fraudSample from "../../payloads/notebook_fraud.json?raw";
import normalSample from "../../payloads/normal.json?raw";

const SAMPLES = [
  { label: "Notebook fraud example", text: fraudSample },
  { label: "Normal payment", text: normalSample },
];

const DECISION_TEXT = {
  allow: "Allow",
  review: "Send to the fraud team",
  block: "Block, then a person checks",
};

export default function App() {
  const [model, setModel] = useState(null);
  const [text, setText] = useState(SAMPLES[0].text);
  const [result, setResult] = useState(null);
  const [problems, setProblems] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/v1/model")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setModel)
      .catch(() => setModel(null));
  }, []);

  async function score() {
    setResult(null);
    setProblems([]);
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      setProblems(["The text is not valid JSON."]);
      return;
    }
    setBusy(true);
    try {
      const r = await fetch("/v1/score", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok) {
        setResult(data);
      } else if (data.error?.details) {
        setProblems(data.error.details.map((d) => `${d.field}: ${d.problem}`));
      } else {
        setProblems([data.error?.message || data.detail || `Request failed (${r.status})`]);
      }
    } catch {
      setProblems(["Cannot reach the service. Is it running on port 8000?"]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header>
        <h1>Card fraud check</h1>
        <p className="warning">
          Teaching model: it misses about one fraud in four. Never block a card or accuse anyone
          without a human check.
        </p>
        {model ? (
          <p className="muted">
            Model {model.model_version} · review from {model.review_threshold} · block from{" "}
            {model.block_threshold} · caught {model.test_metrics.frauds_caught} of{" "}
            {model.test_metrics.frauds_caught + model.test_metrics.missed_frauds} test frauds
          </p>
        ) : (
          <p className="muted">Service not reachable.</p>
        )}
      </header>

      <div className="grid">
        <section>
          <h2>Payment</h2>
          <div className="row">
            {SAMPLES.map((s) => (
              <button key={s.label} className="secondary" onClick={() => setText(s.text)}>
                {s.label}
              </button>
            ))}
          </div>
          <label htmlFor="payment">Payment as JSON (Time, Amount, V1 to V28)</label>
          <textarea
            id="payment"
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
          />
          <button onClick={score} disabled={busy}>
            {busy ? "Checking…" : "Check payment"}
          </button>
        </section>

        <section aria-live="polite">
          <h2>Result</h2>
          {problems.length > 0 && (
            <div className="problems" role="alert">
              <strong>The request was not accepted</strong>
              <ul>
                {problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {result && <Result r={result} />}
          {!result && problems.length === 0 && (
            <p className="muted">Pick an example or paste a payment, then check it.</p>
          )}
        </section>
      </div>
    </main>
  );
}

function Result({ r }) {
  const pct = (x) => `${(x * 100).toFixed(1)}%`;
  return (
    <div>
      <div className={`badge ${r.decision}`}>{DECISION_TEXT[r.decision]}</div>
      <p className="score">
        Fraud score <strong>{r.fraud_score.toFixed(4)}</strong>
        {r.payment_id && <span className="muted"> · {r.payment_id}</span>}
      </p>

      <div className="bar" role="img" aria-label={`Score ${pct(r.fraud_score)}`}>
        <div className="fill" style={{ width: pct(r.fraud_score) }} />
        <span className="tick" style={{ left: pct(r.review_threshold) }} title="review" />
        <span className="tick" style={{ left: pct(r.block_threshold) }} title="block" />
      </div>
      <p className="muted small">
        Marks: review at {r.review_threshold}, block at {r.block_threshold}
      </p>

      <h3>Top reasons</h3>
      <table>
        <thead>
          <tr>
            <th>Input</th>
            <th>Value</th>
            <th>Typical</th>
            <th>Score drops by</th>
          </tr>
        </thead>
        <tbody>
          {r.reasons.map((x) => (
            <tr key={x.input}>
              <td>{x.input}</td>
              <td>{x.value}</td>
              <td>{x.typical}</td>
              <td>{x.drop.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        "Score drops by": how far the score falls if this input alone were typical. Bigger means a
        stronger reason. Trace id {r.trace_id}.
      </p>
    </div>
  );
}
