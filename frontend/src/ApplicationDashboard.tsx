import { useCallback, useEffect, useMemo, useState } from "react";

import { ApplicationWorkflow } from "./ApplicationWorkflow";
import type { ApplicationStatus } from "./ApplicationWorkflow";

type Opportunity = {
  posting_id: string;
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
};

type ApplicationFilter = "all" | "ready" | "active" | "closed";

function statusLabel(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "ready to start";
}

export function ApplicationDashboard({ apiBase }: Props) {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [filter, setFilter] = useState<ApplicationFilter>("all");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/opportunity-index`);
    if (!response.ok) throw new Error("Unable to load application opportunities.");
    setOpportunities((await response.json()) as Opportunity[]);
  }, [apiBase]);

  useEffect(() => {
    refresh().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Application dashboard failed.");
    });
  }, [refresh]);

  const candidates = useMemo(
    () => opportunities.filter(
      (item) => item.review_decision === "pursue" || Boolean(item.application_id),
    ),
    [opportunities],
  );

  const counts = useMemo(() => ({
    all: candidates.length,
    ready: candidates.filter((item) => !item.application_id).length,
    active: candidates.filter((item) => item.application_id && !item.outcome_type).length,
    closed: candidates.filter((item) => Boolean(item.outcome_type)).length,
  }), [candidates]);

  const visibleCandidates = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return candidates.filter((item) => {
      if (filter === "ready" && item.application_id) return false;
      if (filter === "active" && (!item.application_id || item.outcome_type)) return false;
      if (filter === "closed" && !item.outcome_type) return false;
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
          <p>Move pursued roles from preparation through interviews and outcomes without losing the evidence trail.</p>
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
        <div><strong>{counts.ready}</strong><span>Ready to start</span></div>
        <div><strong>{counts.active}</strong><span>Active</span></div>
        <div><strong>{counts.closed}</strong><span>Closed</span></div>
        <div><strong>{counts.all}</strong><span>Total tracked</span></div>
      </div>

      <div className="application-controls">
        <div className="queue-filters" aria-label="Filter applications">
          {(["all", "ready", "active", "closed"] as ApplicationFilter[]).map((item) => (
            <button
              type="button"
              className={filter === item ? "filter-active" : "secondary"}
              onClick={() => setFilter(item)}
              key={item}
            >
              {item} ({counts[item]})
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

      <p className="application-boundary">JOLT records workflow evidence only. It never submits externally or contacts a recruiter.</p>
      {error && <p className="error" role="alert">{error}</p>}

      {visibleCandidates.length === 0 ? (
        <div className="application-empty">
          <h3>No applications match this view</h3>
          <p>Change the filter or search, or mark an opportunity as pursue to prepare an application.</p>
        </div>
      ) : (
        <div className="application-list">
          {visibleCandidates.map((opportunity) => (
            <article className="application-row" key={opportunity.posting_id}>
              <div className="application-row-summary">
                <div>
                  <h3>{opportunity.title || "Untitled opportunity"}</h3>
                  <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                </div>
                <div className={`application-stage ${opportunity.outcome_type ? "application-stage-closed" : ""}`}>
                  <strong>{statusLabel(opportunity.outcome_type ?? opportunity.application_status)}</strong>
                  <span>{opportunity.application_id ? "application record" : "pursue decision"}</span>
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
