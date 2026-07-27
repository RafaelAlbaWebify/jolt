import { useCallback, useEffect, useState } from "react";

import { ProfessionalEvidenceReview } from "./ProfessionalEvidenceReview";
import type { ProfessionalIntelligenceSource } from "./ProfessionalIntelligence";

const AUTHORIZATION_PHRASE = "I UNDERSTAND THIS WILL OPEN LINKEDIN";
const DELETE_PHRASE = "DELETE CAPTURE RUN";

type ProfessionalCaptureRun = {
  id: string;
  mode: "preview_only" | "supervised_read_only";
  status:
    | "planned"
    | "authorized"
    | "expired"
    | "running"
    | "completed"
    | "completed_with_gaps"
    | "failed"
    | "cancelled"
    | "interrupted";
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
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [authorizingRunId, setAuthorizingRunId] = useState<string | null>(null);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const [confirmationPhrase, setConfirmationPhrase] = useState("");
  const [deletePhrase, setDeletePhrase] = useState("");
  const [userPresent, setUserPresent] = useState(false);
  const [error, setError] = useState("");

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`);
      if (!response.ok) throw new Error("Unable to load the Professional Intelligence run ledger.");
      setRuns((await response.json()) as ProfessionalCaptureRun[]);
      setLoaded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Run ledger failed.");
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (!active || loaded) return;
    void loadRuns();
  }, [active, loadRuns, loaded]);

  function replaceRun(changed: ProfessionalCaptureRun) {
    setRuns((current) => current.map((run) => (run.id === changed.id ? changed : run)));
  }

  async function startNewCapture() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("The supervised capture could not be prepared.");
      const created = (await response.json()) as ProfessionalCaptureRun;
      setRuns((current) => [created, ...current]);
      setAuthorizingRunId(created.id);
      setConfirmationPhrase("");
      setUserPresent(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture preparation failed.");
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
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The capture could not be authorized.");
      }
      replaceRun((await response.json()) as ProfessionalCaptureRun);
      setAuthorizingRunId(null);
      setConfirmationPhrase("");
      setUserPresent(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture authorization failed.");
    } finally {
      setBusy(false);
    }
  }

  async function startRun(runId: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/start`,
        { method: "POST" },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The supervised capture could not start.");
      }
      replaceRun((await response.json()) as ProfessionalCaptureRun);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Supervised capture failed.");
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
      if (!response.ok) throw new Error("The capture could not be cancelled.");
      replaceRun((await response.json()) as ProfessionalCaptureRun);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture cancellation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteRun(runId: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/delete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmation_phrase: deletePhrase }),
        },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The capture run could not be deleted.");
      }
      setRuns((current) => current.filter((run) => run.id !== runId));
      setDeletingRunId(null);
      setDeletePhrase("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture deletion failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel professional-run-ledger" aria-labelledby="professional-run-ledger-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Capture operations</p>
          <h2 id="professional-run-ledger-heading">Supervised captures</h2>
          <p>Start a new capture, complete the required safety confirmation, and manage recent capture batches from one place.</p>
        </div>
        <div className="professional-primary-capture-action">
          <button type="button" disabled={busy || !active} onClick={() => void startNewCapture()}>
            {busy ? "Working…" : "Start new supervised capture"}
          </button>
          <p>This prepares a new run and immediately opens its authorization step.</p>
        </div>
      </div>
      <p className="professional-ledger-note">
        Current plan revision: {planRefreshKey}. No credentials, cookies, tokens, or browser storage are persisted.
      </p>
      {error && <p className="error" role="alert">{error}</p>}
      {loading && active && <p role="status">Loading supervised capture history…</p>}
      {error && !loaded && <button type="button" className="secondary" disabled={loading} onClick={() => void loadRuns()}>Retry capture history</button>}
      {loaded && runs.length === 0 && <p>No capture runs recorded yet. Use “Start new supervised capture” above.</p>}
      {runs.length > 0 && (
        <div className="professional-run-list">
          {runs.map((run) => (
            <article className="professional-run-card" key={run.id}>
              <div>
                <strong>{run.status.replaceAll("_", " ")}</strong>
                <span>{new Date(run.requested_at).toLocaleString()}</span>
              </div>
              <p>{run.planned_sources.length} planned sources · {run.artifact_count} artifacts</p>
              <code>{run.id}</code>
              {run.authorization_expires_at && (
                <p>Authorization expires: {new Date(run.authorization_expires_at).toLocaleString()}</p>
              )}
              {run.status === "planned" && authorizingRunId !== run.id && (
                <button type="button" className="secondary" disabled={busy} onClick={() => setAuthorizingRunId(run.id)}>
                  Continue authorization
                </button>
              )}
              {run.status === "planned" && authorizingRunId === run.id && (
                <div className="professional-run-authorization">
                  <p>This visible capture opens only the approved source URLs. Confirm that you are present before continuing.</p>
                  <label>
                    Type the exact phrase
                    <input
                      aria-label={`Authorization phrase for ${run.id}`}
                      value={confirmationPhrase}
                      onChange={(event) => setConfirmationPhrase(event.target.value)}
                      placeholder={AUTHORIZATION_PHRASE}
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
                    disabled={busy || confirmationPhrase !== AUTHORIZATION_PHRASE || !userPresent}
                    onClick={() => void authorizeRun(run.id)}
                  >
                    Authorize capture
                  </button>
                </div>
              )}
              {run.status === "authorized" && (
                <div className="professional-run-start">
                  <p>Authorization is complete. A visible Chromium window will open.</p>
                  <button type="button" disabled={busy} onClick={() => void startRun(run.id)}>
                    Start capture now
                  </button>
                </div>
              )}
              {(run.status === "planned" || run.status === "authorized" || run.status === "running") && (
                <button type="button" className="secondary" disabled={busy} onClick={() => void cancelRun(run.id)}>
                  {run.status === "running" ? "Request cancellation" : "Cancel run"}
                </button>
              )}
              {(run.status === "completed" || run.status === "completed_with_gaps") && (
                <ProfessionalEvidenceReview apiBase={apiBase} runId={run.id} />
              )}
              {run.stop_reason && <p>{run.stop_reason.replaceAll("_", " ")}</p>}
              {run.status !== "running" && deletingRunId !== run.id && (
                <button
                  type="button"
                  className="danger"
                  disabled={busy}
                  onClick={() => {
                    setDeletingRunId(run.id);
                    setDeletePhrase("");
                  }}
                >
                  Delete this capture batch
                </button>
              )}
              {deletingRunId === run.id && (
                <div className="professional-delete-confirmation">
                  <strong>Delete this capture batch?</strong>
                  <p>This removes only this run and its governed local evidence. It cannot be undone.</p>
                  <label>
                    Type {DELETE_PHRASE}
                    <input
                      aria-label={`Deletion phrase for ${run.id}`}
                      value={deletePhrase}
                      onChange={(event) => setDeletePhrase(event.target.value)}
                    />
                  </label>
                  <div className="professional-source-editor-actions">
                    <button
                      type="button"
                      className="danger"
                      disabled={busy || deletePhrase !== DELETE_PHRASE}
                      onClick={() => void deleteRun(run.id)}
                    >
                      Permanently delete batch
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        setDeletingRunId(null);
                        setDeletePhrase("");
                      }}
                    >
                      Keep batch
                    </button>
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
