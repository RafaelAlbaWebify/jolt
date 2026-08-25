import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { createPortal } from "react-dom";

import { ApplicationReadiness } from "./ApplicationReadiness";
import type { ApplicationReadinessData } from "./ApplicationReadiness";
import type { ApplicationStatus } from "./ApplicationWorkflow";
import { AutomatedReview } from "./AutomatedReview";
import { DataTools } from "./DataTools";
import { OpportunityApplicationHandoff } from "./OpportunityApplicationHandoff";
import { ReadinessHistory } from "./ReadinessHistory";

type ReviewChoice = "pursue" | "consider" | "defer" | "reject" | "needs_more_information";
type SortOption = "score_desc" | "score_asc" | "title_asc" | "company_asc";

type OpportunityIndex = {
  posting_id: string;
  evaluation_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  recommendation: "pursue" | "consider" | "reject";
  confidence: string;
  ranking_score: number;
  review_decision: ReviewChoice | null;
  application_id?: string | null;
  application_status?: ApplicationStatus | null;
  outcome_type?: string | null;
};

type OpportunityDetail = OpportunityIndex & {
  proposed_decision: ReviewChoice;
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
};

type IntakeResult = OpportunityIndex & { identity_status: string; reasons: string[] };

type SourceEvidence = {
  identity_status: string;
  evidence_count: number;
  duplicate_evidence_count: number;
  canonical_url: string;
  evidence: Array<{ source_document_id: string; captured_at: string; source_type: string; source_url: string }>;
};

type AppProps = {
  sidebarToolsTarget?: HTMLDivElement | null;
  evaluationRevision?: number;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const PAGE_SIZE = 5;
const REVIEW_CHOICES: ReviewChoice[] = ["pursue", "consider", "defer", "reject", "needs_more_information"];


function externalSourceUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("//")) return `https:${trimmed}`;
  if (trimmed.startsWith("/jobs/") || trimmed.startsWith("jobs/")) {
    return new URL(trimmed, "https://www.linkedin.com/").toString();
  }
  return trimmed;
}

function decisionLabel(value: ReviewChoice | null) {
  return value ? value.replaceAll("_", " ") : "Pending review";
}

function reviewNotice(decision: ReviewChoice, title: string) {
  const name = title || "Opportunity";
  if (decision === "pursue") return `${name} moved out of the review inbox and is available in Application Pipeline.`;
  if (decision === "needs_more_information") return `${name} marked as needing more information and removed from the pending inbox.`;
  if (decision === "defer") return `${name} deferred and removed from the pending inbox.`;
  if (decision === "reject") return `${name} rejected and removed from the pending inbox.`;
  return `${name} reviewed and removed from the pending inbox.`;
}

async function errorFromResponse(response: Response, fallback: string) {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  return new Error(payload?.detail || fallback);
}

