import { useCallback, useEffect, useState } from "react";

import type { ProfessionalIntelligenceSource } from "./ProfessionalIntelligence";

const CONFIRMATION_PHRASE = "I UNDERSTAND THIS WILL OPEN LINKEDIN";

type ProfessionalCaptureRun = {
  id: string;
  mode: "preview_only";
  status: "planned" | "authorized" | "expired" | "cancelled";
  planned_sources: ProfessionalIntelligenceSource[];
  safety_constraints: string[];
  requested_at: string;
  authorized_at: string | null;
  authorization_expires_at: string | null;
  user_present_confirmed: boolean;
  started_at: string | null;
  completed_at: string | null;
  stop_reason: string;
  artifact_count: number;
};

type Props = {
  apiBase: string;
  active: boolean;
  planRefreshKey: number;
};

export function ProfessionalCaptureRuns({ apiBase, active, planRefreshKey }: Props) {
  const [runs, setRuns] = useState<ProfessionalCaptureRun[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [authorizingRunId, setAuthorizingRunId] = useState<string | null>(null);
  const [confirmationPhrase, setConfirmationPhrase] = useState("");
  const [userPresent, setUserPresent] = useState(false);
  const [error, setError] = useState("");

  const loadRuns = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`);
    if (!response.ok) throw new Error("Unable to load the Professional Intelligence run ledger.");
    setRuns((await response.json()) as ProfessionalCaptureRun[]);
    setLoaded(true);
  }, [apiBase]);

  useEffect(() => {
    if (!active || loaded) return;
    void loadRuns().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Run ledger failed.");
    });
  }, [active, loadRuns, loaded]);

  function replaceRun(changed: ProfessionalCaptureRun) {
    setRuns((current) => current.map((run) => (run.id === changed.id ? changed : run)));
  }

  async function recordPreviewRun() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("The preview run could not be recorded.");
      const created = (await response.json()) as ProfessionalCaptureRun;
      setRuns((current) => [created, ...current]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preview run failed.");
    } finally {
      setBusy(false);
    }
  }

  async function authorizeRun(runId: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/authorize`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmation_phrase: confirmationPhrase, user_present: userPresent }),
        },
      );
      if (!response.ok) throw new Error("The preview run could not be authorized.");
      replaceRun((await response.json()) as ProfessionalCaptureRun);
      setAuthorizingRunId(null);
      setConfirmationPhrase("");
      setUserPresent(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preview authorization failed.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelRun(runId: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/cancel`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("The preview run could not be cancelled.");
      replaceRun((await response.json()) as ProfessionalCaptureRun);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preview run cancellation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel professional-run-ledger" aria-labelledby="professional-run-ledger-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Audit ledger</p>
          <h2 id="professional-run-ledger-heading">Preview run history</h2>
          <p>Record and explicitly authorize the current plan. Authorization expires after 15 minutes and still does not launch a browser.</p>
        </div>
        <button type="button" disabled={busy || !active} onClick={() => void recordPreviewRun()}>
          {busy ? "Saving…" : "Record preview run"}
        </button>
      </div>
      <p className="professional-ledger-note">
        Current plan revision: {planRefreshKey}. Browser execution and evidence writing remain unavailable.
      </p>
      {error && <p className="error" role="alert">{error}</p>}
      {!loaded && active && <p role="status">Loading preview run history…</p>}
      {loaded && runs.length === 0 && <p>No preview runs recorded.</p>}
      {runs.length > 0 && (
        <div className="professional-run-list">
          {runs.map((run) => (
            <article className="professional-run-card" key={run.id}>
              <div>
                <strong>{run.status}</strong>
                <span>{new Date(run.requested_at).toLocaleString()}</span>
              </div>
              <p>{run.planned_sources.length} planned sources · {run.artifact_count} artifacts</p>
              <code>{run.id}</code>
              {run.authorization_expires_at && (
                <p>Authorization expires: {new Date(run.authorization_expires_at).toLocaleString()}</p>
              )}
              {run.status === "planned" && authorizingRunId !== run.id && (
                <button type="button" className="secondary" disabled={busy} onClick={() => setAuthorizingRunId(run.id)}>
                  Authorize supervised run
                </button>
              )}
              {run.status === "planned" && authorizingRunId === run.id && (
                <div className="professional-run-authorization">
                  <label>
                    Type the exact phrase
                    <input
                      aria-label={`Authorization phrase for ${run.id}`}
                      value={confirmationPhrase}
                      onChange={(event) => setConfirmationPhrase(event.target.value)}
                      placeholder={CONFIRMATION_PHRASE}
                    />
                  </label>
                  <label className="professional-source-checkbox">
                    <input
                      type="checkbox"
                      aria-label={`User present for ${run.id}`}
                      checked={userPresent}
                      onChange={(event) => setUserPresent(event.target.checked)}
                    />
                    I am present and will supervise this run.
                  </label>
                  <button
                    type="button"
                    disabled={busy || confirmationPhrase !== CONFIRMATION_PHRASE || !userPresent}
                    onClick={() => void authorizeRun(run.id)}
                  >
                    Confirm authorization
                  </button>
                </div>
              )}
              {(run.status === "planned" || run.status === "authorized") && (
                <button type="button" className="secondary" disabled={busy} onClick={() => void cancelRun(run.id)}>
                  Cancel preview
                </button>
              )}
              {run.stop_reason && <p>{run.stop_reason.replaceAll("_", " ")}</p>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
