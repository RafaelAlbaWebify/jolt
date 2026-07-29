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

function runSourceLabel(run: ProfessionalCaptureRun) {
  const first = run.planned_sources[0];
  if (first?.label) return first.label;
  if (run.current_source_id) return sourceLabel(run, run.current_source_id);
  return "Prepared LinkedIn page";
}

function runSourceUrl(run: ProfessionalCaptureRun) {
  return run.planned_sources[0]?.url || "";
}

function progressSummary(run: ProfessionalCaptureRun) {
  const total = run.total_source_count || run.planned_sources.length || run.source_progress.length || 1;
  return `${run.completed_source_count}/${total} sources completed`;
}

function progressPercent(run: ProfessionalCaptureRun) {
  const total = run.total_source_count || run.planned_sources.length || run.source_progress.length || 1;
  return Math.max(0, Math.min(100, Math.round((run.completed_source_count / total) * 100)));
}

function formatDate(value: string | null) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

function shortRunId(value: string) {
  return value.length > 13 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

function shouldPollRun(run: ProfessionalCaptureRun) {
  return run.status === "authorized" || run.status === "running";
}

function isManualBrowserReady(run: ProfessionalCaptureRun) {
  return run.status === "authorized" && run.stop_reason.includes("manual_browser_ready");
}

function isTerminal(run: ProfessionalCaptureRun) {
  return ["completed", "completed_with_gaps", "failed", "cancelled", "interrupted"].includes(run.status);
}

function statusTone(status: ProfessionalCaptureRun["status"]) {
  if (status === "completed") return "success";
  if (status === "completed_with_gaps" || status === "authorized") return "warning";
  if (status === "failed" || status === "cancelled" || status === "interrupted" || status === "expired") return "danger";
  if (status === "running") return "info";
  return "neutral";
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
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [deleteModalRunId, setDeleteModalRunId] = useState<string | null>(null);
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
  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) || runs[0] || null,
    [runs, selectedRunId],
  );
  const deleteModalRun = useMemo(
    () => runs.find((run) => run.id === deleteModalRunId) || null,
    [deleteModalRunId, runs],
  );

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`);
      if (!response.ok) throw new Error("Unable to load the Professional Intelligence run ledger.");
      const loadedRuns = (await response.json()) as ProfessionalCaptureRun[];
      setRuns(loadedRuns);
      setLoaded(true);
      setSelectedRunId((current) => (current && loadedRuns.some((run) => run.id === current) ? current : loadedRuns[0]?.id || null));
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
    setSelectedRunId(changed.id);
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
    replaceRun(prepared);
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
      setSelectedRunId(created.id);
      await prepareBrowser(created);
      ledgerRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture failed.");
      await loadRuns();
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
      setSelectedRunId((current) => (current === runId ? null : current));
      setDeleteModalRunId(null);
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
      className="panel professional-run-ledger professional-workspace-redesign"
      aria-labelledby="professional-run-ledger-heading"
    >
      <div className="professional-redesign-header">
        <div>
          <p className="eyebrow">Capture operations</p>
          <h2 id="professional-run-ledger-heading">Professional</h2>
          <p>Supervised LinkedIn capture and evidence review.</p>
        </div>
        <button type="button" className="secondary" disabled={loading} onClick={() => void loadRuns()}>
          Refresh
        </button>
      </div>

      <ol className="professional-flow-strip" aria-label="Professional capture workflow">
        <li className={!activePreparedRun && !runningRun ? "is-active" : ""}>
          <span>1</span>
          <strong>Open Chromium</strong>
          <small>Launch the browser.</small>
        </li>
        <li className={activePreparedRun ? "is-active" : ""}>
          <span>2</span>
          <strong>Capture prepared page</strong>
          <small>Capture the current page.</small>
        </li>
        <li>
          <span>3</span>
          <strong>Review last evidence</strong>
          <small>Inspect the latest capture.</small>
        </li>
        <li className="is-danger">
          <span>4</span>
          <strong>Delete run</strong>
          <small>Safely delete only if needed.</small>
        </li>
      </ol>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading && active && <p role="status">Loading capture history…</p>}

      <div className="professional-top-grid">
        <section className="professional-dashboard-card professional-current-session-card">
          <div className="professional-card-heading">
            <h3>Current capture session</h3>
            <span className={`professional-status-pill ${activePreparedRun ? "success" : runningRun ? "info" : "neutral"}`}>
              {activePreparedRun ? "Chromium ready" : runningRun ? "Capture running" : "No active session"}
            </span>
          </div>
          <p>
            Prepare the exact LinkedIn profile or job-search results page in Chromium, then capture the current page.
          </p>
          {activePreparedRun ? (
            <div className="professional-prepared-page">
              <small>Prepared run</small>
              <strong>{runSourceLabel(activePreparedRun)}</strong>
              {runSourceUrl(activePreparedRun) && <code>{runSourceUrl(activePreparedRun)}</code>}
            </div>
          ) : (
            <div className="professional-prepared-page professional-empty-session">
              <small>Prepared page</small>
              <strong>Open Chromium and prepare LinkedIn manually.</strong>
              <span>No current page has been captured yet.</span>
            </div>
          )}
          <div className="professional-dashboard-actions">
            <button
              type="button"
              className="secondary"
              disabled={busy || !active || Boolean(activePreparedRun) || Boolean(runningRun)}
              onClick={() => void prepareNewCaptureSession()}
            >
              {busy ? "Preparing…" : "Open Chromium"}
            </button>
            <button
              type="button"
              disabled={busy || !activePreparedRun}
              onClick={() => activePreparedRun && void captureCurrentPage(activePreparedRun)}
            >
              Capture prepared page
            </button>
            {runningRun && (
              <button type="button" className="secondary" disabled={busy} onClick={() => void cancelRun(runningRun.id)}>
                Request cancellation
              </button>
            )}
          </div>
        </section>

        <section className="professional-dashboard-card professional-settings-card">
          <div className="professional-card-heading">
            <h3>Capture settings</h3>
            <span className="professional-status-pill neutral">Plan {planRefreshKey}</span>
          </div>
          <dl className="professional-settings-grid">
            <div>
              <dt>Max sources</dt>
              <dd>{captureOptions.max_sources}</dd>
            </div>
            <div>
              <dt>Scroll batches / source</dt>
              <dd>{captureOptions.max_scroll_batches}</dd>
            </div>
            <div>
              <dt>Max items / source</dt>
              <dd>{captureOptions.max_items_per_source}</dd>
            </div>
            <div>
              <dt>Timeout / source</dt>
              <dd>{captureOptions.timeout_seconds}s</dd>
            </div>
          </dl>
          <p>{captureOptions.stop_on_failure ? "Stops on first failed source." : "Continues after failed sources."}</p>
        </section>

        <section className="professional-dashboard-card professional-storage-card">
          <div className="professional-card-heading">
            <h3>Evidence storage</h3>
            <span className="professional-status-pill success">Ready</span>
          </div>
          <p>Evidence remains in the configured local Professional evidence directory.</p>
          <dl>
            <div>
              <dt>Runtime</dt>
              <dd>Visible Chromium · user-prepared page</dd>
            </div>
            <div>
              <dt>Deletion</dt>
              <dd>Modal confirmation required</dd>
            </div>
          </dl>
        </section>
      </div>

      <div className="professional-history-layout">
        <section className="professional-dashboard-card professional-history-panel">
          <div className="professional-card-heading">
            <h3>Recent capture history</h3>
            <span>{runs.length} runs</span>
          </div>
          {loaded && runs.length === 0 && <p>No captures yet. Open Chromium to prepare your first LinkedIn capture.</p>}
          {runs.length > 0 && (
            <div className="professional-history-table-wrap">
              <table className="professional-history-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Source / query</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice(0, 8).map((run) => (
                    <tr
                      key={run.id}
                      className={selectedRun?.id === run.id ? "is-selected" : ""}
                      onClick={() => setSelectedRunId(run.id)}
                    >
                      <td>
                        <span className={`professional-status-pill ${statusTone(run.status)}`}>{humanize(run.status)}</span>
                      </td>
                      <td>{formatDate(run.started_at || run.requested_at)}</td>
                      <td>
                        <strong>{runSourceLabel(run)}</strong>
                        {runSourceUrl(run) && <code>{runSourceUrl(run)}</code>}
                        <small>
                          {shortRunId(run.id)} · {run.artifact_count || "—"} artifacts · {run.stop_reason ? humanize(run.stop_reason) : progressSummary(run)}
                        </small>
                      </td>
                      <td>
                        <div className="professional-row-actions">
                          <button type="button" className="secondary" onClick={(event) => { event.stopPropagation(); setSelectedRunId(run.id); }}>
                            Details
                          </button>
                          {run.status !== "running" && (
                            <button type="button" className="danger" disabled={busy} onClick={(event) => { event.stopPropagation(); setDeleteModalRunId(run.id); updateDeletePhrase(run.id, ""); }}>
                              Delete
                            </button>
                          )}
                          {run.status === "running" && (
                            <button type="button" className="secondary" disabled={busy} onClick={(event) => { event.stopPropagation(); void cancelRun(run.id); }}>
                              Cancel
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="professional-dashboard-card professional-run-detail-panel" aria-label="Selected run details">
          <div className="professional-card-heading">
            <h3>Selected run details</h3>
            {selectedRun && <span className={`professional-status-pill ${statusTone(selectedRun.status)}`}>{humanize(selectedRun.status)}</span>}
          </div>
          {!selectedRun && <p>Select a run to review progress, evidence, and outcome.</p>}
          {selectedRun && (
            <>
              <dl className="professional-detail-grid">
                <div>
                  <dt>Started</dt>
                  <dd>{formatDate(selectedRun.started_at || selectedRun.requested_at)}</dd>
                </div>
                <div>
                  <dt>Artifacts</dt>
                  <dd>{selectedRun.artifact_count}</dd>
                </div>
                <div>
                  <dt>Source / query</dt>
                  <dd>{runSourceLabel(selectedRun)}</dd>
                </div>
                <div>
                  <dt>Outcome</dt>
                  <dd>{selectedRun.stop_reason ? humanize(selectedRun.stop_reason) : selectedRun.status}</dd>
                </div>
              </dl>
              {runSourceUrl(selectedRun) && <code className="professional-detail-url">{runSourceUrl(selectedRun)}</code>}
              <div className="professional-progress-meter">
                <span>{progressSummary(selectedRun)}</span>
                <strong>{progressPercent(selectedRun)}%</strong>
                <div aria-hidden="true">
                  <i style={{ width: `${progressPercent(selectedRun)}%` }} />
                </div>
              </div>
              {selectedRun.source_progress.length > 0 && (
                <details className="professional-source-progress" open={selectedRun.status === "running" || selectedRun.status === "completed_with_gaps" || selectedRun.status === "failed"}>
                  <summary>Source progress and failure details</summary>
                  <ol>
                    {selectedRun.source_progress.map((source) => (
                      <li key={source.source_id}>
                        <strong>{sourceLabel(selectedRun, source.source_id)}</strong>: {humanize(source.status)}
                        {source.completeness_status ? ` · ${humanize(source.completeness_status)}` : ""}
                        {source.started_at ? ` · started ${formatDate(source.started_at)}` : ""}
                        {source.completed_at ? ` · completed ${formatDate(source.completed_at)}` : ""}
                        {source.detail && <p>{source.detail}</p>}
                      </li>
                    ))}
                  </ol>
                </details>
              )}
              <div className="professional-dashboard-actions">
                {isTerminal(selectedRun) && selectedRun.artifact_count > 0 && (
                  <ProfessionalEvidenceReview apiBase={apiBase} runId={selectedRun.id} />
                )}
                {selectedRun.status !== "running" && (
                  <button type="button" className="danger" disabled={busy} onClick={() => { setDeleteModalRunId(selectedRun.id); updateDeletePhrase(selectedRun.id, ""); }}>
                    Delete selected run
                  </button>
                )}
              </div>
            </>
          )}
        </aside>
      </div>

      <div className="professional-audit-strip" aria-label="Professional section redesign audit fixes">
        <strong>Audit fixes</strong>
        <span>One active capture flow</span>
        <span>No duplicate capture buttons</span>
        <span>Compact history table</span>
        <span>Safe delete modal</span>
        <span>Above-the-fold actions</span>
      </div>

      {deleteModalRun && (
        <div className="professional-delete-modal-backdrop" role="presentation">
          <section className="professional-delete-modal" role="dialog" aria-modal="true" aria-labelledby="professional-delete-modal-title">
            <h3 id="professional-delete-modal-title">Delete capture run?</h3>
            <p>This removes the selected run and its governed local evidence. It cannot be undone.</p>
            <dl>
              <div>
                <dt>Run</dt>
                <dd>{deleteModalRun.id}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{humanize(deleteModalRun.status)}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{runSourceLabel(deleteModalRun)}</dd>
              </div>
            </dl>
            <label>
              Type {DELETE_PHRASE}
              <input
                aria-label={`Deletion phrase for ${deleteModalRun.id}`}
                value={deletePhrases[deleteModalRun.id] || ""}
                onChange={(event) => updateDeletePhrase(deleteModalRun.id, event.target.value)}
              />
            </label>
            <div className="professional-dashboard-actions">
              <button
                type="button"
                className="danger"
                disabled={busy || (deletePhrases[deleteModalRun.id] || "") !== DELETE_PHRASE}
                onClick={() => void deleteRun(deleteModalRun.id)}
              >
                Permanently delete batch
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => {
                  setDeleteModalRunId(null);
                  updateDeletePhrase(deleteModalRun.id, "");
                }}
              >
                Keep batch
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
