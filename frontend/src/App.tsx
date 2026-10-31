import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApplicationStatus } from "./ApplicationWorkflow";

type ReviewChoice = "pursue" | "consider" | "defer" | "reject" | "needs_more_information";
type AIReviewDecision = "strong_pursue" | "pursue" | "conditional" | "reject";
type AIReviewStatus = "reviewed" | "awaiting_ai_review";
type SortOption = "ai_priority" | "title_asc" | "company_asc";
type InboxFilter = "all" | "priority" | "pursue" | "hold" | "not_fit";
type PreviewTab = "overview" | "fit" | "details";

type OpportunityIndex = {
  posting_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;

  ai_review_id: string | null;
  ai_review_status: AIReviewStatus;

  decision: AIReviewDecision | null;
  priority_score: number | null;

  hardline_status: "PASS" | "REJECT" | "MANUAL_REVIEW" | null;
  hardline_reasons: string[];
  location_eligibility: string | null;
  location_evidence: string[];
  mandatory_requirements: Array<Record<string, unknown>>;
  mandatory_requirement_results: Array<Record<string, unknown>>;
  employment_constraints: string[];
  fit_analysis_allowed: boolean | null;
  decision_reason: string;

  geography_status: string | null;
  clearance_status: string | null;
  language_status: string | null;
  technical_fit: number | null;

  duplicate_of_posting_id: string | null;

  summary: string;
  reasons: string[];

  review_decision: ReviewChoice | null;
  application_id?: string | null;
  application_status?: ApplicationStatus | null;

  reviewed_at: string | null;
  imported_at: string | null;
};

type PortalSourceHistory = {
  sources: Array<{ portal: string; source_job_id: string; source_url: string; first_seen_at: string; last_seen_at: string }>;
  total_observations: number;
  confirmed_duplicates: Array<{ posting_id: string; confirmed_at: string }>;
};

type IntakeResult = {
  posting_id: string;
  identity_status: string;
  title: string;
  company: string;
  location: string;
};

type SourceEvidence = {
  identity_status: string;
  evidence_count: number;
  duplicate_evidence_count: number;
  canonical_url: string;
  evidence: Array<{ source_document_id: string; captured_at: string; source_type: string; source_url: string }>;
};

type AppProps = {
  evaluationRevision?: number;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const PAGE_SIZE = 5;

const REVIEW_LABELS: Record<ReviewChoice, string> = {
  pursue: "Apply",
  consider: "Maybe",
  defer: "Save for later",
  reject: "Reject",
  needs_more_information: "Need information",
};

const AI_DECISION_LABELS: Record<AIReviewDecision, string> = {
  strong_pursue: "High priority",
  pursue: "Good match",
  conditional: "Check requirements",
  reject: "Not a match",
};


function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("The AI review file could not be read."));
    };
    reader.onerror = () => reject(new Error("The AI review file could not be read."));
    reader.readAsText(file);
  });
}

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
  return value ? REVIEW_LABELS[value] : "Pending review";
}

function aiDecisionLabel(opportunity: OpportunityIndex) {
  if (opportunity.ai_review_status !== "reviewed") {
    return "Needs AI review";
  }

  if (!opportunity.decision) {
    return "Review unavailable";
  }

  return AI_DECISION_LABELS[opportunity.decision];
}

function hardlineStopped(opportunity: OpportunityIndex) {
  return (
    opportunity.hardline_status === "REJECT" ||
    opportunity.hardline_status === "MANUAL_REVIEW" ||
    opportunity.fit_analysis_allowed === false
  );
}

function hardlineLabel(opportunity: OpportunityIndex) {
  if (opportunity.hardline_status === "REJECT") return "Required condition not met";
  if (opportunity.hardline_status === "MANUAL_REVIEW") return "Needs manual check";
  return "";
}

function hardlineIcon(opportunity: OpportunityIndex) {
  return opportunity.hardline_status === "REJECT" ? "🔴" : "🟠";
}

function hardlineReason(opportunity: OpportunityIndex) {
  return opportunity.hardline_reasons[0] || opportunity.decision_reason || "A required condition needs review.";
}

function aiPriorityGroup(opportunity: OpportunityIndex) {
  if (opportunity.ai_review_status !== "reviewed") return 3;

  if (opportunity.decision === "strong_pursue") return 0;
  if (opportunity.decision === "pursue") return 1;
  if (opportunity.decision === "conditional") return 2;
  if (opportunity.decision === "reject") return 4;

  return 3;
}

function compareAIPriority(
  left: OpportunityIndex,
  right: OpportunityIndex,
) {
  const groupDifference =
    aiPriorityGroup(left) - aiPriorityGroup(right);

  if (groupDifference !== 0) {
    return groupDifference;
  }

  const leftScore = left.priority_score ?? -1;
  const rightScore = right.priority_score ?? -1;

  if (leftScore !== rightScore) {
    return rightScore - leftScore;
  }

  return left.title.localeCompare(right.title);
}

