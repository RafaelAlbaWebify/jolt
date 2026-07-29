import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApplicationContacts } from "./ApplicationContacts";
import { ApplicationDocuments } from "./ApplicationDocuments";
import { ApplicationInterviews } from "./ApplicationInterviews";
import { ApplicationTasks } from "./ApplicationTasks";
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
  application_status?: ApplicationStatus | string | null;
  outcome_type?: string | null;
  last_activity_at?: string | null;
  next_due_at?: string | null;
  next_due_kind?: string | null;
  document_state?: string | null;
  overdue?: boolean;
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
  status: ApplicationStatus | string;
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
  { id: "applied", label: "Applied", description: "Submitted and awaiting employer contact." },
  { id: "interviewing", label: "Interviewing", description: "Recruiter, technical, and hiring stages." },
  { id: "offer", label: "Offer", description: "Review and record the final offer decision." },
  { id: "closed", label: "Closed / archived", description: "Completed, rejected, withdrawn, archived, or no response." },
];

const TABS: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "tasks", label: "Tasks" },
  { id: "interviews", label: "Interviews" },
  { id: "contacts", label: "Contacts" },
  { id: "documents", label: "Documents" },
  { id: "timeline", label: "Timeline" },
];

const INTERVIEW_STATUSES = new Set<string>([
  "recruiter_screen",
  "technical_interview",
  "hiring_manager_interview",
  "final_interview",
]);
const CLOSED_STATUSES = new Set<string>(["rejected", "withdrawn", "no_response", "closed", "archived"]);
const OUTCOME_CODES = [
  "rejected_by_employer",
  "withdrawn_by_user",
  "no_response",
  "offer_declined",
  "offer_accepted",
  "role_closed",
];
const LANE_TARGET_STATUS: Record<PipelineLane, ApplicationStatus> = {
  preparing: "preparing",
  applied: "submitted",
  interviewing: "recruiter_screen",
  offer: "offer",
  closed: "closed",
};

function label(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "ready to prepare";
}

function formatEventNotes(notes: string) {
  return OUTCOME_CODES.reduce((formatted, code) => formatted.replaceAll(code, label(code)), notes);
}

function laneFor(item: Opportunity): PipelineLane {
  if (item.outcome_type || (item.application_status && CLOSED_STATUSES.has(item.application_status))) return "closed";
  if (!item.application_id || !item.application_status || item.application_status === "preparing") return "preparing";
  if (item.application_status === "offer") return "offer";
  if (item.application_status && INTERVIEW_STATUSES.has(item.application_status)) return "interviewing";
  return "applied";
}

function opportunityIdentity(item: Opportunity) {
  return item.application_id ? `application:${item.application_id}` : `posting:${item.posting_id}`;
}

function deduplicateOpportunities(items: Opportunity[]) {
  const unique = new Map<string, Opportunity>();
  for (const item of items) {
    const identity = opportunityIdentity(item);
    if (!unique.has(identity)) unique.set(identity, item);
  }
  return [...unique.values()];
}

function availableTargetLanes(item: Opportunity): PipelineLane[] {
  const currentLane = laneFor(item);
  if (item.application_status === "archived") return ["closed"];
  if (!item.application_id || !item.application_status) return [currentLane];
  const activeLanes: PipelineLane[] = ["preparing", "applied", "interviewing", "offer"];
  if (currentLane === "closed" || item.outcome_type) return ["closed", ...activeLanes];
  return activeLanes;
}

function nextAction(item: Opportunity) {
  if (!item.application_id) return "Create preparation record";
  switch (item.application_status) {
    case "preparing":
      return "Finish documents and record external submission";
    case "submitted":
      return "Watch for acknowledgement or recruiter contact";
    case "acknowledged":
      return "Record recruiter contact when it arrives";
    case "recruiter_screen":
      return "Prepare for the next interview";
    case "technical_interview":
      return "Record the result or next interview";
    case "hiring_manager_interview":
      return "Record the result, final interview, or offer";
    case "final_interview":
      return "Record the final decision or offer";
    case "offer":
      return "Accept or decline the offer";
    case "archived":
      return "Restore if this process becomes active again";
    default:
      return item.outcome_type ? "Reopen if the process changes" : "Review application status";
  }
}

function displayDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "None scheduled";
}

function Placeholder({ title, copy }: { title: string; copy: string }) {
  return (
    <section className="application-tab-placeholder">
      <h4>{title}</h4>
      <p>{copy}</p>
    </section>
  );
}

