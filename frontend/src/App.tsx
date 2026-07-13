import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { AutomatedReview } from "./AutomatedReview";
import { CaptureHistory } from "./CaptureHistory";

type ReviewChoice = "pursue" | "consider" | "defer" | "reject" | "needs_more_information";
type ApplicationStatus =
  | "preparing" | "submitted" | "acknowledged" | "recruiter_screen"
  | "technical_interview" | "hiring_manager_interview" | "final_interview"
  | "offer" | "rejected" | "withdrawn" | "no_response" | "closed";
type QueueFilter = "all" | "pending" | "pursue" | "active";

export type Opportunity = {
  posting_id: string;
  evaluation_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  recommendation: "pursue" | "consider" | "reject";
  proposed_decision: ReviewChoice;
  confidence: string;
  ranking_score: number;
  fit_summary: string;
  strengths: string[];
  gaps: string[];
  blockers: string[];
  uncertainties: string[];
  dimensions: Record<string, number>;
  reasons: string[];
  profile_version_id: string;
  engine_version: string;
  review_decision: ReviewChoice | null;
  application_id?: string | null;
  application_status?: ApplicationStatus | null;
  outcome_type?: string | null;
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

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const REVIEW_CHOICES: ReviewChoice[] = [
  "pursue", "consider", "defer", "reject", "needs_more_information",
];

export function App() {
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [intake, setIntake] = useState<IntakeResult | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [queueFilter, setQueueFilter] = useState<QueueFilter>("all");
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

  const visibleOpportunities = useMemo(() => {
    const filtered = opportunities.filter((opportunity) => {
      if (queueFilter === "pending") return !opportunity.review_decision;
      if (queueFilter === "pursue") return opportunity.review_decision === "pursue";
      if (queueFilter === "active") return Boolean(opportunity.application_id && !opportunity.outcome_type);
      return true;
    });
    return [...filtered].sort((left, right) => right.ranking_score - left.ranking_score);
  }, [opportunities, queueFilter]);

  const counts = useMemo(() => ({
    all: opportunities.length,
    pending: opportunities.filter((item) => !item.review_decision).length,
    pursue: opportunities.filter((item) => item.review_decision === "pursue").length,
    active: opportunities.filter((item) => item.application_id && !item.outcome_type).length,
  }), [opportunities]);

  async function apiAction(url: string, body: object) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}${url}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error("The workflow change could not be saved.");
      await refreshOpportunities();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected workflow error.");
    } finally {
      setBusy(false);
    }
  }

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

  async function reviewOpportunity(postingId: string, evaluationId: string, decision: ReviewChoice) {
    await apiAction(`/api/opportunities/${postingId}/reviews`, {
      evaluation_id: evaluationId,
      decision,
    });
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Job Opportunity Learning & Tracking</p>
        <h1>JOLT</h1>
        <p>Turn job evidence into an auditable decision, application workflow, and outcome history.</p>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      <section className="panel" aria-labelledby="export-heading">
        <h2 id="export-heading">Analysis and feedback</h2>
        <p>Export the complete evidence chain as JSON, CSV, and a readable Markdown summary.</p>
        <a href={`${API_BASE}/api/exports/analysis-pack`} download="JOLT_ANALYSIS_PACK.zip">
          Download analysis pack
        </a>
      </section>

      <CaptureHistory apiBase={API_BASE} onError={setError} />

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
              required rows={10}
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
            {REVIEW_CHOICES.map((choice) => (
              <button type="button" disabled={busy} onClick={() => reviewOpportunity(intake.posting_id, intake.evaluation_id, choice)} key={choice}>
                {choice.replaceAll("_", " ")}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="panel" aria-labelledby="queue-heading">
        <div className="section-heading">
          <div>
            <h2 id="queue-heading">Opportunity review workbench</h2>
            <p>JOLT proposes an evidence-backed decision. You confirm or override it before any application starts.</p>
          </div>
          <button type="button" className="secondary" disabled={busy} onClick={() => refreshOpportunities()}>
            Refresh queue
          </button>
        </div>

        <div className="queue-filters" aria-label="Filter opportunities">
          {(["all", "pending", "pursue", "active"] as QueueFilter[]).map((filter) => (
            <button
              type="button"
              className={queueFilter === filter ? "filter-active" : "secondary"}
              onClick={() => setQueueFilter(filter)}
              key={filter}
            >
              {filter} ({counts[filter]})
            </button>
          ))}
        </div>

        {visibleOpportunities.length === 0 ? <p>No opportunities match this view.</p> : (
          <div className="queue opportunity-grid">
            {visibleOpportunities.map((opportunity) => (
              <article className="opportunity-card" key={opportunity.posting_id}>
                <div className="opportunity-main">
                  <div className="opportunity-title-row">
                    <div>
                      <h3>{opportunity.title || "Untitled opportunity"}</h3>
                      <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                    </div>
                    <div className={`score score-${opportunity.recommendation}`}>
                      <strong>{opportunity.ranking_score}</strong>
                      <span>{opportunity.recommendation}</span>
                    </div>
                  </div>

                  <p className="confidence">{opportunity.confidence} confidence · {opportunity.engine_version}</p>
                  <AutomatedReview review={opportunity} />

                  <div className="card-links">
                    {opportunity.source_url && <a href={opportunity.source_url} target="_blank" rel="noreferrer">Open source job</a>}
                    <span>Profile {opportunity.profile_version_id}</span>
                  </div>

                  <div className="review-actions" aria-label={`Review ${opportunity.title}`}>
                    {REVIEW_CHOICES.map((choice) => (
                      <button
                        type="button"
                        className={opportunity.review_decision === choice ? "decision-active" : "secondary"}
                        disabled={busy}
                        onClick={() => reviewOpportunity(opportunity.posting_id, opportunity.evaluation_id, choice)}
                        key={choice}
                      >
                        {choice.replaceAll("_", " ")}
                      </button>
                    ))}
                  </div>

                  {opportunity.review_decision === "pursue" && !opportunity.application_id && (
                    <button disabled={busy} type="button" onClick={() => apiAction(
                      `/api/opportunities/${opportunity.posting_id}/applications`, {}
                    )}>Start application</button>
                  )}

                  {opportunity.application_id && !opportunity.outcome_type && (
                    <div className="review-actions application-actions" aria-label={`Update ${opportunity.title}`}>
                      {opportunity.application_status === "preparing" && (
                        <button disabled={busy} type="button" onClick={() => apiAction(
                          `/api/applications/${opportunity.application_id}/transitions`, { status: "submitted" }
                        )}>Mark submitted</button>
                      )}
                      {["submitted", "acknowledged"].includes(opportunity.application_status ?? "") && (
                        <button disabled={busy} type="button" onClick={() => apiAction(
                          `/api/applications/${opportunity.application_id}/transitions`, { status: "recruiter_screen" }
                        )}>Recruiter screen</button>
                      )}
                      <button disabled={busy} type="button" className="secondary" onClick={() => apiAction(
                        `/api/applications/${opportunity.application_id}/outcomes`,
                        { outcome_type: "rejected_by_employer" }
                      )}>Record employer rejection</button>
                    </div>
                  )}
                </div>

                <div className="queue-status">
                  <strong>{opportunity.outcome_type ?? opportunity.application_status ?? opportunity.review_decision ?? "pending review"}</strong>
                  <span>human decision</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