function companyInitials(company: string) {
  const words = company.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

function inboxFilterMatches(opportunity: OpportunityIndex, filter: InboxFilter) {
  if (filter === "all") return true;
  if (filter === "priority") return opportunity.decision === "strong_pursue";
  if (filter === "pursue") return opportunity.decision === "pursue";
  if (filter === "hold") return opportunity.decision === "conditional";
  return opportunity.decision === "reject";
}

function reviewNotice(decision: ReviewChoice, title: string) {
  const name = title || "Opportunity";
  if (decision === "pursue") return `${name} is ready in Applications.`;
  if (decision === "reject") return `${name} rejected.`;
  return `${name} review updated.`;
}

function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail.trim() || null;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return null;

        const entry = item as Record<string, unknown>;
        const message =
          typeof entry.msg === "string"
            ? entry.msg
            : typeof entry.message === "string"
              ? entry.message
              : "";
        const location = Array.isArray(entry.loc)
          ? entry.loc.map(String).join(".")
          : "";

        if (message && location) return `${location}: ${message}`;
        if (message) return message;
        return JSON.stringify(entry);
      })
      .filter((message): message is string => Boolean(message));
    return messages.length ? messages.join("; ") : null;
  }

  if (detail && typeof detail === "object") {
    const entry = detail as Record<string, unknown>;
    if (typeof entry.msg === "string") return entry.msg;
    if (typeof entry.message === "string") return entry.message;
    return JSON.stringify(entry);
  }

  return null;
}

async function errorFromResponse(response: Response, fallback: string) {
  const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  return new Error(formatErrorDetail(payload?.detail) || fallback);
}