function Timeline({ detail, loading }: { detail: ApplicationDetail | null; loading: boolean }) {
  if (loading) return <p role="status">Loading application timeline…</p>;
  if (!detail) {
    return (
      <Placeholder
        title="No application timeline yet"
        copy="Create the preparation record first. JOLT will then preserve every stage change and outcome here."
      />
    );
  }
  const events = [...detail.events].sort((left, right) => right.occurred_at.localeCompare(left.occurred_at));
  return (
    <section className="application-timeline" aria-labelledby="application-timeline-heading">
      <div className="application-tab-heading">
        <div>
          <p className="eyebrow">Immutable activity history</p>
          <h4 id="application-timeline-heading">Timeline</h4>
        </div>
        <span>{events.length} events</span>
      </div>
      {events.length === 0 ? (
        <p className="application-timeline-empty">No application events have been recorded.</p>
      ) : (
        <ol>
          {events.map((event) => (
            <li key={event.event_id}>
              <time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time>
              <div>
                <strong>{label(event.event_type)}</strong>
                {(event.from_status || event.to_status) && (
                  <p className="application-timeline-transition">
                    {event.from_status ? label(event.from_status) : "Started"} → {event.to_status ? label(event.to_status) : "Recorded"}
                  </p>
                )}
                {event.notes && <p>{formatEventNotes(event.notes)}</p>}
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
  const [draggedPostingId, setDraggedPostingId] = useState<string | null>(null);
  const [dragOverLane, setDragOverLane] = useState<PipelineLane | null>(null);
  const [moveNotice, setMoveNotice] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const movingApplicationIds = useRef(new Set<string>());
  const detailRequestRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/application-index${showArchived ? "?include_archived=true" : ""}`);
    if (!response.ok) throw new Error("Unable to load application opportunities.");
    const rows = (await response.json()) as Opportunity[];
    setOpportunities(deduplicateOpportunities(rows));
  }, [apiBase, showArchived]);

  useEffect(() => {
    if (active) refresh().catch((caught) => setError(caught instanceof Error ? caught.message : "Application dashboard failed."));
  }, [active, refresh]);

  useEffect(() => {
    if (!selectedPostingId) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedPostingId(null);
    };
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
  const archivedCount = useMemo(
    () => opportunities.filter((item) => item.application_status === "archived").length,
    [opportunities],
  );
  const visibleCandidates = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) return candidates;
    return candidates.filter((item) =>
      [item.title, item.company, item.location, item.application_status, item.outcome_type]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery),
    );
  }, [candidates, query]);
  const grouped = useMemo(
    () =>
      Object.fromEntries(LANES.map((lane) => [lane.id, visibleCandidates.filter((item) => laneFor(item) === lane.id)])) as Record<
        PipelineLane,
        Opportunity[]
      >,
    [visibleCandidates],
  );
  const selected = candidates.find((item) => item.posting_id === selectedPostingId) ?? null;

  const loadApplicationDetail = useCallback(
    async (applicationId: string | null | undefined) => {
      if (!applicationId) {
        detailRequestRef.current?.abort();
        setApplicationDetail(null);
        setDetailLoading(false);
        return;
      }
      detailRequestRef.current?.abort();
      const controller = new AbortController();
      detailRequestRef.current = controller;
      setDetailLoading(true);
      setError("");
      try {
        const response = await fetch(`${apiBase}/api/applications/${applicationId}`, { signal: controller.signal });
        if (!response.ok) throw new Error("Unable to load application history.");
        const detail = (await response.json()) as ApplicationDetail;
        if (detailRequestRef.current === controller) setApplicationDetail(detail);
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        if (detailRequestRef.current === controller) {
          setError(caught instanceof Error ? caught.message : "Application history failed.");
        }
      } finally {
        if (detailRequestRef.current === controller) setDetailLoading(false);
      }
    },
    [apiBase],
  );

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

  async function moveApplication(item: Opportunity, targetLane: PipelineLane) {
    if (!item.application_id || item.application_status === "archived" || laneFor(item) === targetLane || busy) return;
    if (!availableTargetLanes(item).includes(targetLane)) {
      setError(`The application cannot move directly from ${laneFor(item)} to ${targetLane}.`);
      return;
    }
    if (movingApplicationIds.current.has(item.application_id)) return;
    movingApplicationIds.current.add(item.application_id);
    setBusy(true);
    setError("");
    setMoveNotice("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${item.application_id}/transitions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: LANE_TARGET_STATUS[targetLane],
          notes: `Moved on application board from ${laneFor(item)} to ${targetLane}.`,
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The application could not be moved.");
      }
      await refresh();
      setMoveNotice(`${item.title || "Application"} moved to ${LANES.find((lane) => lane.id === targetLane)?.label}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The application could not be moved.");
    } finally {
      if (item.application_id) movingApplicationIds.current.delete(item.application_id);
      setBusy(false);
      setDraggedPostingId(null);
      setDragOverLane(null);
    }
  }

  async function archiveCard(item: Opportunity) {
    if (!item.application_id || busy) return;
    const confirmed = window.confirm(
      `Archive ${item.title || "this application"}? It will be removed from the active board, but its history stays in the database.`,
    );
    if (!confirmed) return;
    setBusy(true);
    setError("");
    setMoveNotice("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${item.application_id}/archive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: "Archived from the Applications board." }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The application could not be archived.");
      }
      if (selectedPostingId === item.posting_id) setSelectedPostingId(null);
      await refresh();
      setMoveNotice(`${item.title || "Application"} archived and removed from the active board.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The application could not be archived.");
    } finally {
      setBusy(false);
    }
  }

  async function restoreCard(item: Opportunity) {
    if (!item.application_id || busy) return;
    setBusy(true);
    setError("");
    setMoveNotice("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${item.application_id}/restore`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: "Restored from the Applications archived view." }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The application could not be restored.");
      }
      await refresh();
      setMoveNotice(`${item.title || "Application"} restored to the active board.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The application could not be restored.");
    } finally {
      setBusy(false);
    }
  }

  const draggedItem = candidates.find((item) => item.posting_id === draggedPostingId) ?? null;

  return (
    <section className="panel application-workspace" aria-labelledby="application-dashboard-heading">
      <div className="section-heading application-workspace-heading">
        <div>
          <p className="eyebrow">Application pipeline</p>
          <h2 id="application-dashboard-heading">Applications</h2>
          <p>Move from preparation to applied, interviews, offer, and closure without losing history.</p>
        </div>
        <button
          type="button"
          className="secondary"
          disabled={busy}
          onClick={() => refresh().catch(() => setError("Unable to refresh applications."))}
        >
          Refresh applications
        </button>
      </div>
      <div className="application-board-toolbar">
        <label className="application-search">
          <span>Search pipeline</span>
          <input
            type="search"
            value={query}
            placeholder="Role, company, location, or stage"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="professional-source-checkbox">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(event) => setShowArchived(event.target.checked)}
          />
          Show archived cards{showArchived ? ` (${archivedCount})` : ""}
        </label>
        <p className="application-boundary">Move cards forward or backward to correct the pipeline. Archive removes a card from the active board while preserving history.</p>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {moveNotice && (
        <p className="application-move-notice" role="status">
          {moveNotice}
        </p>
      )}
      <div className="application-board" aria-label="Application pipeline board">
        {LANES.map((lane) => (
          <section
            className={`application-lane application-lane-${lane.id}${dragOverLane === lane.id ? " application-lane-drop-target" : ""}`}
            key={lane.id}
            aria-labelledby={`lane-${lane.id}`}
            onDragEnter={(event) => {
              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id) && laneFor(draggedItem) !== lane.id) {
                event.preventDefault();
                setDragOverLane(lane.id);
              }
            }}
            onDragOver={(event) => {
              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id) && laneFor(draggedItem) !== lane.id) {
                event.preventDefault();
              }
            }}
            onDragLeave={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragOverLane(null);
            }}
            onDrop={(event) => {
              event.preventDefault();
              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id)) {
                void moveApplication(draggedItem, lane.id);
              }
            }}
          >
            <header className="application-lane-header">
              <div>
                <h3 id={`lane-${lane.id}`}>{lane.label}</h3>
                <p>{lane.description}</p>
              </div>
              <strong aria-label={`${lane.label} count`}>{grouped[lane.id].length}</strong>
            </header>
            <div className="application-lane-cards">
              {grouped[lane.id].length === 0 ? (
                <p className="application-lane-empty">No applications</p>
              ) : (
                grouped[lane.id].map((opportunity) => (
                  <article
                    className={`application-card${opportunity.overdue ? " application-card-overdue" : ""}${
                      draggedPostingId === opportunity.posting_id ? " application-card-dragging" : ""
                    }`}
                    key={opportunityIdentity(opportunity)}
                    data-application-id={opportunity.application_id ?? undefined}
                    data-posting-id={opportunity.posting_id}
                    draggable={availableTargetLanes(opportunity).length > 1 && !busy}
                    onDragStart={(event) => {
                      if (!opportunity.application_id || availableTargetLanes(opportunity).length <= 1) {
                        event.preventDefault();
                        return;
                      }
                      event.dataTransfer.effectAllowed = "move";
                      event.dataTransfer.setData("text/plain", opportunity.posting_id);
                      setDraggedPostingId(opportunity.posting_id);
                      setMoveNotice("");
                    }}
                    onDragEnd={() => {
                      setDraggedPostingId(null);
                      setDragOverLane(null);
                    }}
                  >
                    <button
                      type="button"
                      className="application-card-open"
                      onClick={() => openWorkspace(opportunity.posting_id)}
                      aria-label={`Open ${opportunity.title || "untitled opportunity"}`}
                    >
                      <span className="application-card-stage">{label(opportunity.outcome_type ?? opportunity.application_status)}</span>
                      {opportunity.overdue && <span className="application-card-alert">Overdue</span>}
                      <strong>{opportunity.title || "Untitled opportunity"}</strong>
                      <span className="application-card-company">{opportunity.company || "Unknown company"}</span>
                      {opportunity.location && <span className="application-card-location">{opportunity.location}</span>}
                      <dl className="application-card-signals">
                        <div>
                          <dt>Last activity</dt>
                          <dd>{displayDate(opportunity.last_activity_at)}</dd>
                        </div>
                        <div>
                          <dt>Next {opportunity.next_due_kind ?? "due"}</dt>
                          <dd>{displayDate(opportunity.next_due_at)}</dd>
                        </div>
                        <div>
                          <dt>Resume</dt>
                          <dd>{opportunity.document_state ?? "Unknown"}</dd>
                        </div>
                      </dl>
                      <span className="application-card-next">
                        <b>Next:</b> {nextAction(opportunity)}
                      </span>
                    </button>
                    <div className="application-card-move">
                      <label>
                        <span>Move to lane</span>
                        <select
                          aria-label={`Move ${opportunity.title || "untitled opportunity"} to lane`}
                          value={laneFor(opportunity)}
                          disabled={availableTargetLanes(opportunity).length <= 1 || busy}
                          onChange={(event) => void moveApplication(opportunity, event.target.value as PipelineLane)}
                        >
                          {availableTargetLanes(opportunity).map((targetLane) => {
                            const target = LANES.find((lane) => lane.id === targetLane)!;
                            return (
                              <option key={target.id} value={target.id}>
                                {target.label}
                              </option>
                            );
                          })}
                        </select>
                      </label>
                    </div>
                    <div className="application-card-links">
                      {opportunity.source_url && (
                        <a href={opportunity.source_url} target="_blank" rel="noreferrer">
                          Source job
                        </a>
                      )}
                      <a href={`${apiBase}/api/opportunities/${opportunity.posting_id}/preparation-pack`} download>
                        Preparation pack
                      </a>
                      {opportunity.application_id && opportunity.application_status === "archived" && (
                        <button
                          type="button"
                          className="secondary application-card-restore"
                          disabled={busy}
                          onClick={() => void restoreCard(opportunity)}
                        >
                          Restore card
                        </button>
                      )}
                      {opportunity.application_id && opportunity.application_status !== "archived" && (
                        <button
                          type="button"
                          className="danger application-card-archive"
                          disabled={busy}
                          onClick={() => void archiveCard(opportunity)}
                        >
                          Archive card
                        </button>
                      )}
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>
        ))}
      </div>
      {selected && (
        <div
          className="application-workspace-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setSelectedPostingId(null);
          }}
        >
          <section className="application-detail-workspace" role="dialog" aria-modal="true" aria-labelledby="application-detail-title">
            <header className="application-detail-header">
              <div>
                <p className="eyebrow">Application workspace</p>
                <h3 id="application-detail-title">{selected.title || "Untitled opportunity"}</h3>
                <p>{[selected.company, selected.location].filter(Boolean).join(" · ")}</p>
              </div>
              <button type="button" className="secondary" onClick={() => setSelectedPostingId(null)}>
                Close
              </button>
            </header>
            <nav className="application-detail-tabs" aria-label="Application workspace sections" role="tablist">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  aria-controls={`application-panel-${tab.id}`}
                  className={activeTab === tab.id ? "application-detail-tab-active" : ""}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
            <div className="application-detail-body" id={`application-panel-${activeTab}`} role="tabpanel">
              {activeTab === "overview" && (
                <ApplicationWorkflow
                  apiBase={apiBase}
                  postingId={selected.posting_id}
                  title={selected.title || "Untitled opportunity"}
                  reviewDecision={selected.review_decision}
                  applicationId={selected.application_id}
                  applicationStatus={selected.application_status as ApplicationStatus | null | undefined}
                  disabled={busy || selected.application_status === "archived"}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "tasks" && (
                <ApplicationTasks apiBase={apiBase} applicationId={selected.application_id} onChanged={refreshAfterChange} onError={setError} />
              )}
              {activeTab === "interviews" && (
                <ApplicationInterviews
                  apiBase={apiBase}
                  applicationId={selected.application_id}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "contacts" && (
                <ApplicationContacts
                  apiBase={apiBase}
                  applicationId={selected.application_id}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "documents" && (
                <ApplicationDocuments
                  apiBase={apiBase}
                  applicationId={selected.application_id}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "timeline" && <Timeline detail={applicationDetail} loading={detailLoading} />}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
