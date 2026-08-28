import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApplicationContacts } from "./ApplicationContacts";
import { ApplicationDocuments } from "./ApplicationDocuments";
import { ApplicationInterviews } from "./ApplicationInterviews";
import { ApplicationTasks } from "./ApplicationTasks";
import { ApplicationWorkflow } from "./ApplicationWorkflow";
import type { ApplicationStatus } from "./ApplicationWorkflow";

type ApplicationRecordStatus = ApplicationStatus | "archived";

type Opportunity = {
  posting_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  review_decision: string | null;
  application_id?: string | null;
  application_status?: ApplicationRecordStatus | null;
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
  status: ApplicationRecordStatus;
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
type OutcomeChoice = { value: string; label: string };

const LANES: LaneDefinition[] = [
  { id: "preparing", label: "Preparing", description: "Tailor materials and get ready to apply." },
  { id: "applied", label: "Applied", description: "Submitted and awaiting employer contact." },
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
const OUTCOME_CODES = [
  "rejected_by_employer",
  "withdrawn_by_user",
  "no_response",
  "offer_declined",
  "offer_accepted",
  "role_closed",
];

const GENERAL_CLOSE_OUTCOMES: OutcomeChoice[] = [
  { value: "rejected_by_employer", label: "Rejected by employer" },
  { value: "withdrawn_by_user", label: "Withdrawn by me" },
  { value: "no_response", label: "No response" },
  { value: "role_closed", label: "Role closed" },
];

const OFFER_CLOSE_OUTCOMES: OutcomeChoice[] = [
  { value: "offer_accepted", label: "Offer accepted" },
  { value: "offer_declined", label: "Offer declined" },
];

function label(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "unknown";
}

function formatEventNotes(notes: string) {
  return OUTCOME_CODES.reduce((formatted, code) => formatted.replaceAll(code, label(code)), notes);
}

function activeLaneFor(item: Opportunity): PipelineLane | null {
  if (!item.application_id || !item.application_status || item.application_status === "archived") return null;
  if (item.outcome_type || CLOSED_STATUSES.has(item.application_status)) return "closed";
  if (item.application_status === "preparing") return "preparing";
  if (item.application_status === "offer") return "offer";
  if (INTERVIEW_STATUSES.has(item.application_status)) return "interviewing";
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

function activityTimestamp(item: Opportunity) {
  if (!item.last_activity_at) return Number.NEGATIVE_INFINITY;
  const parsed = Date.parse(item.last_activity_at);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
}

function newestActivityFirst(left: Opportunity, right: Opportunity) {
  const leftTimestamp = activityTimestamp(left);
  const rightTimestamp = activityTimestamp(right);

  if (leftTimestamp !== rightTimestamp) {
    return rightTimestamp - leftTimestamp;
  }

  return opportunityIdentity(left).localeCompare(opportunityIdentity(right));
}

function availableTargetLanes(item: Opportunity): PipelineLane[] {
  const currentLane = activeLaneFor(item);
  if (!currentLane) return [];

  const activeLanes: PipelineLane[] = ["preparing", "applied", "interviewing", "offer"];
  if (currentLane === "closed" || item.outcome_type) return ["closed", ...activeLanes];
  return [...activeLanes, "closed"];
}

function targetStatusForLane(
  item: Opportunity,
  targetLane: Exclude<PipelineLane, "closed">,
): ApplicationStatus {
  if (targetLane === "preparing") return "preparing";
  if (targetLane === "applied") return "submitted";
  if (targetLane === "offer") return "offer";

  if (item.application_status && item.application_status !== "archived" && INTERVIEW_STATUSES.has(item.application_status)) {
    return item.application_status;
  }

  const currentLane = activeLaneFor(item);
  if (currentLane === "offer" || currentLane === "closed") return "final_interview";
  return "recruiter_screen";
}

function closeOutcomesFor(item: Opportunity): OutcomeChoice[] {
  return item.application_status === "offer" ? OFFER_CLOSE_OUTCOMES : GENERAL_CLOSE_OUTCOMES;
}

function canDeletePermanently(item: Opportunity) {
  return item.application_status === "archived" || activeLaneFor(item) === "closed";
}

function nextAction(item: Opportunity) {
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

function activeApplicationStatus(status: ApplicationRecordStatus | null | undefined): ApplicationStatus | null {
  return status && status !== "archived" ? status : null;
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
        copy="The application record is unavailable, so its timeline cannot be shown."
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

function ApplicationSummaryButton({ item, onOpen }: { item: Opportunity; onOpen: () => void }) {
  return (
    <button
      type="button"
      className="application-card-open"
      onClick={onOpen}
      aria-label={`Open ${item.title || "untitled opportunity"}`}
    >
      <span className="application-card-stage">{label(item.outcome_type ?? item.application_status)}</span>
      {item.overdue && <span className="application-card-alert">Overdue</span>}
      <strong>{item.title || "Untitled opportunity"}</strong>
      <span className="application-card-company">{item.company || "Unknown company"}</span>
      {item.location && <span className="application-card-location">{item.location}</span>}
      <dl className="application-card-signals">
        <div>
          <dt>Last activity</dt>
          <dd>{displayDate(item.last_activity_at)}</dd>
        </div>
        <div>
          <dt>Next {item.next_due_kind ?? "due"}</dt>
          <dd>{displayDate(item.next_due_at)}</dd>
        </div>
        <div>
          <dt>Resume</dt>
          <dd>{item.document_state ?? "Unknown"}</dd>
        </div>
      </dl>
      <span className="application-card-next">
        <b>Next:</b> {nextAction(item)}
      </span>
    </button>
  );
}

function ArchivedOverview({ detail, loading }: { detail: ApplicationDetail | null; loading: boolean }) {
  if (loading) return <p role="status">Loading archived application…</p>;
  if (!detail) return <Placeholder title="Archived application unavailable" copy="The archived record could not be loaded." />;
  return (
    <section className="application-archived-overview">
      <p className="application-read-only-notice" role="status">
        Archived application — this workspace is read-only until the application is restored.
      </p>
      <dl>
        <div><dt>Status</dt><dd>Archived</dd></div>
        <div><dt>Final outcome</dt><dd>{detail.outcome_type ? label(detail.outcome_type) : "None recorded"}</dd></div>
        <div><dt>Application URL</dt><dd>{detail.application_url || "Not recorded"}</dd></div>
        <div><dt>CV / resume</dt><dd>{detail.resume_used || "Not recorded"}</dd></div>
        <div><dt>Preparation notes</dt><dd>{detail.notes || "None recorded"}</dd></div>
      </dl>
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
  const [closingPostingId, setClosingPostingId] = useState<string | null>(null);
  const [closeOutcome, setCloseOutcome] = useState("rejected_by_employer");
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

  useEffect(() => {
    if (!closingPostingId) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setClosingPostingId(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [closingPostingId]);

  const candidates = useMemo(
    () => opportunities.filter((item) => Boolean(item.application_id)),
    [opportunities],
  );
  const activeCandidates = useMemo(
    () => candidates.filter((item) => item.application_status !== "archived"),
    [candidates],
  );
  const archivedCandidates = useMemo(
    () => candidates.filter((item) => item.application_status === "archived"),
    [candidates],
  );
  const visibleActiveCandidates = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) return activeCandidates;
    return activeCandidates.filter((item) =>
      [item.title, item.company, item.location, item.application_status, item.outcome_type]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery),
    );
  }, [activeCandidates, query]);
  const visibleArchivedCandidates = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) return archivedCandidates;
    return archivedCandidates.filter((item) =>
      [item.title, item.company, item.location, item.outcome_type]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery),
    );
  }, [archivedCandidates, query]);
  const grouped = useMemo(
    () => Object.fromEntries(
      LANES.map((lane) => [
        lane.id,
        visibleActiveCandidates
          .filter((item) => activeLaneFor(item) === lane.id)
          .sort(newestActivityFirst),
      ]),
    ) as Record<PipelineLane, Opportunity[]>,
    [visibleActiveCandidates],
  );
  const selected = candidates.find((item) => item.posting_id === selectedPostingId) ?? null;
  const closingItem = activeCandidates.find((item) => item.posting_id === closingPostingId) ?? null;
  const draggedItem = activeCandidates.find((item) => item.posting_id === draggedPostingId) ?? null;

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
    setError("");
    setActiveTab("overview");
    setSelectedPostingId(postingId);
  }

  function openCloseDialog(item: Opportunity) {
    const outcomes = closeOutcomesFor(item);
    setCloseOutcome(outcomes[0].value);
    setClosingPostingId(item.posting_id);
    setDraggedPostingId(null);
    setDragOverLane(null);
    setMoveNotice("");
    setError("");
  }

  async function moveApplication(item: Opportunity, targetLane: PipelineLane) {
    const currentLane = activeLaneFor(item);
    if (!item.application_id || !currentLane || currentLane === targetLane || busy) return;

    if (!availableTargetLanes(item).includes(targetLane)) {
      setError(`The application cannot move directly from ${currentLane} to ${targetLane}.`);
      return;
    }

    if (targetLane === "closed") {
      openCloseDialog(item);
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
          status: targetStatusForLane(item, targetLane),
          notes: `Moved on application board from ${currentLane} to ${targetLane}.`,
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
      movingApplicationIds.current.delete(item.application_id);
      setBusy(false);
      setDraggedPostingId(null);
      setDragOverLane(null);
    }
  }

  async function closeApplication(item: Opportunity) {
    if (!item.application_id || busy) return;
    const outcomes = closeOutcomesFor(item);
    const selectedOutcome = outcomes.some((outcome) => outcome.value === closeOutcome)
      ? closeOutcome
      : outcomes[0].value;

    setBusy(true);
    setError("");
    setMoveNotice("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${item.application_id}/outcomes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outcome_type: selectedOutcome,
          notes: "Closed from the Applications board.",
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The application could not be closed.");
      }
      setClosingPostingId(null);
      await refresh();
      const outcomeLabel = outcomes.find((outcome) => outcome.value === selectedOutcome)?.label ?? selectedOutcome;
      setMoveNotice(`${item.title || "Application"} closed as ${outcomeLabel}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The application could not be closed.");
    } finally {
      setBusy(false);
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

  async function deleteCardPermanently(item: Opportunity) {
    if (!item.application_id || !canDeletePermanently(item) || busy) return;
    const confirmed = window.confirm(
      `Permanently delete ${item.title || "this application"}? ` +
        "Its application history, outcome, tasks, interviews, contacts, and documents will be removed. " +
        "The opportunity and capture evidence will remain. This cannot be undone.",
    );
    if (!confirmed) return;

    setBusy(true);
    setError("");
    setMoveNotice("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${item.application_id}/delete`, { method: "POST" });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The application could not be deleted.");
      }
      if (selectedPostingId === item.posting_id) setSelectedPostingId(null);
      await refresh();
      setMoveNotice(
        `${item.title || "Application"} permanently deleted. The opportunity and capture evidence were preserved.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The application could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel application-workspace" aria-labelledby="application-dashboard-heading">
      <div className="section-heading application-workspace-heading">
        <div>
          <p className="eyebrow">Application pipeline</p>
          <h2 id="application-dashboard-heading">Application Pipeline</h2>
          <p>Track active applications from preparation through closure without losing history.</p>
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
          Show archived cards
        </label>
        <p className="application-boundary">
          Closed means the process ended. Archived applications are shown separately and remain read-only until restored.
        </p>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {moveNotice && <p className="application-move-notice" role="status">{moveNotice}</p>}

      <div className="application-board" aria-label="Application pipeline board">
        {LANES.map((lane) => (
          <section
            className={`application-lane application-lane-${lane.id}${dragOverLane === lane.id ? " application-lane-drop-target" : ""}`}
            key={lane.id}
            aria-labelledby={`lane-${lane.id}`}
            onDragEnter={(event) => {
              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id) && activeLaneFor(draggedItem) !== lane.id) {
                event.preventDefault();
                setDragOverLane(lane.id);
              }
            }}
            onDragOver={(event) => {
              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id) && activeLaneFor(draggedItem) !== lane.id) {
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
                grouped[lane.id].map((opportunity) => {
                  const currentLane = activeLaneFor(opportunity);
                  const targets = availableTargetLanes(opportunity);
                  const canDrag = Boolean(opportunity.application_id && targets.length > 1 && !busy);
                  return (
                    <article
                      className={`application-card${opportunity.overdue ? " application-card-overdue" : ""}${draggedPostingId === opportunity.posting_id ? " application-card-dragging" : ""}`}
                      key={opportunityIdentity(opportunity)}
                      data-application-id={opportunity.application_id ?? undefined}
                      data-posting-id={opportunity.posting_id}
                      draggable={false}
                    >
                      <ApplicationSummaryButton item={opportunity} onOpen={() => openWorkspace(opportunity.posting_id)} />
                      <div className="application-card-move">
                        <button
                          type="button"
                          className="application-card-drag-handle"
                          draggable={canDrag}
                          disabled={!canDrag}
                          aria-label={`Drag ${opportunity.title || "untitled opportunity"} to another stage`}
                          title="Drag this handle to move the application"
                          onDragStart={(event) => {
                            if (!canDrag) {
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
                          Drag to move
                        </button>
                        <label>
                          <span>Move stage</span>
                          <select
                            aria-label={`Move ${opportunity.title || "untitled opportunity"} to stage`}
                            value={currentLane ?? "preparing"}
                            disabled={targets.length <= 1 || busy}
                            onChange={(event) => void moveApplication(opportunity, event.target.value as PipelineLane)}
                          >
                            {targets.map((targetLane) => {
                              const target = LANES.find((laneItem) => laneItem.id === targetLane)!;
                              return <option key={target.id} value={target.id}>{target.label}</option>;
                            })}
                          </select>
                        </label>
                      </div>
                      <div className="application-card-links">
                        {opportunity.source_url && <a href={opportunity.source_url} target="_blank" rel="noreferrer">Source job</a>}
                        <a href={`${apiBase}/api/opportunities/${opportunity.posting_id}/preparation-pack`} download>Download prep pack</a>
                        <button
                          type="button"
                          className="danger application-card-archive"
                          disabled={busy}
                          onClick={() => void archiveCard(opportunity)}
                        >
                          Archive card
                        </button>
                        {currentLane === "closed" && (
                          <button
                            type="button"
                            className="danger application-card-delete"
                            disabled={busy}
                            onClick={() => void deleteCardPermanently(opportunity)}
                          >
                            Delete permanently
                          </button>
                        )}
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </section>
        ))}
      </div>

      {showArchived && (
        <section className="application-archived-section" aria-labelledby="application-archived-heading">
          <div className="application-archived-heading">
            <div>
              <p className="eyebrow">Separate lifecycle state</p>
              <h3 id="application-archived-heading">Archived applications</h3>
              <p>Archived records do not count as Closed and cannot be edited until restored.</p>
            </div>
            <strong aria-label="Archived count">{visibleArchivedCandidates.length}</strong>
          </div>
          {visibleArchivedCandidates.length === 0 ? (
            <p className="application-lane-empty">No archived applications</p>
          ) : (
            <div className="application-archived-list">
              {visibleArchivedCandidates.map((opportunity) => (
                <article
                  className="application-card application-card-archived"
                  key={opportunityIdentity(opportunity)}
                  data-application-id={opportunity.application_id ?? undefined}
                  data-posting-id={opportunity.posting_id}
                >
                  <ApplicationSummaryButton item={opportunity} onOpen={() => openWorkspace(opportunity.posting_id)} />
                  <div className="application-card-links">
                    {opportunity.source_url && <a href={opportunity.source_url} target="_blank" rel="noreferrer">Source job</a>}
                    <a href={`${apiBase}/api/opportunities/${opportunity.posting_id}/preparation-pack`} download>Download prep pack</a>
                    <button
                      type="button"
                      className="secondary application-card-archive"
                      disabled={busy}
                      onClick={() => void restoreCard(opportunity)}
                    >
                      Restore card
                    </button>
                    <button
                      type="button"
                      className="danger application-card-delete"
                      disabled={busy}
                      onClick={() => void deleteCardPermanently(opportunity)}
                    >
                      Delete permanently
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {closingItem && (
        <div
          className="application-close-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target && !busy) setClosingPostingId(null);
          }}
        >
          <section
            className="application-close-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="application-close-title"
          >
            <div>
              <p className="eyebrow">Final outcome</p>
              <h3 id="application-close-title">Close {closingItem.title || "application"}</h3>
              <p>{[closingItem.company, closingItem.location].filter(Boolean).join(" · ")}</p>
              <p className="application-close-current-stage">Current stage: {label(closingItem.application_status)}</p>
            </div>
            {error && <p className="error application-close-error" role="alert">{error}</p>}
            <label>
              <span>Final outcome</span>
              <select
                aria-label={`Close ${closingItem.title || "untitled opportunity"} with outcome`}
                value={closeOutcome}
                disabled={busy}
                onChange={(event) => setCloseOutcome(event.target.value)}
              >
                {closeOutcomesFor(closingItem).map((outcome) => (
                  <option key={outcome.value} value={outcome.value}>{outcome.label}</option>
                ))}
              </select>
            </label>
            <div className="application-close-actions">
              <button type="button" className="danger" disabled={busy} onClick={() => void closeApplication(closingItem)}>
                {busy ? "Closing…" : "Confirm close"}
              </button>
              <button type="button" className="secondary" disabled={busy} onClick={() => setClosingPostingId(null)}>
                Cancel
              </button>
            </div>
          </section>
        </div>
      )}

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
              <div className="application-detail-header-actions">
                {selected.application_status === "archived" && (
                  <>
                    <button type="button" className="secondary" disabled={busy} onClick={() => void restoreCard(selected)}>
                      Restore application
                    </button>
                    <button type="button" className="danger" disabled={busy} onClick={() => void deleteCardPermanently(selected)}>
                      Delete permanently
                    </button>
                  </>
                )}
                <button type="button" className="secondary" onClick={() => setSelectedPostingId(null)}>
                  Close
                </button>
              </div>
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
              {error && <p className="error application-workspace-error" role="alert">{error}</p>}
              {selected.application_status === "archived" && activeTab === "overview" && (
                <ArchivedOverview detail={applicationDetail} loading={detailLoading} />
              )}
              {selected.application_status !== "archived" && activeTab === "overview" && (
                <ApplicationWorkflow
                  apiBase={apiBase}
                  postingId={selected.posting_id}
                  title={selected.title || "Untitled opportunity"}
                  reviewDecision={selected.review_decision}
                  applicationId={selected.application_id}
                  applicationStatus={activeApplicationStatus(selected.application_status)}
                  disabled={busy}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "tasks" && (
                <ApplicationTasks
                  apiBase={apiBase}
                  applicationId={selected.application_id}
                  readOnly={selected.application_status === "archived"}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "interviews" && (
                <ApplicationInterviews
                  apiBase={apiBase}
                  applicationId={selected.application_id}
                  readOnly={selected.application_status === "archived"}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "contacts" && (
                <ApplicationContacts
                  apiBase={apiBase}
                  applicationId={selected.application_id}
                  readOnly={selected.application_status === "archived"}
                  onChanged={refreshAfterChange}
                  onError={setError}
                />
              )}
              {activeTab === "documents" && (
                <ApplicationDocuments
                  apiBase={apiBase}
                  applicationId={selected.application_id}
                  readOnly={selected.application_status === "archived"}
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