function SourceDescription({ postingId }: { postingId: string }) {
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetch(`${API_BASE}/api/opportunities/${postingId}/source-description`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load the captured job description.");
        return (await response.json()) as { description: string; location: string };
      })
      .then((data) => {
        if (!cancelled) {
          setDescription(data.description);
          setLocation(data.location);
        }
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Unable to load description.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [postingId]);

  return (
    <section className="inspector-source-description" aria-label="Captured job description">
      <h3>Original job description</h3>
      {loading && <p role="status">Loading captured description…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && (
        <>
          {location && <p><strong>Captured location:</strong> {location}</p>}
          {description ? <div className="inspector-source-text">{description}</div> : <p>No source description is available for this opportunity.</p>}
          <small>Source text is not an AI assessment. Verify geography, work authorization, and mandatory requirements before deciding.</small>
        </>
      )}
    </section>
  );
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
      <summary>Sources and history</summary>
      {loading && <p>Loading sources…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {error && <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>Retry sources</button>}
      {data && (
        <div className="source-compact">
          <p>
            <strong>{data.evidence_count}</strong> observations · <strong>{data.duplicate_evidence_count}</strong>{" "}
            repeated
          </p>
          {data.canonical_url && (
            <a href={externalSourceUrl(data.canonical_url)} target="_blank" rel="noreferrer">
              Open job
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
  const [sortOption, setSortOption] = useState<SortOption>("ai_priority");
  const [inboxFilter, setInboxFilter] = useState<InboxFilter>("all");
  const [previewOpportunityId, setPreviewOpportunityId] = useState<string | null>(null);
  const [previewTab, setPreviewTab] = useState<PreviewTab>("overview");
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);
  const [portalHistory, setPortalHistory] = useState<PortalSourceHistory | null>(null);
  const [portalHistoryError, setPortalHistoryError] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [workflowNotice, setWorkflowNotice] = useState("");
  const [capturingOfficialSources, setCapturingOfficialSources] = useState(false);
  const [officialSourceReport, setOfficialSourceReport] = useState<{
    candidate_links: number;
    attempted: number;
    cached_fresh: number;
    remaining_or_skipped: number;
    provider_searches?: number;
    provider_statuses?: Record<string, number>;
    results: Array<{
      posting_id?: string;
      url?: string;
      status: string;
      detail?: string;
      http_status?: string;
      captured_at?: string;
    }>;
  } | null>(null);
  const inspectorCloseRef = useRef<HTMLButtonElement | null>(null);
  const inspectorTriggerRef = useRef<HTMLButtonElement | null>(null);
  const aiReviewImportRef = useRef<HTMLInputElement | null>(null);
  const evaluationRevisionRef = useRef(evaluationRevision);

  const loadOpportunityIndex = useCallback(async () => {
    const response = await fetch(`${API_BASE}/api/ai-review/opportunity-index`);
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

  useEffect(() => {
    if (!hasLoaded) void refreshOpportunities();
  }, [hasLoaded, refreshOpportunities]);

  useEffect(() => {
    if (evaluationRevisionRef.current === evaluationRevision) {
      return;
    }

    evaluationRevisionRef.current = evaluationRevision;
    void refreshOpportunities();
  }, [
    evaluationRevision,
    refreshOpportunities,
  ]);

  useEffect(() => {
    if (!selectedOpportunityId) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const trigger = inspectorTriggerRef.current;
    const timer = window.setTimeout(() => inspectorCloseRef.current?.focus(), 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelectedOpportunityId(null);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      trigger?.focus();
    };
  }, [selectedOpportunityId]);


  useEffect(() => {
    setPortalHistory(null);
    setPortalHistoryError("");
    if (!selectedOpportunityId) return;
    const controller = new AbortController();
    void fetch(`${API_BASE}/api/discovery-postings/${encodeURIComponent(selectedOpportunityId)}/source-history`, {
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) throw new Error("Source history is currently unavailable.");
      setPortalHistory((await response.json()) as PortalSourceHistory);
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) {
        setPortalHistoryError(caught instanceof Error ? caught.message : "Source history is unavailable.");
      }
    });
    return () => controller.abort();
  }, [selectedOpportunityId]);

  const selectedOpportunity = useMemo(
    () =>
      opportunities.find(
        (opportunity) =>
          opportunity.posting_id === selectedOpportunityId,
      ) ?? null,
    [opportunities, selectedOpportunityId],
  );

  const previewOpportunity = useMemo(
    () =>
      opportunities.find(
        (opportunity) => opportunity.posting_id === previewOpportunityId,
      ) ?? null,
    [opportunities, previewOpportunityId],
  );

  const inboxCounts = useMemo(() => ({
    all: opportunities.length,
    priority: opportunities.filter((item) => inboxFilterMatches(item, "priority")).length,
    pursue: opportunities.filter((item) => inboxFilterMatches(item, "pursue")).length,
    hold: opportunities.filter((item) => inboxFilterMatches(item, "hold")).length,
    not_fit: opportunities.filter((item) => inboxFilterMatches(item, "not_fit")).length,
    reviewed: opportunities.filter((item) => item.ai_review_status === "reviewed").length,
  }), [opportunities]);

  const awaitingAIReviewCount = opportunities.filter(
    (item) => item.ai_review_status === "awaiting_ai_review",
  ).length;

  const visibleOpportunities = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLocaleLowerCase();
    const filtered = opportunities.filter((opportunity) => {
      if (!inboxFilterMatches(opportunity, inboxFilter)) return false;
      if (!normalizedQuery) return true;
      return [opportunity.title, opportunity.company, opportunity.location]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery);
    });
    return [...filtered].sort((left, right) => {
      if (sortOption === "title_asc") {
        return left.title.localeCompare(right.title);
      }

      if (sortOption === "company_asc") {
        return left.company.localeCompare(right.company);
      }

      return compareAIPriority(left, right);
    });
  }, [opportunities, searchQuery, sortOption, inboxFilter]);

  const pageCount = Math.max(1, Math.ceil(visibleOpportunities.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pagedOpportunities = visibleOpportunities.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    if (pagedOpportunities.length === 0) {
      setPreviewOpportunityId(null);
      return;
    }
    if (!previewOpportunityId || !pagedOpportunities.some((item) => item.posting_id === previewOpportunityId)) {
      setPreviewOpportunityId(pagedOpportunities[0].posting_id);
      setPreviewTab("overview");
    }
  }, [pagedOpportunities, previewOpportunityId]);

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
      await refreshOpportunities();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected workflow error.");
      throw caught;
    } finally {
      setBusy(false);
    }
  }

  async function reviewOpportunity(
    opportunity: OpportunityIndex,
    decision: ReviewChoice,
  ) {
    if (!opportunity.ai_review_id) {
      setError(
        "This job is awaiting AI review and cannot be decided yet.",
      );
      return;
    }

    setWorkflowNotice("");

    try {
      await apiAction(
        `/api/opportunities/${opportunity.posting_id}/reviews`,
        {
          ai_review_id: opportunity.ai_review_id,
          decision,
        },
      );

      setSelectedOpportunityId(null);
      setWorkflowNotice(
        reviewNotice(decision, opportunity.title),
      );
    } catch {
      // apiAction already surfaces the error.
    }
  }

  async function importAIReviewFile(file: File) {
    setBusy(true);
    setError("");
    setWorkflowNotice("");

    try {
      const text = await readTextFile(file);
      let payload: unknown;

      try {
        payload = JSON.parse(text);
      } catch {
        throw new Error("The selected file is not valid JSON.");
      }

      const hasReviewInbox =
        payload !== null &&
        typeof payload === "object" &&
        "review_inbox" in payload &&
        (payload as { review_inbox?: unknown }).review_inbox != null;

      if (hasReviewInbox) {
        const preflightResponse = await fetch(
          `${API_BASE}/api/ai-work-package/preflight`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          },
        );

        if (!preflightResponse.ok) {
          throw await errorFromResponse(
            preflightResponse,
            "The AI review package failed pre-import validation.",
          );
        }
      }

      const response = await fetch(`${API_BASE}/api/ai-work-package/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw await errorFromResponse(
          response,
          "The AI review result could not be imported.",
        );
      }

      const result = (await response.json()) as {
        review_inbox_imported?: boolean;
        section_results?: {
          review_inbox?: {
            received_count?: number;
          };
        };
      };

      await refreshOpportunities();

      const importedCount =
        result.section_results?.review_inbox?.received_count ??
        awaitingAIReviewCount;

      setWorkflowNotice(
        result.review_inbox_imported
          ? `AI review imported successfully for ${importedCount} job${
              importedCount === 1 ? "" : "s"
            }.`
          : "AI work package imported successfully.",
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The AI review result could not be imported.",
      );
    } finally {
      if (aiReviewImportRef.current) {
        aiReviewImportRef.current.value = "";
      }
      setBusy(false);
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
        } cleared from ${result.archived_capture_run_count} search run${
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
      setWorkflowNotice(`${loaded.title || "Opportunity"} added and awaiting AI review.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected intake error.");
    } finally {
      setBusy(false);
    }
  }

  async function enrichOfficialSources() {
    setCapturingOfficialSources(true);
    setError("");
    setWorkflowNotice("");
    setOfficialSourceReport(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/ai-work-package/official-evidence/refresh`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw await errorFromResponse(response, "Official source enrichment failed.");
      }
      const result = (await response.json()) as NonNullable<typeof officialSourceReport>;
      const captured = result.results.filter(
        (item) => item.status === "captured_identity_unverified",
      ).length;
      const failedOrBlocked = result.results.filter(
        (item) => item.status !== "captured_identity_unverified" && item.status !== "cached_fresh",
      ).length;
      setOfficialSourceReport(result);
      setWorkflowNotice(
        `Official sources: ${captured} page(s) captured; ${result.attempted} attempted; ` +
        `${result.cached_fresh} fresh cached; ${failedOrBlocked} failed or blocked; ` +
        `${result.remaining_or_skipped} candidate link(s) not attempted. ` +
        "Captured ATS text still requires offer-identity and eligibility review.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Official source enrichment failed.");
    } finally {
      setCapturingOfficialSources(false);
    }
  }

  const manualIntakeForm = (
    <section className="panel manual-intake-panel" aria-labelledby="manual-intake-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Manual intake</p>
          <h2 id="manual-intake-heading">Add job manually</h2>
          <p>Paste a job description when a role was not found through your saved searches.</p>
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
          {busy ? "Processing…" : "Clean and add to inbox"}
        </button>
      </form>
    </section>
  );

  return (
    <main className="opportunity-main">
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
      {officialSourceReport && (
        <section className="panel" aria-labelledby="official-source-report-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Capture diagnostics</p>
              <h2 id="official-source-report-heading">Official source results</h2>
              <p>
                {officialSourceReport.candidate_links} candidate link(s):{" "}
                {officialSourceReport.attempted} attempted, {officialSourceReport.cached_fresh} served from
                fresh cache, and {officialSourceReport.remaining_or_skipped} not attempted.
              </p>
              <p>
                Provider searches: {officialSourceReport.provider_searches ?? 0}.{" "}
                {Object.entries(officialSourceReport.provider_statuses ?? {}).length
                  ? Object.entries(officialSourceReport.provider_statuses ?? {})
                      .map(([status, count]) => `${status}: ${count}`)
                      .join(" · ")
                  : "No provider search status was returned."}
              </p>
            </div>
          </div>
          {officialSourceReport.results.length > 0 ? (
            <details open>
              <summary>Show per-link outcomes ({officialSourceReport.results.length})</summary>
              <ol>
                {officialSourceReport.results.map((item, index) => (
                  <li key={`${item.posting_id ?? "unknown"}-${item.url ?? "no-url"}-${index}`}>
                    <strong>{item.status.replaceAll("_", " ")}</strong>
                    {item.posting_id && <>{" · "}Posting {item.posting_id}</>}
                    {item.http_status && <> · HTTP {item.http_status}</>}
                    {item.detail && <> · {item.detail}</>}
                    {item.captured_at && <> · Cached at {new Date(item.captured_at).toLocaleString()}</>}
                    {item.url && (
                      <>
                        <br />
                        <a href={item.url} target="_blank" rel="noreferrer">{item.url}</a>
                      </>
                    )}
                  </li>
                ))}
              </ol>
            </details>
          ) : (
            <p>No individual link outcomes were returned.</p>
          )}
        </section>
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
      <section className="panel opportunity-workspace review-inbox-redesign" aria-labelledby="queue-heading">
        <div className="section-heading opportunity-toolbar review-inbox-header">
          <div>
            <p className="eyebrow">Pending review inbox</p>
            <h2 id="queue-heading">Review Inbox</h2>
            <p>Review the jobs JOLT has analyzed and decide which ones deserve your time.</p>
          </div>
          <div className="professional-source-editor-actions">
            {awaitingAIReviewCount > 0 && (
              <>
                <a
                  className="primary-link"
                  href={`${API_BASE}/api/ai-work-package/review-export`}
                  download="JOLT_REVIEW_ONLY.json"
                  title="Export pending Review Inbox jobs for classification without unrelated intelligence sections."
                >
                  Export AI review ({awaitingAIReviewCount})
                </a>
                <input
                  ref={aiReviewImportRef}
                  type="file"
                  accept="application/json,.json"
                  hidden
                  aria-label="AI review result file"
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    if (file) void importAIReviewFile(file);
                  }}
                />
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => aiReviewImportRef.current?.click()}
                >
                  {busy ? "Importing…" : "Import AI review result"}
                </button>
              </>
            )}
            <button type="button" onClick={() => setShowManualIntake(true)} disabled={busy}>
              Add job manually
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy || capturingOfficialSources}
              onClick={() => void enrichOfficialSources()}
            >
              {capturingOfficialSources ? "Enriching official sources…" : "Enrich official sources"}
            </button>
            <button type="button" className="secondary" disabled={refreshing} onClick={() => void refreshOpportunities()}>
              {refreshing ? "Refreshing…" : "Refresh list"}
            </button>
          </div>
        </div>

        <div className="review-inbox-summary-bar">
          <div className="review-inbox-stat">
            <span className="review-inbox-stat-icon">▤</span>
            <span><strong>{inboxCounts.all.toLocaleString()}</strong><small>waiting</small></span>
          </div>
          <div className="review-inbox-stat review-inbox-stat-priority">
            <span className="review-inbox-stat-icon">◆</span>
            <span><strong>{inboxCounts.priority.toLocaleString()}</strong><small>high priority</small></span>
          </div>
          <div className="review-inbox-stat review-inbox-stat-reviewed">
            <span className="review-inbox-stat-icon">✓</span>
            <span><strong>{inboxCounts.reviewed.toLocaleString()}</strong><small>AI reviewed</small></span>
          </div>
          <details className="review-inbox-maintenance">
            <summary>Maintenance</summary>
            <div className="review-inbox-maintenance-menu">
              <p>Remove unresolved inbox cards in bulk. Reviewed jobs, applications, and captured evidence are preserved.</p>
              <button type="button" className="danger" disabled={busy || opportunities.length === 0} onClick={() => void clearPendingInbox()}>
                Clear unresolved inbox ({opportunities.length})
              </button>
            </div>
          </details>
        </div>

        <div className="review-inbox-filterbar">
          <label className="review-inbox-search">
            <span>Search inbox</span>
            <input
              type="search"
              value={searchQuery}
              placeholder="Search jobs by title, company, or location…"
              onChange={(event) => {
                setSearchQuery(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <div className="review-inbox-filterchips" role="group" aria-label="Review Inbox filters">
            {([
              ["all", "All", inboxCounts.all],
              ["priority", "High priority", inboxCounts.priority],
              ["pursue", "Good match", inboxCounts.pursue],
              ["hold", "Check", inboxCounts.hold],
              ["not_fit", "Not a match", inboxCounts.not_fit],
            ] as Array<[InboxFilter, string, number]>).map(([value, labelText, count]) => (
              <button
                type="button"
                key={value}
                className={inboxFilter === value ? "review-inbox-filterchip active" : "review-inbox-filterchip"}
                aria-pressed={inboxFilter === value}
                onClick={() => {
                  setInboxFilter(value);
                  setPage(1);
                }}
              >
                {labelText} <span>{count.toLocaleString()}</span>
              </button>
            ))}
          </div>
          <label className="review-inbox-sort">
            <span>Sort by</span>
            <select
              value={sortOption}
              onChange={(event) => {
                setSortOption(event.target.value as SortOption);
                setPage(1);
              }}
            >
              <option value="ai_priority">Best matches first</option>
              <option value="title_asc">Title A–Z</option>
              <option value="company_asc">Company A–Z</option>
            </select>
          </label>
        </div>

        {hasLoaded && visibleOpportunities.length === 0 ? (
          <p className="empty-queue">No pending review items match this view.</p>
        ) : (
          <div className="review-inbox-split">
            <section className="review-inbox-list-pane" aria-label="Jobs awaiting review">
              <div className="review-inbox-list-header">
                <span>
                  Showing {pagedOpportunities.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, visibleOpportunities.length)} of {visibleOpportunities.length}
                </span>
                <span>Page {currentPage} of {pageCount}</span>
              </div>
              <div className="review-inbox-card-list">
                {pagedOpportunities.map((opportunity) => {
                  const active = previewOpportunity?.posting_id === opportunity.posting_id;
                  return (
                    <article className={active ? "review-inbox-card active" : "review-inbox-card"} key={opportunity.posting_id}>
                      <button
                        type="button"
                        className="review-inbox-card-main"
                        aria-pressed={active}
                        onClick={() => {
                          setPreviewOpportunityId(opportunity.posting_id);
                          setPreviewTab("overview");
                        }}
                      >
                        <span className="review-company-mark" aria-hidden="true">{companyInitials(opportunity.company || "Unknown company")}</span>
                        <span className="review-inbox-card-copy">
                          <h3>{opportunity.title || "Untitled opportunity"}</h3>
                          <span>{opportunity.company || "Unknown company"}</span>
                          <small>{[opportunity.location, opportunity.imported_at ? new Date(opportunity.imported_at).toLocaleDateString() : ""].filter(Boolean).join(" · ")}</small>
                        </span>
                      </button>
                      <div className="review-inbox-card-score">
                        <strong>{hardlineStopped(opportunity) ? hardlineIcon(opportunity) : opportunity.priority_score ?? "—"}</strong>
                        <span>{opportunity.ai_review_status === "reviewed" ? aiDecisionLabel(opportunity) : "Pending"}</span>
                      </div>
                      <div className="review-inbox-card-ai">
                        <strong>{opportunity.ai_review_status === "reviewed" ? "AI reviewed" : "Needs AI review"}</strong>
                        <span>{hardlineStopped(opportunity) ? hardlineLabel(opportunity) : `Technical fit ${opportunity.technical_fit ?? "—"}`}</span>
                      </div>
                      <div className="review-inbox-card-actions" aria-label={`Actions for ${opportunity.title}`}>
                        <button
                          type="button"
                          className="review-inbox-apply"
                          disabled={busy || !opportunity.ai_review_id}
                          onClick={() => void reviewOpportunity(opportunity, "pursue")}
                        >
                          Apply
                        </button>
                        <button
                          type="button"
                          className="review-inbox-reject"
                          disabled={busy || !opportunity.ai_review_id}
                          onClick={() => void reviewOpportunity(opportunity, "reject")}
                        >
                          Reject
                        </button>
                      </div>
                      <button
                        type="button"
                        className="review-inbox-card-open"
                        aria-label="Inspect"
                        title="Inspect full details"
                        onClick={(event) => {
                          inspectorTriggerRef.current = event.currentTarget;
                          setSelectedOpportunityId(opportunity.posting_id);
                        }}
                      >
                        ›
                      </button>
                    </article>
                  );
                })}
              </div>
              <div className="review-inbox-list-pagination">
                <button type="button" className="secondary" aria-label="Previous page" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>‹</button>
                <span>Page {currentPage} of {pageCount}</span>
                <button type="button" className="secondary" aria-label="Next page" disabled={currentPage >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>›</button>
              </div>
            </section>

            <section className="review-inbox-preview-pane" aria-label="Selected job preview">
              {previewOpportunity ? (
                <>
                  <header className="review-preview-header">
                    <span className="review-company-mark review-company-mark-large" aria-hidden="true">
                      {companyInitials(previewOpportunity.company || "Unknown company")}
                    </span>
                    <div className="review-preview-title">
                      <h3>{previewOpportunity.title || "Untitled opportunity"}</h3>
                      <p>{previewOpportunity.company || "Unknown company"}</p>
                      <span>{previewOpportunity.location || "Location not recorded"}</span>
                    </div>
                    <div className="review-preview-score">
                      <strong>{hardlineStopped(previewOpportunity) ? hardlineIcon(previewOpportunity) : previewOpportunity.priority_score ?? "—"}</strong>
                      <span>{previewOpportunity.ai_review_status === "reviewed" ? aiDecisionLabel(previewOpportunity) : "Pending"}</span>
                    </div>
                  </header>

                  <div className="review-preview-tabs" role="tablist" aria-label="Preview sections">
                    {([
                      ["overview", "Overview"],
                      ["fit", "Fit analysis"],
                      ["details", "Job details"],
                    ] as Array<[PreviewTab, string]>).map(([value, labelText]) => (
                      <button
                        type="button"
                        role="tab"
                        key={value}
                        aria-selected={previewTab === value}
                        className={previewTab === value ? "active" : ""}
                        onClick={() => setPreviewTab(value)}
                      >
                        {labelText}
                      </button>
                    ))}
                  </div>

                  <div className="review-preview-body">
                    <div className="review-preview-primary">
                      {previewTab === "overview" && (
                        <>
                          <section>
                            <h4>Job summary</h4>
                            <p>{previewOpportunity.summary || previewOpportunity.decision_reason || "No concise job summary is available yet."}</p>
                          </section>

                          <div className="review-preview-evidence-grid">
                            <section className="review-preview-signal-card">
                              <h4>{previewOpportunity.decision === "reject" ? "Why this role was rejected" : previewOpportunity.decision === "conditional" ? "Why it needs review" : "Why it looks promising"}</h4>
                              {previewOpportunity.reasons.length ? (
                                <ul>{previewOpportunity.reasons.slice(0, 4).map((reason) => <li key={reason}>{reason}</li>)}</ul>
                              ) : (
                                <p>No additional positive signals are recorded.</p>
                              )}
                            </section>
                            <section className="review-preview-risk-card">
                              <h4>What to verify</h4>
                              {hardlineStopped(previewOpportunity) && (
                                <p>Fit score not shown because a required condition was not met.</p>
                              )}
                              {[...previewOpportunity.hardline_reasons, ...previewOpportunity.employment_constraints].length ? (
                                <ul>{[...previewOpportunity.hardline_reasons, ...previewOpportunity.employment_constraints].slice(0, 4).map((reason) => <li key={reason}>{reason}</li>)}</ul>
                              ) : (
                                <p>No explicit blockers are recorded.</p>
                              )}
                            </section>
                          </div>

                          <div className="review-preview-meta">
                            <div><span>Geography</span><strong>{previewOpportunity.geography_status ?? "unknown"}</strong></div>
                            <div><span>Clearance</span><strong>{previewOpportunity.clearance_status ?? "unknown"}</strong></div>
                            <div><span>Language</span><strong>{previewOpportunity.language_status ?? "unknown"}</strong></div>
                            {!hardlineStopped(previewOpportunity) && (
                              <div><span>Technical fit</span><strong>{previewOpportunity.technical_fit ?? "—"}</strong></div>
                            )}
                          </div>
                        </>
                      )}

                      {previewTab === "fit" && (
                        <>
                          <section className="review-fit-summary">
                            <h4>Fit assessment</h4>
                            <p>{previewOpportunity.decision_reason || previewOpportunity.summary || "No fit rationale is available yet."}</p>
                          </section>

                          <div className="review-fit-score-grid">
                            <div>
                              <span>Priority score</span>
                              <strong>{hardlineStopped(previewOpportunity) ? "Blocked" : previewOpportunity.priority_score ?? "—"}</strong>
                            </div>
                            <div>
                              <span>Technical fit</span>
                              <strong>{hardlineStopped(previewOpportunity) ? "—" : previewOpportunity.technical_fit ?? "—"}</strong>
                            </div>
                            <div>
                              <span>Geography</span>
                              <strong>{previewOpportunity.geography_status ?? "unknown"}</strong>
                            </div>
                            <div>
                              <span>Language</span>
                              <strong>{previewOpportunity.language_status ?? "unknown"}</strong>
                            </div>
                          </div>

                          <div className="review-preview-evidence-grid">
                            <section className="review-preview-signal-card">
                              <h4>Evidence supporting the match</h4>
                              {previewOpportunity.reasons.length ? (
                                <ul>{previewOpportunity.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                              ) : (
                                <p>No supporting reasons are recorded.</p>
                              )}
                            </section>
                            <section className="review-preview-risk-card">
                              <h4>Constraints and blockers</h4>
                              {[...previewOpportunity.hardline_reasons, ...previewOpportunity.employment_constraints].length ? (
                                <ul>{[...previewOpportunity.hardline_reasons, ...previewOpportunity.employment_constraints].map((reason) => <li key={reason}>{reason}</li>)}</ul>
                              ) : (
                                <p>No explicit constraints are recorded.</p>
                              )}
                            </section>
                          </div>
                        </>
                      )}

                      {previewTab === "details" && (
                        <>
                          <section className="review-job-details-grid">
                            <div><span>Company</span><strong>{previewOpportunity.company || "Unknown company"}</strong></div>
                            <div><span>Location</span><strong>{previewOpportunity.location || "Not recorded"}</strong></div>
                            <div><span>AI review</span><strong>{previewOpportunity.ai_review_status === "reviewed" ? "Reviewed" : "Pending"}</strong></div>
                            <div><span>Human decision</span><strong>{decisionLabel(previewOpportunity.review_decision)}</strong></div>
                            <div><span>Location evidence</span><strong>{previewOpportunity.location_evidence.length}</strong></div>
                            <div><span>Mandatory requirements</span><strong>{previewOpportunity.mandatory_requirements.length}</strong></div>
                            <div><span>Employment constraints</span><strong>{previewOpportunity.employment_constraints.length}</strong></div>
                            <div><span>Duplicate</span><strong>{previewOpportunity.duplicate_of_posting_id ? "Yes" : "No"}</strong></div>
                          </section>

                          {previewOpportunity.location_evidence.length > 0 && (
                            <section className="review-detail-list">
                              <h4>Location evidence</h4>
                              <ul>{previewOpportunity.location_evidence.slice(0, 6).map((item) => <li key={item}>{item}</li>)}</ul>
                            </section>
                          )}

                          <section className="review-detail-timestamps">
                            <div><span>Imported</span><strong>{previewOpportunity.imported_at ? new Date(previewOpportunity.imported_at).toLocaleString() : "Not recorded"}</strong></div>
                            <div><span>Reviewed</span><strong>{previewOpportunity.reviewed_at ? new Date(previewOpportunity.reviewed_at).toLocaleString() : "Not reviewed yet"}</strong></div>
                          </section>
                        </>
                      )}
                    </div>

                    <aside className="review-preview-actions">
                      <h4>Your decision</h4>
                      <p className="review-preview-pending-note">Leave untouched to keep this job pending.</p>
                      <button
                        type="button"
                        className="review-preview-apply"
                        disabled={busy || !previewOpportunity.ai_review_id}
                        onClick={() => void reviewOpportunity(previewOpportunity, "pursue")}
                      >
                        Apply
                      </button>
                      <button
                        type="button"
                        className="review-preview-reject"
                        disabled={busy || !previewOpportunity.ai_review_id}
                        onClick={() => void reviewOpportunity(previewOpportunity, "reject")}
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={(event) => {
                          inspectorTriggerRef.current = event.currentTarget;
                          setSelectedOpportunityId(previewOpportunity.posting_id);
                        }}
                      >
                        Inspect full details
                      </button>
                      {previewOpportunity.source_url && (
                        <a className="review-preview-source-link" href={externalSourceUrl(previewOpportunity.source_url)} target="_blank" rel="noreferrer">
                          Open source job ↗
                        </a>
                      )}
                    </aside>
                  </div>
                </>
              ) : (
                <div className="review-preview-empty">
                  <strong>Select a job to review</strong>
                  <span>Choose an item from the list to see its AI review and evidence.</span>
                </div>
              )}
            </section>
          </div>
        )}
      </section>
      {selectedOpportunityId && selectedOpportunity && (
        <div
          className="inspector-backdrop"
          role="presentation"
          onMouseDown={() => setSelectedOpportunityId(null)}
        >
          <aside
            className="opportunity-inspector"
            role="dialog"
            aria-modal="true"
            aria-labelledby="opportunity-inspector-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="inspector-header">
              <div>
                <p className="eyebrow">AI-reviewed opportunity</p>
                <h2 id="opportunity-inspector-title">
                  {selectedOpportunity.title || "Untitled opportunity"}
                </h2>
                <p>
                  {[selectedOpportunity.company, selectedOpportunity.location]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
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

            <div className="inspector-sticky-actions">
              <div
                className={`score score-${
                  selectedOpportunity.decision ?? "awaiting"
                }`}
              >
                <strong>
                  {hardlineStopped(selectedOpportunity)
                    ? hardlineIcon(selectedOpportunity)
                    : selectedOpportunity.priority_score ?? "—"}
                </strong>
                <span>
                  {hardlineStopped(selectedOpportunity)
                    ? hardlineLabel(selectedOpportunity)
                    : aiDecisionLabel(selectedOpportunity)}
                </span>
              </div>

              <div className="inspector-review-actions" aria-label={`Review actions for ${selectedOpportunity.title}`}>
                <span>Human decision</span>
                <div>
                  <button
                    type="button"
                    disabled={busy || !selectedOpportunity.ai_review_id}
                    onClick={() => void reviewOpportunity(selectedOpportunity, "pursue")}
                  >
                    Apply
                  </button>
                  <button
                    type="button"
                    className="secondary inspector-reject-action"
                    disabled={busy || !selectedOpportunity.ai_review_id}
                    onClick={() => void reviewOpportunity(selectedOpportunity, "reject")}
                  >
                    Reject
                  </button>
                </div>
                <small>
                  {selectedOpportunity.ai_review_id
                    ? "Leave untouched to keep pending."
                    : "AI review required before deciding."}
                </small>
              </div>

              {selectedOpportunity.source_url && (
                <a
                  className="primary-link"
                  href={externalSourceUrl(
                    selectedOpportunity.source_url,
                  )}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open source job
                </a>
              )}
            </div>

            <section aria-label="Verified portal sources" className="automated-review">
              <div className="automated-review-heading"><strong>Verified portal sources</strong></div>
              {portalHistoryError && <p role="status">{portalHistoryError}</p>}
              {!portalHistoryError && !portalHistory && <p>Loading verified source history…</p>}
              {portalHistory && (
                <>
                  <p>{portalHistory.sources.length} verified portal identity records · {portalHistory.total_observations} capture observations</p>
                  {portalHistory.sources.length === 0 && <p>No independently verified portal identity available for this job.</p>}
                  <ul>
                    {portalHistory.sources.map((source) => (
                      <li key={`${source.portal}:${source.source_job_id}`}>
                        <strong>{source.portal}</strong>{" "}
                        <a href={externalSourceUrl(source.source_url)} target="_blank" rel="noreferrer">
                          Source job {source.source_job_id}
                        </a>
                      </li>
                    ))}
                  </ul>
                  {portalHistory.confirmed_duplicates.length > 0 && (
                    <div>
                      <strong>Operator-confirmed same vacancy</strong>
                      <ul>
                        {portalHistory.confirmed_duplicates.map((link) => (
                          <li key={link.posting_id}>Linked posting {link.posting_id}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </section>

            {selectedOpportunity.ai_review_status ===
            "awaiting_ai_review" ? (
              <section
                className="automated-review"
                aria-label="AI review status"
              >
                <div className="automated-review-heading">
                  <div>
                    <span className="review-label">
                      Classification authority
                    </span>
                    <strong>Needs AI review</strong>
                  </div>
                </div>

                <p>
                  JOLT has captured and cleaned the source evidence.
                  Export the AI review package, analyze it externally,
                  then import the returned review file.
                </p>
              </section>
            ) : (
              <section
                className="automated-review"
                aria-label="External AI job review"
              >
                <div className="automated-review-heading">
                  <div>
                    <span className="review-label">
                      External AI decision
                    </span>
                    <strong>
                      {hardlineStopped(selectedOpportunity)
                        ? hardlineLabel(selectedOpportunity)
                        : aiDecisionLabel(selectedOpportunity)}
                    </strong>
                  </div>
                  <span>
                    Human confirmation required
                  </span>
                </div>

                {hardlineStopped(selectedOpportunity) && (
                  <div className="review-evidence-group">
                    <strong>{hardlineLabel(selectedOpportunity)}</strong>
                    <p>Reason: {hardlineReason(selectedOpportunity)}</p>
                    <p>Fit score not shown because a required condition was not met.</p>
                  </div>
                )}

                {selectedOpportunity.summary && (
                  <p>{selectedOpportunity.summary}</p>
                )}

                <div className="dimension-grid">
                  {!hardlineStopped(selectedOpportunity) && (
                    <div>
                      <span>AI priority</span>
                      <strong>
                        {selectedOpportunity.priority_score ?? "—"}
                      </strong>
                    </div>
                  )}
                  {!hardlineStopped(selectedOpportunity) && (
                    <div>
                      <span>Technical fit</span>
                      <strong>
                        {selectedOpportunity.technical_fit ?? "—"}
                      </strong>
                    </div>
                  )}
                  <div>
                    <span>Geography</span>
                    <strong>
                      {selectedOpportunity.geography_status ?? "unknown"}
                    </strong>
                  </div>
                  <div>
                    <span>Clearance</span>
                    <strong>
                      {selectedOpportunity.clearance_status ?? "unknown"}
                    </strong>
                  </div>
                  <div>
                    <span>Language</span>
                    <strong>
                      {selectedOpportunity.language_status ?? "unknown"}
                    </strong>
                  </div>
                </div>

                {selectedOpportunity.reasons.length > 0 && (
                  <div className="review-evidence-group">
                    <strong>AI review reasons</strong>
                    <ul>
                      {selectedOpportunity.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {selectedOpportunity.duplicate_of_posting_id && (
                  <p>
                    Duplicate of posting:{" "}
                    <code>
                      {selectedOpportunity.duplicate_of_posting_id}
                    </code>
                  </p>
                )}
              </section>
            )}

            <SourceDescription postingId={selectedOpportunity.posting_id} />
            <Sources postingId={selectedOpportunity.posting_id} />
          </aside>
        </div>
      )}
    </main>
  );
}