function Sources({ postingId }: { postingId: string }) {
  const [data, setData] = useState<SourceEvidence | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    if (data || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/opportunities/${postingId}/identity-evidence`);
      if (!response.ok) throw new Error("Unable to load source evidence.");
      setData((await response.json()) as SourceEvidence);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Source evidence failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <details
      className="inspector-collapsible"
      onToggle={(event) => {
        if (event.currentTarget.open) void load();
      }}
    >
      <summary>Sources and capture history</summary>
      {loading && <p>Loading sources…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {error && <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>Retry sources</button>}
      {data && (
        <div className="source-compact">
          <p>
            <strong>{data.evidence_count}</strong> captures · <strong>{data.duplicate_evidence_count}</strong>{" "}
            repeated observations
          </p>
          {data.canonical_url && (
            <a href={externalSourceUrl(data.canonical_url)} target="_blank" rel="noreferrer">
              Open canonical job
            </a>
          )}
          <ul>
            {data.evidence.map((item) => (
              <li key={item.source_document_id}>
                <span>
                  {new Date(item.captured_at).toLocaleString()} · {item.source_type}
                </span>
                {item.source_url && (
                  <a href={externalSourceUrl(item.source_url)} target="_blank" rel="noreferrer">
                    source
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </details>
  );
}

export function App({
  sidebarToolsTarget = null,
  evaluationRevision = 0,
}: AppProps) {
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [intake, setIntake] = useState<IntakeResult | null>(null);
  const [opportunities, setOpportunities] = useState<OpportunityIndex[]>([]);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [showManualIntake, setShowManualIntake] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOption, setSortOption] = useState<SortOption>("score_desc");
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<OpportunityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [workflowNotice, setWorkflowNotice] = useState("");
  const inspectorCloseRef = useRef<HTMLButtonElement | null>(null);
  const inspectorTriggerRef = useRef<HTMLButtonElement | null>(null);
  const detailRequestRef = useRef<AbortController | null>(null);
  const evaluationRevisionRef = useRef(evaluationRevision);

  const loadOpportunityIndex = useCallback(async () => {
    const response = await fetch(`${API_BASE}/api/opportunity-index`);
    if (!response.ok) throw await errorFromResponse(response, "Unable to load opportunities.");
    setOpportunities((await response.json()) as OpportunityIndex[]);
    setHasLoaded(true);
  }, []);

  const refreshOpportunities = useCallback(async () => {
    setRefreshing(true);
    setError("");
    try {
      await loadOpportunityIndex();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load opportunities.");
    } finally {
      setRefreshing(false);
    }
  }, [loadOpportunityIndex]);

  const loadDetail = useCallback(async (postingId: string) => {
    detailRequestRef.current?.abort();
    const controller = new AbortController();
    detailRequestRef.current = controller;
    setDetailLoading(true);
    setSelectedDetail(null);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/opportunity-detail/${postingId}`, { signal: controller.signal });
      if (!response.ok) throw await errorFromResponse(response, "Unable to load opportunity details.");
      const detail = (await response.json()) as OpportunityDetail;
      if (detailRequestRef.current === controller) setSelectedDetail(detail);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      if (detailRequestRef.current === controller) {
        setError(caught instanceof Error ? caught.message : "Opportunity detail failed.");
      }
    } finally {
      if (detailRequestRef.current === controller) setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!hasLoaded) void refreshOpportunities();
  }, [hasLoaded, refreshOpportunities]);

  useEffect(() => {
    if (evaluationRevisionRef.current === evaluationRevision) {
      return;
    }

    evaluationRevisionRef.current = evaluationRevision;

    void (async () => {
      await refreshOpportunities();

      if (selectedOpportunityId) {
        await loadDetail(selectedOpportunityId);
      }
    })();
  }, [
    evaluationRevision,
    loadDetail,
    refreshOpportunities,
    selectedOpportunityId,
  ]);

  useEffect(() => {
    if (!selectedOpportunityId) {
      detailRequestRef.current?.abort();
      setDetailLoading(false);
      setSelectedDetail(null);
      return;
    }
    void loadDetail(selectedOpportunityId);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => inspectorCloseRef.current?.focus());
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedOpportunityId(null);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      window.requestAnimationFrame(() => inspectorTriggerRef.current?.focus());
    };
  }, [loadDetail, selectedOpportunityId]);

  const visibleOpportunities = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLocaleLowerCase();
    const filtered = opportunities.filter((opportunity) => {
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
  }, [opportunities, searchQuery, sortOption]);

  const pageCount = Math.max(1, Math.ceil(visibleOpportunities.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pagedOpportunities = visibleOpportunities.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  async function refreshSelected() {
    await refreshOpportunities();
    if (selectedOpportunityId) await loadDetail(selectedOpportunityId);
  }

  async function apiAction(url: string, body: object) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}${url}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw await errorFromResponse(response, "The workflow change could not be saved.");
      await refreshSelected();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected workflow error.");
      throw caught;
    } finally {
      setBusy(false);
    }
  }

  async function reviewOpportunity(opportunity: OpportunityIndex, decision: ReviewChoice) {
    setWorkflowNotice("");
    try {
      await apiAction(`/api/opportunities/${opportunity.posting_id}/reviews`, {
        evaluation_id: opportunity.evaluation_id,
        decision,
      });
      setSelectedOpportunityId(null);
      setWorkflowNotice(reviewNotice(decision, opportunity.title));
    } catch {
      // apiAction already surfaces the error.
    }
  }

  async function clearPendingInbox() {
    if (busy || opportunities.length === 0) return;

    const confirmed = window.confirm(
      `Clear ${opportunities.length} pending Review Inbox card${
        opportunities.length === 1 ? "" : "s"
      }? Capture batches containing only pending items will be archived. ` +
        "Reviewed or applied opportunities and all evidence will be preserved.",
    );
    if (!confirmed) return;

    setBusy(true);
    setError("");
    setWorkflowNotice("");

    try {
      const response = await fetch(
        `${API_BASE}/api/review-inbox/clear-pending`,
        { method: "POST" },
      );

      if (!response.ok) {
        throw await errorFromResponse(
          response,
          "The pending Review Inbox could not be cleared.",
        );
      }

      const result = (await response.json()) as {
        cleared_pending_count: number;
        archived_capture_run_count: number;
        protected_pending_count: number;
      };

      setSelectedOpportunityId(null);
      await refreshOpportunities();

      const protectedNotice = result.protected_pending_count
        ? ` ${result.protected_pending_count} protected card${
            result.protected_pending_count === 1 ? " was" : "s were"
          } left unchanged.`
        : "";

      setWorkflowNotice(
        `${result.cleared_pending_count} pending card${
          result.cleared_pending_count === 1 ? "" : "s"
        } cleared from ${result.archived_capture_run_count} capture batch${
          result.archived_capture_run_count === 1 ? "" : "es"
        }.${protectedNotice}`,
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The pending Review Inbox could not be cleared.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setWorkflowNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/intake/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_url: sourceUrl, raw_text: rawText }),
      });
      if (!response.ok) throw await errorFromResponse(response, "The opportunity could not be processed.");
      const loaded = (await response.json()) as IntakeResult;
      setIntake(loaded);
      setRawText("");
      setSourceUrl("");
      setShowManualIntake(false);
      await refreshOpportunities();
      setWorkflowNotice(`${loaded.title || "Opportunity"} added to the review inbox.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected intake error.");
    } finally {
      setBusy(false);
    }
  }

  const manualIntakeForm = (
    <section className="panel manual-intake-panel" aria-labelledby="manual-intake-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Manual intake</p>
          <h2 id="manual-intake-heading">Add job manually</h2>
          <p>Paste a job description when you do not have a capture batch yet.</p>
        </div>
        <button type="button" className="secondary" onClick={() => setShowManualIntake(false)}>
          Close
        </button>
      </div>
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
            rows={8}
            placeholder={"Job title\nCompany\nLocation\nFull description..."}
          />
        </label>
        <button disabled={busy || !rawText.trim()} type="submit">
          {busy ? "Processing…" : "Evaluate and add to inbox"}
        </button>
      </form>
    </section>
  );

  const operationsTools = <DataTools apiBase={API_BASE} />;

  return (
    <main className="opportunity-main">
      {sidebarToolsTarget ? createPortal(operationsTools, sidebarToolsTarget) : operationsTools}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {workflowNotice && (
        <p className="application-move-notice" role="status">
          {workflowNotice}
        </p>
      )}
      {intake && (
        <section className="panel result">
          <div>
            <p className="eyebrow">{intake.identity_status.replaceAll("_", " ")}</p>
            <h2>{intake.title}</h2>
            <p>
              {intake.company} · {intake.location}
            </p>
          </div>
        </section>
      )}
      {showManualIntake && manualIntakeForm}
      <section className="panel opportunity-workspace" aria-labelledby="queue-heading">
        <div className="section-heading opportunity-toolbar">
          <div>
            <p className="eyebrow">Pending review inbox</p>
            <h2 id="queue-heading">Review Inbox</h2>
            <p>Review newly captured or manually added jobs. A decision removes the item from this inbox.</p>
          </div>
          <div className="professional-source-editor-actions">
            <button type="button" onClick={() => setShowManualIntake(true)} disabled={busy}>
              Add job manually
            </button>
            <button
              type="button"
              className="danger"
              disabled={busy || opportunities.length === 0}
              onClick={() => void clearPendingInbox()}
            >
              Clear pending inbox ({opportunities.length})
            </button>
            <button
              type="button"
              className="secondary"
              disabled={refreshing}
              onClick={() => void refreshOpportunities()}
            >
              {refreshing ? "Refreshing…" : "Refresh list"}
            </button>
          </div>
        </div>
        <div className="queue-summary">
          <strong>{opportunities.length}</strong> pending review items
        </div>
        <div className="opportunity-query-tools">
          <label>
            <span>Search inbox</span>
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
            {hasLoaded
              ? `Showing ${pagedOpportunities.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, visibleOpportunities.length)} of ${visibleOpportunities.length}`
              : "Loading review inbox…"}
          </span>
          <span>{hasLoaded ? `Page ${currentPage} of ${pageCount}` : ""}</span>
        </div>
        {hasLoaded && visibleOpportunities.length === 0 ? (
          <p className="empty-queue">No pending review items match this view.</p>
        ) : (
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
                    <strong>
                      {opportunity.outcome_type ??
                        opportunity.application_status ??
                        decisionLabel(opportunity.review_decision)}
                    </strong>
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
                        if (decision) {
                          void reviewOpportunity(opportunity, decision);
                        }
                      }}
                    >
                      <option value="">Pending review</option>
                      {REVIEW_CHOICES.map((choice) => (
                        <option value={choice} key={choice}>
                          {choice.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="secondary inspect-opportunity"
                    aria-haspopup="dialog"
                    onClick={(event) => {
                      inspectorTriggerRef.current = event.currentTarget;
                      setSelectedOpportunityId(opportunity.posting_id);
                    }}
                  >
                    Inspect
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
        <div className="pagination">
          <button
            type="button"
            className="secondary"
            disabled={currentPage <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {pageCount}
          </span>
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
      {selectedOpportunityId && (
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
                <h2 id="opportunity-inspector-title">{selectedDetail?.title ?? "Loading opportunity…"}</h2>
                <p>{selectedDetail ? [selectedDetail.company, selectedDetail.location].filter(Boolean).join(" · ") : ""}</p>
              </div>
              <button
                ref={inspectorCloseRef}
                type="button"
                className="secondary"
                onClick={() => setSelectedOpportunityId(null)}
              >
                Close
              </button>
            </header>
            {detailLoading && (
              <div className="inspector-loading" role="status">
                Loading full analysis…
              </div>
            )}
            {selectedDetail && (
              <>
                <div className="inspector-sticky-actions">
                  <div className={`score score-${selectedDetail.recommendation}`}>
                    <strong>{selectedDetail.ranking_score}</strong>
                    <span>{selectedDetail.recommendation}</span>
                  </div>
                  <label className="decision-control">
                    <span>Decision</span>
                    <select
                      value={selectedDetail.review_decision ?? ""}
                      disabled={busy}
                      onChange={(event) => {
                        const decision = event.target.value as ReviewChoice;
                        if (decision) {
                          void reviewOpportunity(selectedDetail, decision);
                        }
                      }}
                    >
                      <option value="">Pending review</option>
                      {REVIEW_CHOICES.map((choice) => (
                        <option value={choice} key={choice}>
                          {choice.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedDetail.source_url && (
                    <a className="primary-link" href={externalSourceUrl(selectedDetail.source_url)} target="_blank" rel="noreferrer">
                      Open source job
                    </a>
                  )}
                  <a href={`${API_BASE}/api/opportunities/${selectedDetail.posting_id}/preparation-pack`} download>
                    Download prep pack
                  </a>
                </div>
                <div className="opportunity-detail-grid compact-detail-grid">
                  <AutomatedReview review={selectedDetail} />
                  <ApplicationReadiness readiness={selectedDetail.readiness} />
                  <Sources postingId={selectedDetail.posting_id} />
                  <details className="inspector-collapsible">
                    <summary>Readiness report history</summary>
                    <ReadinessHistory
                      apiBase={API_BASE}
                      postingId={selectedDetail.posting_id}
                      title={selectedDetail.title || "Untitled opportunity"}
                      disabled={busy}
                      onRefreshed={refreshSelected}
                      onError={setError}
                    />
                  </details>
                  <OpportunityApplicationHandoff
                    applicationId={selectedDetail.application_id}
                    applicationStatus={selectedDetail.application_status}
                    outcomeType={selectedDetail.outcome_type}
                    reviewDecision={selectedDetail.review_decision}
                  />
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </main>
  );
}



