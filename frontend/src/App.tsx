import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const PAGE_SIZE = 20;
const REVIEW_CHOICES: ReviewChoice[] = ["pursue", "consider", "defer", "reject", "needs_more_information"];

function decisionLabel(value: ReviewChoice | null) {
  return value ? value.replaceAll("_", " ") : "Pending review";
}

function Sources({ postingId }: { postingId: string }) {
  const [data, setData] = useState<SourceEvidence | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (data || loading) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/opportunities/${postingId}/identity-evidence`);
      if (response.ok) setData((await response.json()) as SourceEvidence);
    } finally {
      setLoading(false);
    }
  }

  return (
    <details className="inspector-collapsible" onToggle={(event) => {
      if (event.currentTarget.open) void load();
    }}>
      <summary>Sources and capture history</summary>
      {loading && <p>Loading sources…</p>}
      {data && (
        <div className="source-compact">
          <p><strong>{data.evidence_count}</strong> captures · <strong>{data.duplicate_evidence_count}</strong> repeated observations</p>
          {data.canonical_url && <a href={data.canonical_url} target="_blank" rel="noreferrer">Open canonical job</a>}
          <ul>
            {data.evidence.map((item) => (
              <li key={item.source_document_id}>
                <span>{new Date(item.captured_at).toLocaleString()} · {item.source_type}</span>
                {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">source</a>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </details>
  );
}

export function App() {
  const [sourceUrl, setSourceUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [intake, setIntake] = useState<IntakeResult | null>(null);
  const [opportunities, setOpportunities] = useState<OpportunityIndex[]>([]);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [queueFilter, setQueueFilter] = useState<QueueFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOption, setSortOption] = useState<SortOption>("score_desc");
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<OpportunityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inspectorCloseRef = useRef<HTMLButtonElement | null>(null);
  const inspectorTriggerRef = useRef<HTMLButtonElement | null>(null);

  const refreshOpportunities = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await fetch(`${API_BASE}/api/opportunity-index`);
      if (!response.ok) throw new Error("Unable to load opportunities.");
      setOpportunities((await response.json()) as OpportunityIndex[]);
      setHasLoaded(true);
    } finally {
      setRefreshing(false);
    }
  }, []);

  const loadDetail = useCallback(async (postingId: string) => {
    setDetailLoading(true);
    setSelectedDetail(null);
    try {
      const response = await fetch(`${API_BASE}/api/opportunity-detail/${postingId}`);
      if (!response.ok) throw new Error("Unable to load opportunity details.");
      setSelectedDetail((await response.json()) as OpportunityDetail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Opportunity detail failed.");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!hasLoaded) refreshOpportunities().catch(() => setError("The JOLT API is not available."));
  }, [hasLoaded, refreshOpportunities]);

  useEffect(() => {
    if (!selectedOpportunityId) return;
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
      if (queueFilter === "pending" && opportunity.review_decision) return false;
      if (queueFilter === "pursue" && opportunity.review_decision !== "pursue") return false;
      if (queueFilter === "active" && !(opportunity.application_id && !opportunity.outcome_type)) return false;
      if (!normalizedQuery) return true;
      return [opportunity.title, opportunity.company, opportunity.location].join(" ").toLocaleLowerCase().includes(normalizedQuery);
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
      if (!response.ok) throw new Error("The workflow change could not be saved.");
      await refreshSelected();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected workflow error.");
    } finally {
      setBusy(false);
    }
  }

  async function reviewOpportunity(postingId: string, evaluationId: string, decision: ReviewChoice) {
    await apiAction(`/api/opportunities/${postingId}/reviews`, { evaluation_id: evaluationId, decision });
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

  function changeFilter(filter: QueueFilter) {
    setQueueFilter(filter);
    setPage(1);
  }

  return (
    <main className="opportunity-main">
      {error && <p className="error" role="alert">{error}</p>}

      <details className="panel operations-tools">
        <summary>Intake, captures, and exports</summary>
        <div className="operations-grid">
          <section aria-labelledby="export-heading">
            <h2 id="export-heading">Analysis and feedback</h2>
            <p>Export the complete evidence chain as JSON, CSV, and Markdown.</p>
            <a href={`${API_BASE}/api/exports/analysis-pack`} download="JOLT_ANALYSIS_PACK.zip">Download analysis pack</a>
          </section>
          <section aria-labelledby="intake-heading">
            <h2 id="intake-heading">Manual opportunity intake</h2>
            <form onSubmit={submitIntake}>
              <label>Source URL <span>(optional)</span><input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} type="url" /></label>
              <label>Job text<textarea value={rawText} onChange={(event) => setRawText(event.target.value)} required rows={5} placeholder={"Job title\nCompany\nLocation\nFull description..."} /></label>
              <button disabled={busy || !rawText.trim()} type="submit">{busy ? "Processing…" : "Evaluate opportunity"}</button>
            </form>
          </section>
        </div>
        <CaptureHistory apiBase={API_BASE} onError={setError} />
      </details>

      {intake && <section className="panel result"><div><p className="eyebrow">{intake.identity_status.replaceAll("_", " ")}</p><h2>{intake.title}</h2><p>{intake.company} · {intake.location}</p></div></section>}

      <section className="panel opportunity-workspace" aria-labelledby="queue-heading">
        <div className="section-heading opportunity-toolbar">
          <div><h2 id="queue-heading">Opportunity review workbench</h2><p>Review the highest-value opportunities first.</p></div>
          <button type="button" className="secondary" disabled={refreshing} onClick={() => void refreshOpportunities()}>{refreshing ? "Refreshing…" : "Refresh queue"}</button>
        </div>

        <div className="queue-filters" aria-label="Filter opportunities">
          {(["all", "pending", "pursue", "active"] as QueueFilter[]).map((filter) => <button type="button" className={queueFilter === filter ? "filter-active" : "secondary"} onClick={() => changeFilter(filter)} key={filter}>{filter} ({counts[filter]})</button>)}
        </div>

        <div className="opportunity-query-tools">
          <label><span>Search opportunities</span><input type="search" value={searchQuery} placeholder="Title, company, or location" onChange={(event) => { setSearchQuery(event.target.value); setPage(1); }} /></label>
          <label><span>Sort</span><select value={sortOption} onChange={(event) => { setSortOption(event.target.value as SortOption); setPage(1); }}><option value="score_desc">Highest score</option><option value="score_asc">Lowest score</option><option value="title_asc">Title A–Z</option><option value="company_asc">Company A–Z</option></select></label>
        </div>

        <div className="queue-summary"><span>{hasLoaded ? `Showing ${pagedOpportunities.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, visibleOpportunities.length)} of ${visibleOpportunities.length}` : "Loading opportunities…"}</span><span>{hasLoaded ? `Page ${currentPage} of ${pageCount}` : ""}</span></div>

        {hasLoaded && visibleOpportunities.length === 0 ? <p className="empty-queue">No opportunities match this view.</p> : (
          <div className="opportunity-list">
            {pagedOpportunities.map((opportunity) => (
              <article className="opportunity-row" key={opportunity.posting_id}><div className="opportunity-row-primary">
                <div className="opportunity-row-title"><h3>{opportunity.title || "Untitled opportunity"}</h3><p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p></div>
                <div className={`score score-${opportunity.recommendation}`}><strong>{opportunity.ranking_score}</strong><span>{opportunity.recommendation}</span></div>
                <div className="opportunity-state"><strong>{opportunity.outcome_type ?? opportunity.application_status ?? decisionLabel(opportunity.review_decision)}</strong><span>{opportunity.confidence} confidence</span></div>
                <label className="decision-control"><span>Decision</span><select aria-label={`Decision for ${opportunity.title}`} value={opportunity.review_decision ?? ""} disabled={busy} onChange={(event) => { const decision = event.target.value as ReviewChoice; if (decision) void reviewOpportunity(opportunity.posting_id, opportunity.evaluation_id, decision); }}><option value="">Pending review</option>{REVIEW_CHOICES.map((choice) => <option value={choice} key={choice}>{choice.replaceAll("_", " ")}</option>)}</select></label>
                <button type="button" className="secondary inspect-opportunity" aria-haspopup="dialog" onClick={(event) => { inspectorTriggerRef.current = event.currentTarget; setSelectedOpportunityId(opportunity.posting_id); }}>Inspect</button>
              </div></article>
            ))}
          </div>
        )}

        <div className="pagination"><button type="button" className="secondary" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button><span>Page {currentPage} of {pageCount}</span><button type="button" className="secondary" disabled={currentPage >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next</button></div>
      </section>

      {selectedOpportunityId && (
        <div className="inspector-backdrop" role="presentation" onMouseDown={() => setSelectedOpportunityId(null)}>
          <aside className="opportunity-inspector" role="dialog" aria-modal="true" aria-labelledby="opportunity-inspector-title" onMouseDown={(event) => event.stopPropagation()}>
            <header className="inspector-header">
              <div><p className="eyebrow">Opportunity inspector</p><h2 id="opportunity-inspector-title">{selectedDetail?.title ?? "Loading opportunity…"}</h2><p>{selectedDetail ? [selectedDetail.company, selectedDetail.location].filter(Boolean).join(" · ") : ""}</p></div>
              <button ref={inspectorCloseRef} type="button" className="secondary" onClick={() => setSelectedOpportunityId(null)}>Close</button>
            </header>

            {detailLoading && <div className="inspector-loading" role="status">Loading full analysis…</div>}
            {selectedDetail && (
              <>
                <div className="inspector-sticky-actions">
                  <div className={`score score-${selectedDetail.recommendation}`}><strong>{selectedDetail.ranking_score}</strong><span>{selectedDetail.recommendation}</span></div>
                  <label className="decision-control"><span>Decision</span><select value={selectedDetail.review_decision ?? ""} disabled={busy} onChange={(event) => { const decision = event.target.value as ReviewChoice; if (decision) void reviewOpportunity(selectedDetail.posting_id, selectedDetail.evaluation_id, decision); }}><option value="">Pending review</option>{REVIEW_CHOICES.map((choice) => <option value={choice} key={choice}>{choice.replaceAll("_", " ")}</option>)}</select></label>
                  {selectedDetail.source_url && <a className="primary-link" href={selectedDetail.source_url} target="_blank" rel="noreferrer">Open source job</a>}
                  <a href={`${API_BASE}/api/opportunities/${selectedDetail.posting_id}/preparation-pack`} download>Preparation pack</a>
                </div>

                <div className="opportunity-detail-grid compact-detail-grid">
                  <AutomatedReview review={selectedDetail} />
                  <ApplicationReadiness readiness={selectedDetail.readiness} />
                  <Sources postingId={selectedDetail.posting_id} />
                  <details className="inspector-collapsible"><summary>Readiness report history</summary><ReadinessHistory apiBase={API_BASE} postingId={selectedDetail.posting_id} title={selectedDetail.title || "Untitled opportunity"} disabled={busy} onRefreshed={refreshSelected} onError={setError} /></details>

                  {selectedDetail.review_decision === "pursue" && !selectedDetail.application_id && <button disabled={busy} type="button" onClick={() => apiAction(`/api/opportunities/${selectedDetail.posting_id}/applications`, {})}>Start application</button>}
                  {selectedDetail.application_id && !selectedDetail.outcome_type && <div className="review-actions application-actions">{selectedDetail.application_status === "preparing" && <button disabled={busy} type="button" onClick={() => apiAction(`/api/applications/${selectedDetail.application_id}/transitions`, { status: "submitted" })}>Mark submitted</button>}<button disabled={busy} type="button" className="secondary" onClick={() => apiAction(`/api/applications/${selectedDetail.application_id}/outcomes`, { outcome_type: "rejected_by_employer" })}>Record employer rejection</button></div>}
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </main>
  );
}
