import { useCallback, useEffect, useState } from "react";

import { ApplicationWorkflow } from "./ApplicationWorkflow";

type Opportunity = {
  posting_id: string;
  title: string;
  company: string;
  location: string;
  review_decision: string | null;
  application_id?: string | null;
  application_status?: string | null;
  outcome_type?: string | null;
};

type Props = {
  apiBase: string;
};

export function ApplicationDashboard({ apiBase }: Props) {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/opportunities`);
    if (!response.ok) throw new Error("Unable to load application opportunities.");
    setOpportunities((await response.json()) as Opportunity[]);
  }, [apiBase]);

  useEffect(() => {
    refresh().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Application dashboard failed.");
    });
  }, [refresh]);

  const candidates = opportunities.filter(
    (item) => item.review_decision === "pursue" || Boolean(item.application_id),
  );

  return (
    <section className="panel" aria-labelledby="application-dashboard-heading">
      <div className="section-heading">
        <div>
          <h2 id="application-dashboard-heading">Application management</h2>
          <p>Create local application records, advance stages manually, preserve event history, and record final outcomes.</p>
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

      <p>This workbench records evidence only. It never submits an external application or contacts a recruiter.</p>
      {error && <p className="error" role="alert">{error}</p>}

      {candidates.length === 0 ? (
        <p>No pursued or active applications are available.</p>
      ) : (
        <div className="queue opportunity-grid">
          {candidates.map((opportunity) => (
            <article className="opportunity-card" key={opportunity.posting_id}>
              <div className="opportunity-main">
                <h3>{opportunity.title || "Untitled opportunity"}</h3>
                <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                <ApplicationWorkflow
                  apiBase={apiBase}
                  postingId={opportunity.posting_id}
                  title={opportunity.title || "Untitled opportunity"}
                  reviewDecision={opportunity.review_decision}
                  applicationId={opportunity.application_id}
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
              </div>
              <div className="queue-status">
                <strong>{opportunity.outcome_type ?? opportunity.application_status ?? "ready to start"}</strong>
                <span>application record</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
