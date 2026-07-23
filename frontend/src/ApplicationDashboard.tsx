import { useCallback, useEffect, useMemo, useState } from "react";

import { ApplicationWorkflow } from "./ApplicationWorkflow";
import type { ApplicationStatus } from "./ApplicationWorkflow";

type Opportunity = {
  posting_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  review_decision: string | null;
  application_id?: string | null;
  application_status?: ApplicationStatus | null;
  outcome_type?: string | null;
};

type ApplicationEvent = {
  event_id: string;
  event_type: string;
  from_status: string;
  to_status: string;
  notes: string;
  occurred_at: string;
};

type ApplicationDetail = {
  application_id: string;
  posting_id: string;
  status: ApplicationStatus;
  application_url: string;
  resume_used: string;
  notes: string;
  outcome_type: string | null;
  events: ApplicationEvent[];
};

type Props = { apiBase: string; active: boolean };
type PipelineLane = "preparing" | "applied" | "interviewing" | "offer" | "closed";
type WorkspaceTab = "overview" | "tasks" | "interviews" | "contacts" | "documents" | "timeline";
type LaneDefinition = { id: PipelineLane; label: string; description: string };

const LANES: LaneDefinition[] = [
  { id: "preparing", label: "Preparing", description: "Tailor materials and get ready to apply." },
  { id: "applied", label: "Applied", description: "Submitted and waiting for employer contact." },
  { id: "interviewing", label: "Interviewing", description: "Recruiter, technical, and hiring stages." },
  { id: "offer", label: "Offer", description: "Review and record the final offer decision." },
  { id: "closed", label: "Closed", description: "Completed, rejected, withdrawn, or no response." },
];

const TABS: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "tasks", label: "Tasks" },
  { id: "interviews", label: "Interviews" },
  { id: "contacts", label: "Contacts" },
  { id: "documents", label: "Documents" },
  { id: "timeline", label: "Timeline" },
];

const INTERVIEW_STATUSES = new Set<ApplicationStatus>([
  "recruiter_screen",
  "technical_interview",
  "hiring_manager_interview",
  "final_interview",
]);
const CLOSED_STATUSES = new Set<ApplicationStatus>(["rejected", "withdrawn", "no_response", "closed"]);

function label(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "ready to prepare";
}

function laneFor(item: Opportunity): PipelineLane {
  if (item.outcome_type || (item.application_status && CLOSED_STATUSES.has(item.application_status))) return "closed";
  if (!item.application_id || !item.application_status || item.application_status === "preparing") return "preparing";
  if (item.application_status === "offer") return "offer";
  if (INTERVIEW_STATUSES.has(item.application_status)) return "interviewing";
  return "applied";
}

function nextAction(item: Opportunity) {
  if (!item.application_id) return "Create preparation record";
  switch (item.application_status) {
    case "preparing": return "Finish documents and record external submission";
    case "submitted": return "Watch for acknowledgement or recruiter contact";
    case "acknowledged": return "Record recruiter contact when it arrives";
    case "recruiter_screen": return "Prepare for the next interview";
    case "technical_interview": return "Record the result or next interview";
    case "hiring_manager_interview": return "Record the result, final interview, or offer";
    case "final_interview": return "Record the final decision or offer";
    case "offer": return "Accept or decline the offer";
    default: return item.outcome_type ? "Reopen if the process changes" : "Review application status";
  }
}

function Placeholder({ title, copy }: { title: string; copy: string }) {
  return <section className="application-tab-placeholder"><h4>{title}</h4><p>{copy}</p></section>;
}

