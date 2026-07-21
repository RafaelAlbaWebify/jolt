import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApplicationReadiness } from "./ApplicationReadiness";
import type { ApplicationReadinessData } from "./ApplicationReadiness";
import { AutomatedReview } from "./AutomatedReview";
import { CaptureHistory } from "./CaptureHistory";
import { ReadinessHistory } from "./ReadinessHistory";

type ReviewChoice = "pursue" | "consider" | "defer" | "reject" | "needs_more_information";
type ApplicationStatus =
  | "preparing" | "submitted" | "acknowledged" | "recruiter_screen"
  | "technical_interview" | "hiring_manager_interview" | "final_interview"
  | "offer" | "rejected" | "withdrawn" | "no_response" | "closed";
type QueueFilter = "all" | "pending" | "pursue" | "active";
type SortOption = "score_desc" | "score_asc" | "title_asc" | "company_asc";

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
  readiness: ApplicationReadinessData;
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
const PAGE_SIZE = 20;
const REVIEW_CHOICES: ReviewChoice[] = [
  "pursue", "consider", "defer", "reject", "needs_more_information",
];

function decisionLabel(value: ReviewChoice | null) {
  return value ? value.replaceAll("_", " ") : "Pending review";
}

export function App() {
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [intake, setIntake] = useState<IntakeResult | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [queueFilter, setQueueFilter] = useState<QueueFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOption, setSortOption] = useState<SortOption>("score_desc");
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
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
    const normalizedQuery = searchQuery.trim().toLocaleLowerCase();
    const filtered = opportunities.filter((opportunity) => {
      if (queueFilter === "pending" && opportunity.review_decision) return false;
      if (queueFilter === "pursue" && opportunity.review_decision !== "pursue") return false;
      if (queueFilter === "active" && !(opportunity.application_id && !opportunity.outcome_type)) return false;
      if (!normalizedQuery) return true;
      return [opportunity.title, opportunity.company, opportunity.location]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery);
    });

    return [...filtered].sort((left, right) => {
      if (sortOption === "score_asc") return left.ranking_score - right.ranking_score;
      if (sortOption === "title_asc") return left.title.localeCompare(right.title);
      if (sortOption === "company_asc") return left.company.localeCompare(right.company);
      return right.ranking_score - left.ranking_score;
    });
  }, [opportunities, queueFilter, searchQuery, sortOption]);

  const counts = useMemo(() => ({
    all: opportunities.length,
    pending: opportunities.filter((item) => !item.review_decision).length,
    pursue: opportunities.filter((item) => item.review_decision === "pursue").length,
    active: opportunities.filter((item) => item.application_id && !item.outcome_type).length,
  }), [opportunities]);

  const selectedOpportunity = useMemo(
    () => opportunities.find((item) => item.posting_id === selectedOpportunityId) ?? null,
    [opportunities, selectedOpportunityId],
  );

  const pageCount = Math.max(1, Math.ceil(visibleOpportunities.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pagedOpportunities = visibleOpportunities.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

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

  function changeFilter(filter: QueueFilter) {
    setQueueFilter(filter);
    setPage(1);
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Job Opportunity Learning & Tracking</p>
        <h1>JOLT</h1>
        <p>Turn job evidence into an auditable decision, application workflow, and outcome history.</p>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      <details className="panel operations-tools">
        <summary>Intake, captures, and exports</summary>
        <div className="operations-grid">
          <section aria-labelledby="export-heading">
            <h2 id="export-heading">Analysis and feedback</h2>
            <p>Export the complete evidence chain as JSON, CSV, and a readable Markdown summary.</p>
            <a href={`${API_BASE}/api/exports/analysis-pack`} download="JOLT_ANALYSIS_PACK.zip">
              Download analysis pack
            </a>
          </section>

          <section aria-labelledby="intake-heading">
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
                  required rows={8}
                  placeholder={"Job title\nCompany\nLocation: Remote Spain\nFull description..."}
                />
              </label>
              <button disabled={busy || !rawText.trim()} type="submit">
                {busy ? "Processing…" : "Evaluate opportunity"}
              </button>
            </form>
          </section>
        </div>

        <CaptureHistory apiBase={API_BASE} onError={setError} />
      </details>

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

      <section className="panel opportunity-workspace" aria-labelledby="queue-heading">
        <div className="section-heading opportunity-toolbar">
          <div>
            <h2 id="queue-heading">Opportunity review workbench</h2>
            <p>Review the highest-value opportunities first. Inspect one opportunity without expanding the queue.</p>
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
              onClick={() => changeFilter(filter)}
              key={filter}
            >
              {filter} ({counts[filter]})
            </button>
          ))}
        </div>

        <div className="opportunity-query-tools">
          <label>
            <span>Search opportunities</span>
            <input
              type="search"
              value={searchQuery}
              placeholder="Title, company, or location"
              onChange={(event) => {
                setSearchQuery(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label>
            <span>Sort</span>
            <select
              value={sortOption}
              onChange={(event) => {
                setSortOption(event.target.value as SortOption);
                setPage(1);
              }}
            >
              <option value="score_desc">Highest score</option>
              <option value="score_asc">Lowest score</option>
              <option value="title_asc">Title A–Z</option>
              <option value="company_asc">Company A–Z</option>
            </select>
          </label>
        </div>

        <div className="queue-summary">
          <span>
            Showing {pagedOpportunities.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1}
            {"–"}{Math.min(currentPage * PAGE_SIZE, visibleOpportunities.length)} of {visibleOpportunities.length}
          </span>
          <span>Page {currentPage} of {pageCount}</span>
        </div>

        {visibleOpportunities.length === 0 ? <p className="empty-queue">No opportunities match this view.</p> : (
          <div className="opportunity-list">
            {pagedOpportunities.map((opportunity) => (
              <article className="opportunity-row" key={opportunity.posting_id}>
                <div className="opportunity-row-primary">
                  <div className="opportunity-row-title">
                    <h3>{opportunity.title || "Untitled opportunity"}</h3>
                    <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                  </div>

                  <div className={`score score-${opportunity.recommendation}`}>
                    <strong>{opportunity.ranking_score}</strong>
                    <span>{opportunity.recommendation}</span>
                  </div>

                  <div className="opportunity-state">
                    <strong>{opportunity.outcome_type ?? opportunity.application_status ?? decisionLabel(opportunity.review_decision)}</strong>
                    <span>{opportunity.confidence} confidence</span>
                  </div>

                  <label className="decision-control">
                    <span>Decision</span>
                    <select
                      aria-label={`Decision for ${opportunity.title}`}
                      value={opportunity.review_decision ?? ""}
                      disabled={busy}
                      onChange={(event) => {
                        const decision = event.target.value as ReviewChoice;
                        if (decision) void reviewOpportunity(opportunity.posting_id, opportunity.evaluation_id, decision);
                      }}
                    >
                      <option value="">Pending review</option>
                      {REVIEW_CHOICES.map((choice) => (
                        <option value={choice} key={choice}>{choice.replaceAll("_", " ")}</option>
                      ))}
                    </select>
                  </label>

                  <button
                    type="button"
                    className="secondary inspect-opportunity"
                    aria-haspopup="dialog"
                    onClick={() => setSelectedOpportunityId(opportunity.posting_id)}
                  >
                    Inspect
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}

        <div className="pagination" aria-label="Opportunity pages">
          <button
            type="button"
            className="secondary"
            disabled={currentPage <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            Previous
          </button>
          <span>Page {currentPage} of {pageCount}</span>
          <button
            type="button"
            className="secondary"
            disabled={currentPage >= pageCount}
            onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
          >
            Next
          </button>
        </div>
      </section>

      {selectedOpportunity && (
        <div className="inspector-backdrop" role="presentation" onMouseDown={() => setSelectedOpportunityId(null)}>
          <aside
            className="opportunity-inspector"
            role="dialog"
            aria-modal="true"
            aria-labelledby="opportunity-inspector-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="inspector-header">
              <div>
                <p className="eyebrow">Opportunity inspector</p>
                <h2 id="opportunity-inspector-title">{selectedOpportunity.title || "Untitled opportunity"}</h2>
                <p>{[selectedOpportunity.company, selectedOpportunity.location].filter(Boolean).join(" · ")}</p>
              </div>
              <button type="button" className="secondary" onClick={() => setSelectedOpportunityId(null)}>
                Close
              </button>
            </header>

            <div className="inspector-summary">
              <div className={`score score-${selectedOpportunity.recommendation}`}>
                <strong>{selectedOpportunity.ranking_score}</strong>
                <span>{selectedOpportunity.recommendation}</span>
              </div>
              <div>
                <strong>{selectedOpportunity.outcome_type ?? selectedOpportunity.application_status ?? decisionLabel(selectedOpportunity.review_decision)}</strong>
                <span>{selectedOpportunity.confidence} confidence</span>
              </div>
            </div>

            <div className="opportunity-detail-grid">
              <AutomatedReview review={selectedOpportunity} />
              <ApplicationReadiness readiness={selectedOpportunity.readiness} />
              <ReadinessHistory
                apiBase={API_BASE}
                postingId={selectedOpportunity.posting_id}
                title={selectedOpportunity.title || "Untitled opportunity"}
                disabled={busy}
                onRefreshed={refreshOpportunities}
                onError={setError}
              />

              <div className="card-links">
                {selectedOpportunity.source_url && <a href={selectedOpportunity.source_url} target="_blank" rel="noreferrer">Open source job</a>}
                <a
                  href={`${API_BASE}/api/opportunities/${selectedOpportunity.posting_id}/preparation-pack`}
                  download={`JOLT_PREPARATION_${selectedOpportunity.posting_id}.zip`}
                >
                  Download preparation pack
                </a>
                <span>Profile {selectedOpportunity.profile_version_id}</span>
              </div>

              {selectedOpportunity.review_decision === "pursue" && !selectedOpportunity.application_id && (
                <button disabled={busy} type="button" onClick={() => apiAction(
                  `/api/opportunities/${selectedOpportunity.posting_id}/applications`, {}
                )}>Start application</button>
              )}

              {selectedOpportunity.application_id && !selectedOpportunity.outcome_type && (
                <div className="review-actions application-actions" aria-label={`Update ${selectedOpportunity.title}`}>
                  {selectedOpportunity.application_status === "preparing" && (
                    <button disabled={busy} type="button" onClick={() => apiAction(
                      `/api/applications/${selectedOpportunity.application_id}/transitions`, { status: "submitted" }
                    )}>Mark submitted</button>
                  )}
                  {["submitted", "acknowledged"].includes(selectedOpportunity.application_status ?? "") && (
                    <button disabled={busy} type="button" onClick={() => apiAction(
                      `/api/applications/${selectedOpportunity.application_id}/transitions`, { status: "recruiter_screen" }
                    )}>Recruiter screen</button>
                  )}
                  <button disabled={busy} type="button" className="secondary" onClick={() => apiAction(
                    `/api/applications/${selectedOpportunity.application_id}/outcomes`,
                    { outcome_type: "rejected_by_employer" }
                  )}>Record employer rejection</button>
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}
