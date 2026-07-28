import { useCallback, useEffect, useRef, useState } from "react";

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
  startRequestKey?: number;
};

export function ProfessionalCaptureRuns({
  apiBase,
  active,
  planRefreshKey,
  startRequestKey = 0,
}: Props) {
  const [runs, setRuns] = useState<ProfessionalCaptureRun[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const [deletePhrase, setDeletePhrase] = useState("");
  const [error, setError] = useState("");
  const ledgerRef = useRef<HTMLElement | null>(null);
  const previousStartRequestKey = useRef(startRequestKey);

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

  useEffect(() => {
    if (startRequestKey === previousStartRequestKey.current) return;
    previousStartRequestKey.current = startRequestKey;
    if (active) void startNewCapture();
  }, [active, startRequestKey]);

  function replaceRun(changed: ProfessionalCaptureRun) {
    setRuns((current) => current.map((run) => (run.id === changed.id ? changed : run)));
  }

  async function authorizeAndStart(run: ProfessionalCaptureRun): Promise<ProfessionalCaptureRun> {
    let ready = run;
    if (ready.status === "planned") {
      const authorization = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${ready.id}/authorize`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            confirmation_phrase: AUTHORIZATION_PHRASE,
            user_present: true,
          }),
        },
      );
      if (!authorization.ok) {
        const payload = (await authorization.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The capture could not be authorized.");
      }
      ready = (await authorization.json()) as ProfessionalCaptureRun;
    }

    const response = await fetch(
      `${apiBase}/api/professional-intelligence/capture-runs/${ready.id}/start`,
      { method: "POST" },
    );
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(payload?.detail || "The supervised capture could not start.");
    }
    return (await response.json()) as ProfessionalCaptureRun;
  }

  async function startNewCapture() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("The supervised capture could not be prepared.");
      const created = (await response.json()) as ProfessionalCaptureRun;
      setRuns((current) => [created, ...current]);
      const completed = await authorizeAndStart(created);
      replaceRun(completed);
      ledgerRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture failed.");
      await loadRuns();
    } finally {
      setBusy(false);
    }
  }

  async function resumeRun(run: ProfessionalCaptureRun) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      replaceRun(await authorizeAndStart(run));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture failed.");
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
    <section
      id="professional-run-ledger"
      ref={ledgerRef}
      className="panel professional-run-ledger"
      aria-labelledby="professional-run-ledger-heading"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Capture operations</p>
          <h2 id="professional-run-ledger-heading">Capture history</h2>
          <p>Review completed captures or remove a bad batch.</p>
        </div>
        <button
          type="button"
          className="secondary"
          disabled={busy || !active}
          onClick={() => void startNewCapture()}
        >
          {busy ? "Capturing…" : "Start another capture"}
        </button>
      </div>
      <p className="professional-ledger-note">
        Current plan revision: {planRefreshKey}. The click that starts a capture records user presence locally.
      </p>
      {error && <p className="error" role="alert">{error}</p>}
      {loading && active && <p role="status">Loading capture history…</p>}
      {error && !loaded && <button type="button" className="secondary" disabled={loading} onClick={() => void loadRuns()}>Retry capture history</button>}
      {loaded && runs.length === 0 && <p>No captures yet. Use “Start capture” at the top of this workspace.</p>}
      {runs.length > 0 && (
        <div className="professional-run-list">
          {runs.map((run) => (
            <article className="professional-run-card" key={run.id}>
              <div>
                <strong>{run.status.replaceAll("_", " ")}</strong>
                <span>{new Date(run.requested_at).toLocaleString()}</span>
              </div>
              <p>{run.planned_sources.length} sources · {run.artifact_count} artifacts</p>
              <code>{run.id}</code>
              {(run.status === "planned" || run.status === "authorized" || run.status === "expired") && (
                <button type="button" disabled={busy} onClick={() => void resumeRun(run)}>
                  Start capture
                </button>
              )}
              {run.status === "running" && (
                <button type="button" className="secondary" disabled={busy} onClick={() => void cancelRun(run.id)}>
                  Request cancellation
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
