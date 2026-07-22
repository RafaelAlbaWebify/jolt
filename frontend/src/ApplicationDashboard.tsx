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

type Props = {
  apiBase: string;
  active: boolean;
};

type ApplicationFilter = "preparation" | "attention" | "active" | "closed" | "all";

const ATTENTION_STATUSES = new Set<ApplicationStatus>(["submitted", "acknowledged", "offer"]);
const ACTIVE_STATUSES = new Set<ApplicationStatus>([
  "recruiter_screen",
  "technical_interview",
  "hiring_manager_interview",
  "final_interview",
]);

function statusLabel(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "ready to prepare";
}

function bucketFor(item: Opportunity): Exclude<ApplicationFilter, "all"> {
  if (item.outcome_type) return "closed";
  if (!item.application_id || item.application_status === "preparing") return "preparation";
  if (item.application_status && ATTENTION_STATUSES.has(item.application_status)) return "attention";
  return "active";
}

function nextAction(item: Opportunity) {
  if (!item.application_id) return "Create a preparation record";
  switch (item.application_status) {
    case "preparing": return "Finish documents and record external submission";
    case "submitted": return "Watch for acknowledgement or recruiter contact";
    case "acknowledged": return "Wait for recruiter contact";
    case "recruiter_screen": return "Prepare for the next interview";
    case "technical_interview": return "Record the result or next interview";
    case "hiring_manager_interview": return "Record the result, final interview, or offer";
    case "final_interview": return "Record the final decision or offer";
    case "offer": return "Accept or decline the offer";
    default: return item.outcome_type ? "No action required" : "Review application status";
  }
}

export function ApplicationDashboard({ apiBase, active }: Props) {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [filter, setFilter] = useState<ApplicationFilter>("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/application-index`);
    if (!response.ok) throw new Error("Unable to load application opportunities.");
    setOpportunities((await response.json()) as Opportunity[]);
  }, [apiBase]);

  useEffect(() => {
    if (!active) return;
    refresh().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Application dashboard failed.");
    });
  }, [active, refresh]);

  const candidates = useMemo(
    () => opportunities.filter((item) => item.review_decision === "pursue" || Boolean(item.application_id)),
    [opportunities],
  );

  const counts = useMemo(() => ({
    all: candidates.length,
    preparation: candidates.filter((item) => bucketFor(item) === "preparation").length,
    attention: candidates.filter((item) => bucketFor(item) === "attention").length,
    active: candidates.filter((item) => bucketFor(item) === "active").length,
    closed: candidates.filter((item) => bucketFor(item) === "closed").length,
  }), [candidates]);

  const visibleCandidates = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return candidates.filter((item) => {
      if (filter !== "all" && bucketFor(item) !== filter) return false;
      if (!normalizedQuery) return true;
      return [item.title, item.company, item.location, item.application_status, item.outcome_type]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery);
    });
  }, [candidates, filter, query]);

  return (
    <section className="panel application-workspace" aria-labelledby="application-dashboard-heading">
      <div className="section-heading application-workspace-heading">
        <div>
          <p className="eyebrow">Application pipeline</p>
          <h2 id="application-dashboard-heading">Application management</h2>
          <p>Prepare, submit externally, follow up, record interviews, and close outcomes.</p>
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

      <div className="application-metrics" aria-label="Application pipeline summary">
        <button type="button" onClick={() => setFilter("preparation")}><strong>{counts.preparation}</strong><span>Preparation</span></button>
        <button type="button" onClick={() => setFilter("attention")}><strong>{counts.attention}</strong><span>Action required</span></button>
        <button type="button" onClick={() => setFilter("active")}><strong>{counts.active}</strong><span>Interviews</span></button>
        <button type="button" onClick={() => setFilter("closed")}><strong>{counts.closed}</strong><span>Closed</span></button>
      </div>

      <div className="application-controls">
        <div className="queue-filters" aria-label="Filter applications">
          {(["attention", "preparation", "active", "closed", "all"] as ApplicationFilter[]).map((item) => (
            <button
              type="button"
              className={filter === item ? "filter-active" : "secondary"}
              onClick={() => setFilter(item)}
              key={item}
            >
              {item.replaceAll("_", " ")} ({counts[item]})
            </button>
          ))}
        </div>
        <label className="application-search">
          <span>Search applications</span>
          <input
            type="search"
            value={query}
            placeholder="Role, company, location, or stage"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>

      <p className="application-boundary">JOLT records and guides the workflow. External submission and recruiter contact remain under your control.</p>
      {error && <p className="error" role="alert">{error}</p>}

      {visibleCandidates.length === 0 ? (
        <div className="application-empty">
          <h3>No applications match this view</h3>
          <p>Change the filter or mark an opportunity as pursue to prepare an application.</p>
        </div>
      ) : (
        <div className="application-list">
          {visibleCandidates.map((opportunity) => (
            <article className="application-row" key={opportunity.posting_id}>
              <div className="application-row-summary">
                <div>
                  <h3>{opportunity.title || "Untitled opportunity"}</h3>
                  <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                  <div className="application-quick-links">
                    {opportunity.source_url && <a href={opportunity.source_url} target="_blank" rel="noreferrer">Open source job</a>}
                    <a href={`${apiBase}/api/opportunities/${opportunity.posting_id}/preparation-pack`} download>Preparation pack</a>
                  </div>
                </div>
                <div className={`application-stage ${opportunity.outcome_type ? "application-stage-closed" : ""}`}>
                  <strong>{statusLabel(opportunity.outcome_type ?? opportunity.application_status)}</strong>
                  <span>{nextAction(opportunity)}</span>
                </div>
              </div>
              <ApplicationWorkflow
                apiBase={apiBase}
                postingId={opportunity.posting_id}
                title={opportunity.title || "Untitled opportunity"}
                reviewDecision={opportunity.review_decision}
                applicationId={opportunity.application_id}
                applicationStatus={opportunity.application_status}
                disabled={busy}
                onChanged={async () => {
                  setBusy(true);
                  try {
                    await refresh();
                  } finally {
                    setBusy(false);
                  }
                }}
                onError={setError}
              />
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
