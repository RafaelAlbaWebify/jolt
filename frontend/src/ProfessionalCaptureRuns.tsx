import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ProfessionalEvidenceReview } from "./ProfessionalEvidenceReview";
import type { ProfessionalIntelligenceSource } from "./ProfessionalIntelligence";

const AUTHORIZATION_PHRASE = "I UNDERSTAND THIS WILL OPEN LINKEDIN";
const DELETE_PHRASE = "DELETE CAPTURE RUN";
const CAPTURE_POLL_MS = 2_000;

export type ProfessionalCaptureOptions = {
  max_sources: number;
  max_scroll_batches: number;
  max_items_per_source: number;
  timeout_seconds: number;
  stop_on_failure: boolean;
};

type ProfessionalSourceProgress = {
  source_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  completeness_status: string;
  detail: string;
};

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
  capture_options: ProfessionalCaptureOptions;
  requested_at: string;
  authorized_at: string | null;
  authorization_expires_at: string | null;
  user_present_confirmed: boolean;
  started_at: string | null;
  completed_at: string | null;
  stop_reason: string;
  artifact_count: number;
  source_progress: ProfessionalSourceProgress[];
  completed_source_count: number;
  total_source_count: number;
  current_source_id: string;
  cancel_requested: boolean;
  progress_updated_at: string | null;
};

type Props = {
  apiBase: string;
  active: boolean;
  planRefreshKey: number;
  captureOptions: ProfessionalCaptureOptions;
  startRequestKey?: number;
};

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

function sourceLabel(run: ProfessionalCaptureRun, sourceId: string) {
  return run.planned_sources.find((source) => source.source_id === sourceId)?.label || sourceId;
}

function progressSummary(run: ProfessionalCaptureRun) {
  const total = run.total_source_count || run.planned_sources.length || run.source_progress.length;
  return `${run.completed_source_count}/${total} sources completed`;
}

function formatDate(value: string | null) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

function shouldPollRun(run: ProfessionalCaptureRun) {
  return run.status === "authorized" || run.status === "running";
}

function isManualBrowserReady(run: ProfessionalCaptureRun) {
  return run.status === "authorized" && run.stop_reason.includes("manual_browser_ready");
}