function Timeline({ detail, loading }: { detail: ApplicationDetail | null; loading: boolean }) {
  if (loading) return <p role="status">Loading application timeline…</p>;
  if (!detail) return <Placeholder title="No application timeline yet" copy="Create the preparation record first. JOLT will then preserve every stage change and outcome here." />;
  const events = [...detail.events].sort((left, right) => right.occurred_at.localeCompare(left.occurred_at));
  return (
    <section className="application-timeline" aria-labelledby="application-timeline-heading">
      <div className="application-tab-heading">
        <div><p className="eyebrow">Immutable activity history</p><h4 id="application-timeline-heading">Timeline</h4></div>
        <span>{events.length} events</span>
      </div>
      {events.length === 0 ? <p className="application-timeline-empty">No application events have been recorded.</p> : (
        <ol>
          {events.map((event) => (
            <li key={event.event_id}>
              <time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time>
              <div>
                <strong>{label(event.event_type)}</strong>
                {(event.from_status || event.to_status) && <p className="application-timeline-transition">{event.from_status ? label(event.from_status) : "Started"} → {event.to_status ? label(event.to_status) : "Recorded"}</p>}
                {event.notes && <p>{event.notes}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function ApplicationDashboard({ apiBase, active }: Props) {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedPostingId, setSelectedPostingId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [applicationDetail, setApplicationDetail] = useState<ApplicationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const refresh = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/application-index`);
    if (!response.ok) throw new Error("Unable to load application opportunities.");
    setOpportunities((await response.json()) as Opportunity[]);
  }, [apiBase]);

  useEffect(() => {
    if (!active) return;
    refresh().catch((caught) => setError(caught instanceof Error ? caught.message : "Application dashboard failed."));
  }, [active, refresh]);

  useEffect(() => {
    if (!selectedPostingId) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setSelectedPostingId(null); };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [selectedPostingId]);

  const candidates = useMemo(
    () => opportunities.filter((item) => item.review_decision === "pursue" || Boolean(item.application_id)),
    [opportunities],
  );
  const visibleCandidates = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) return candidates;
    return candidates.filter((item) => [item.title, item.company, item.location, item.application_status, item.outcome_type].join(" ").toLocaleLowerCase().includes(normalizedQuery));
  }, [candidates, query]);
  const grouped = useMemo(() => Object.fromEntries(
    LANES.map((lane) => [lane.id, visibleCandidates.filter((item) => laneFor(item) === lane.id)]),
  ) as Record<PipelineLane, Opportunity[]>, [visibleCandidates]);
  const selected = candidates.find((item) => item.posting_id === selectedPostingId) ?? null;

  const loadApplicationDetail = useCallback(async (applicationId: string | null | undefined) => {
    if (!applicationId) { setApplicationDetail(null); return; }
    setDetailLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}`);
      if (!response.ok) throw new Error("Unable to load application history.");
      setApplicationDetail((await response.json()) as ApplicationDetail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Application history failed.");
    } finally {
      setDetailLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    setActiveTab("overview");
    setApplicationDetail(null);
    if (selected) void loadApplicationDetail(selected.application_id);
  }, [loadApplicationDetail, selected?.application_id, selected?.posting_id]);

  async function refreshAfterChange() {
    setBusy(true);
    try {
      await refresh();
      if (selected?.application_id) await loadApplicationDetail(selected.application_id);
    } finally {
      setBusy(false);
    }
  }

  function openWorkspace(postingId: string) {
    setActiveTab("overview");
    setSelectedPostingId(postingId);
  }

  return (
    <section className="panel application-workspace" aria-labelledby="application-dashboard-heading">
      <div className="section-heading application-workspace-heading">
        <div><p className="eyebrow">Application pipeline</p><h2 id="application-dashboard-heading">Application management</h2><p>Move from preparation to applied, interviews, offer, and closure without losing history.</p></div>
        <button type="button" className="secondary" disabled={busy} onClick={() => refresh().catch(() => setError("Unable to refresh applications."))}>Refresh applications</button>
      </div>
      <div className="application-board-toolbar">
        <label className="application-search"><span>Search pipeline</span><input type="search" value={query} placeholder="Role, company, location, or stage" onChange={(event) => setQuery(event.target.value)} /></label>
        <p className="application-boundary">JOLT records the workflow. Applications and recruiter contact remain under your control.</p>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="application-board" aria-label="Application pipeline board">
        {LANES.map((lane) => (
          <section className={`application-lane application-lane-${lane.id}`} key={lane.id} aria-labelledby={`lane-${lane.id}`}>
            <header className="application-lane-header"><div><h3 id={`lane-${lane.id}`}>{lane.label}</h3><p>{lane.description}</p></div><strong aria-label={`${lane.label} count`}>{grouped[lane.id].length}</strong></header>
            <div className="application-lane-cards">
              {grouped[lane.id].length === 0 ? <p className="application-lane-empty">No applications</p> : grouped[lane.id].map((opportunity) => (
                <article className="application-card" key={opportunity.posting_id}>
                  <button type="button" className="application-card-open" onClick={() => openWorkspace(opportunity.posting_id)} aria-label={`Open ${opportunity.title || "untitled opportunity"}`}>
                    <span className="application-card-stage">{label(opportunity.outcome_type ?? opportunity.application_status)}</span><strong>{opportunity.title || "Untitled opportunity"}</strong><span className="application-card-company">{opportunity.company || "Unknown company"}</span>{opportunity.location && <span className="application-card-location">{opportunity.location}</span>}<span className="application-card-next"><b>Next:</b> {nextAction(opportunity)}</span>
                  </button>
                  <div className="application-card-links">{opportunity.source_url && <a href={opportunity.source_url} target="_blank" rel="noreferrer">Source job</a>}<a href={`${apiBase}/api/opportunities/${opportunity.posting_id}/preparation-pack`} download>Preparation pack</a></div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
      {selected && (
        <div className="application-workspace-overlay" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setSelectedPostingId(null); }}>
          <section className="application-detail-workspace" role="dialog" aria-modal="true" aria-labelledby="application-detail-title">
            <header className="application-detail-header"><div><p className="eyebrow">Application workspace</p><h3 id="application-detail-title">{selected.title || "Untitled opportunity"}</h3><p>{[selected.company, selected.location].filter(Boolean).join(" · ")}</p></div><button type="button" className="secondary" onClick={() => setSelectedPostingId(null)}>Close</button></header>
            <nav className="application-detail-tabs" aria-label="Application workspace sections" role="tablist">
              {TABS.map((tab) => <button key={tab.id} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`application-panel-${tab.id}`} className={activeTab === tab.id ? "application-detail-tab-active" : ""} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}
            </nav>
            <div className="application-detail-body" id={`application-panel-${activeTab}`} role="tabpanel">
              {activeTab === "overview" && <ApplicationWorkflow apiBase={apiBase} postingId={selected.posting_id} title={selected.title || "Untitled opportunity"} reviewDecision={selected.review_decision} applicationId={selected.application_id} applicationStatus={selected.application_status} disabled={busy} onChanged={refreshAfterChange} onError={setError} />}
              {activeTab === "tasks" && <Placeholder title="Tasks are the next persisted workflow slice" copy="This panel will hold dated next actions, ownership, completion state, and overdue indicators. It is intentionally not storing temporary browser-only tasks." />}
              {activeTab === "interviews" && <Placeholder title="Interview records are not persisted yet" copy="The next backend slice will capture interview type, date, participants, preparation notes, outcome, and follow-up." />}
              {activeTab === "contacts" && <Placeholder title="Contacts are not persisted yet" copy="Recruiters, hiring managers, and referral contacts will be attached to this application in a later structured-data slice." />}
              {activeTab === "documents" && <Placeholder title="Document records are not persisted yet" copy="Resume, cover letter, preparation pack, and supporting evidence will be managed here after the document contract is implemented." />}
              {activeTab === "timeline" && <Timeline detail={applicationDetail} loading={detailLoading} />}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
