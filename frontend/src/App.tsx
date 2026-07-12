import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

export type Opportunity = {
  posting_id: string;
  title: string;
  company: string;
  location: string;
  recommendation: "pursue" | "consider" | "reject";
  ranking_score: number;
  review_decision: ReviewChoice | null;
};

type IntakeResult = {
  posting_id: string;
  evaluation_id: string;
  identity_status: string;
  title: string;
  company: string;
  location: string;
  recommendation: "pursue" | "consider" | "reject";
  confidence: string;
  ranking_score: number;
  reasons: string[];
};

type ReviewChoice = "pursue" | "consider" | "defer" | "reject" | "needs_more_information";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export function App() {
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [intake, setIntake] = useState<IntakeResult | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refreshOpportunities = useCallback(async () => {
    const response = await fetch(`${API_BASE}/api/opportunities`);
    if (!response.ok) throw new Error("Unable to load opportunities.");
    setOpportunities((await response.json()) as Opportunity[]);
  }, []);

  useEffect(() => {
    refreshOpportunities().catch(() => setError("The JOLT API is not available."));
  }, [refreshOpportunities]);

  async function submitIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/intake/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_url: sourceUrl, raw_text: rawText }),
      });
      if (!response.ok) throw new Error("The opportunity could not be processed.");
      setIntake((await response.json()) as IntakeResult);
      await refreshOpportunities();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected intake error.");
    } finally {
      setBusy(false);
    }
  }

  async function review(decision: ReviewChoice) {
    if (!intake) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/opportunities/${intake.posting_id}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ evaluation_id: intake.evaluation_id, decision }),
      });
      if (!response.ok) throw new Error("The review decision could not be saved.");
      await refreshOpportunities();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected review error.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Job Opportunity Learning & Tracking</p>
        <h1>JOLT</h1>
        <p>Turn a job description into an auditable recommendation and a human decision.</p>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      <section className="panel" aria-labelledby="intake-heading">
        <h2 id="intake-heading">Manual opportunity intake</h2>
        <form onSubmit={submitIntake}>
          <label>
            Source URL <span>(optional)</span>
            <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} type="url" />
          </label>
          <label>
            Job text
            <textarea
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              required
              rows={10}
              placeholder={"Job title\nCompany\nLocation: Remote Spain\nFull description..."}
            />
          </label>
          <button disabled={busy || !rawText.trim()} type="submit">
            {busy ? "Processing…" : "Evaluate opportunity"}
          </button>
        </form>
      </section>

      {intake && (
        <section className="panel result" aria-labelledby="result-heading">
          <div>
            <p className="eyebrow">{intake.identity_status.replaceAll("_", " ")}</p>
            <h2 id="result-heading">{intake.title || "Untitled opportunity"}</h2>
            <p>{[intake.company, intake.location].filter(Boolean).join(" · ")}</p>
          </div>
          <div className="recommendation">
            <strong>{intake.recommendation}</strong>
            <span>Rule score {intake.ranking_score} · {intake.confidence} confidence</span>
          </div>
          <ul>{intake.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          <div className="review-actions" aria-label="Record your decision">
            {(["pursue", "consider", "defer", "reject", "needs_more_information"] as const).map((choice) => (
              <button type="button" disabled={busy} onClick={() => review(choice)} key={choice}>
                {choice.replaceAll("_", " ")}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="panel" aria-labelledby="queue-heading">
        <h2 id="queue-heading">Opportunity queue</h2>
        {opportunities.length === 0 ? (
          <p>No opportunities saved yet.</p>
        ) : (
          <div className="queue">
            {opportunities.map((opportunity) => (
              <article key={opportunity.posting_id}>
                <div>
                  <h3>{opportunity.title || "Untitled opportunity"}</h3>
                  <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                </div>
                <div className="queue-status">
                  <strong>{opportunity.review_decision ?? "pending review"}</strong>
                  <span>{opportunity.recommendation} · {opportunity.ranking_score}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