export function ProfessionalCaptureRuns({
  apiBase,
  active,
  planRefreshKey,
  captureOptions,
  startRequestKey = 0,
}: Props) {
  const [runs, setRuns] = useState<ProfessionalCaptureRun[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [activeSessionRunId, setActiveSessionRunId] = useState<string | null>(null);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const [deletePhrases, setDeletePhrases] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const ledgerRef = useRef<HTMLElement | null>(null);
  const previousStartRequestKey = useRef(startRequestKey);

  const runningRun = useMemo(() => runs.find((run) => run.status === "running") || null, [runs]);
  const activePreparedRun = useMemo(
    () =>
      runs.find((run) => run.id === activeSessionRunId && isManualBrowserReady(run)) ||
      runs.find(isManualBrowserReady) ||
      null,
    [activeSessionRunId, runs],
  );

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
    if (active) void prepareNewCaptureSession();
  }, [active, startRequestKey]);

  useEffect(() => {
    if (!active || !runs.some(shouldPollRun)) return;
    const interval = window.setInterval(() => {
      void loadRuns();
    }, CAPTURE_POLL_MS);
    return () => window.clearInterval(interval);
  }, [active, loadRuns, runs]);

  function replaceRun(changed: ProfessionalCaptureRun) {
    setRuns((current) => current.map((run) => (run.id === changed.id ? changed : run)));
  }

  async function authorizeRun(run: ProfessionalCaptureRun): Promise<ProfessionalCaptureRun> {
    if (run.status !== "planned" && run.status !== "expired") return run;
    const authorization = await fetch(
      `${apiBase}/api/professional-intelligence/capture-runs/${run.id}/authorize`,
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
    const ready = (await authorization.json()) as ProfessionalCaptureRun;
    replaceRun(ready);
    return ready;
  }

  async function prepareBrowser(run: ProfessionalCaptureRun): Promise<ProfessionalCaptureRun> {
    const ready = await authorizeRun(run);
    const response = await fetch(
      `${apiBase}/api/professional-intelligence/capture-runs/${ready.id}/prepare-browser`,
      { method: "POST" },
    );
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(payload?.detail || "The manual Chromium browser could not be prepared.");
    }
    const prepared = (await response.json()) as ProfessionalCaptureRun;
    setActiveSessionRunId(prepared.id);
    return prepared;
  }

  async function captureCurrentPage(run: ProfessionalCaptureRun) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${run.id}/capture-current-page`,
        { method: "POST" },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The current Chromium page could not be captured.");
      }
      const queued = (await response.json()) as ProfessionalCaptureRun;
      replaceRun(queued);
      setActiveSessionRunId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Current-page capture failed.");
      await loadRuns();
    } finally {
      setBusy(false);
    }
  }

  async function prepareNewCaptureSession() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ options: captureOptions }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The supervised capture could not be prepared.");
      }
      const created = (await response.json()) as ProfessionalCaptureRun;
      setRuns((current) => [created, ...current]);
      const prepared = await prepareBrowser(created);
      replaceRun(prepared);
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
      replaceRun(await prepareBrowser(run));
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
      if (runId === activeSessionRunId) setActiveSessionRunId(null);
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
          body: JSON.stringify({ confirmation_phrase: deletePhrases[runId] || "" }),
        },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The capture run could not be deleted.");
      }
      setRuns((current) => current.filter((run) => run.id !== runId));
      if (runId === activeSessionRunId) setActiveSessionRunId(null);
      setDeletingRunId(null);
      setDeletePhrases((current) => {
        const next = { ...current };
        delete next[runId];
        return next;
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture deletion failed.");
    } finally {
      setBusy(false);
    }
  }

  function updateDeletePhrase(runId: string, value: string) {
    setDeletePhrases((current) => ({ ...current, [runId]: value }));
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
          <h2 id="professional-run-ledger-heading">Capture current LinkedIn page</h2>
          <p>Open Chromium once, prepare LinkedIn manually, then capture exactly the visible page.</p>
        </div>
      </div>

      <div className="professional-manual-capture-panel">
        <h3>Current capture session</h3>
        <p>
          Prepare the exact LinkedIn profile or job-search results page in the opened browser. When the page is ready,
          come back here and capture the current Chromium page.
        </p>
        <div className="professional-source-editor-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy || !active || Boolean(activePreparedRun) || Boolean(runningRun)}
            onClick={() => void prepareNewCaptureSession()}
          >
            {busy ? "Preparing…" : activePreparedRun ? "Chromium is ready" : "Open Chromium to prepare capture"}
          </button>
          <button
            type="button"
            disabled={busy || !activePreparedRun}
            onClick={() => activePreparedRun && void captureCurrentPage(activePreparedRun)}
          >
            Capture current Chromium page
          </button>
          {runningRun && (
            <button type="button" className="secondary" disabled={busy} onClick={() => void cancelRun(runningRun.id)}>
              Request cancellation
            </button>
          )}
        </div>
        {activePreparedRun && (
          <p role="status">
            Chromium is open. Sign in to LinkedIn if needed, navigate to the exact page/search results you want, then
            capture this current page.
          </p>
        )}
      </div>

      <p className="professional-ledger-note">
        Current plan revision: {planRefreshKey}. History below is read-only except review, cancel, and delete actions.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading && active && <p role="status">Loading capture history…</p>}
      {error && !loaded && (
        <button type="button" className="secondary" disabled={loading} onClick={() => void loadRuns()}>
          Retry capture history
        </button>
      )}
      {loaded && runs.length === 0 && <p>No captures yet. Use “Open Chromium to prepare capture”.</p>}
      {runs.length > 0 && (
        <div className="professional-run-list">
          {runs.map((run) => {
            const deletePhrase = deletePhrases[run.id] || "";
            return (
              <article className="professional-run-card" key={run.id}>
                <div>
                  <strong>{humanize(run.status)}</strong>
                  <span>{new Date(run.requested_at).toLocaleString()}</span>
                </div>
                <p>{run.planned_sources.length} sources · {run.artifact_count} artifacts</p>
                <p>
                  Limits: {run.capture_options.max_sources} sources · {run.capture_options.max_scroll_batches} scroll
                  batches · {run.capture_options.max_items_per_source} items/source · {run.capture_options.timeout_seconds}s
                  timeout
                </p>
                <p>
                  Progress: {progressSummary(run)}
                  {run.current_source_id ? ` · Current: ${sourceLabel(run, run.current_source_id)}` : ""}
                  {run.cancel_requested ? " · cancellation requested" : ""}
                </p>
                {isManualBrowserReady(run) && (
                  <p>Prepared batch. Use the top Current capture session panel to capture the newest prepared page.</p>
                )}
                {run.progress_updated_at && <p>Progress updated: {formatDate(run.progress_updated_at)}</p>}
                {run.source_progress.length > 0 && (
                  <details
                    className="professional-source-progress"
                    open={run.status === "running" || run.status === "completed_with_gaps" || run.status === "failed"}
                  >
                    <summary>Source progress and failure details</summary>
                    <ol>
                      {run.source_progress.map((source) => (
                        <li key={source.source_id}>
                          <strong>{sourceLabel(run, source.source_id)}</strong>: {humanize(source.status)}
                          {source.completeness_status ? ` · ${humanize(source.completeness_status)}` : ""}
                          {source.started_at ? ` · started ${formatDate(source.started_at)}` : ""}
                          {source.completed_at ? ` · completed ${formatDate(source.completed_at)}` : ""}
                          {source.detail && <p>{source.detail}</p>}
                        </li>
                      ))}
                    </ol>
                  </details>
                )}
                <code>{run.id}</code>
                {(run.status === "planned" || run.status === "expired") && (
                  <button type="button" disabled={busy || Boolean(activePreparedRun)} onClick={() => void resumeRun(run)}>
                    Open Chromium to prepare this run
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
                {run.stop_reason && <p>{humanize(run.stop_reason)}</p>}
                {run.status !== "running" && deletingRunId !== run.id && (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => {
                      setDeletingRunId(run.id);
                      updateDeletePhrase(run.id, "");
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
                        onChange={(event) => updateDeletePhrase(run.id, event.target.value)}
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
                          updateDeletePhrase(run.id, "");
                        }}
                      >
                        Keep batch
                      </button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
