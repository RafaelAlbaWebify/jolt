import { useCallback, useEffect, useRef, useState } from "react";

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

type ProfessionalRoutingCounts = {
  job_opportunities: number;
  linkedin_presence: number;
  market_signals: number;
  unclassified_evidence: number;
  rejected_noise: number;
};

type ProfessionalSourceRoutingDecision = {
  source_id: string;
  label: string;
  source_category: string;
  target_bucket: string;
  target_workspace: string;
  routing_status: string;
  reason: string;
};

type ProfessionalCaptureRoutingSummary = {
  capture_run_id: string;
  run_status: string;
  artifact_count: number;
  total_sources: number;
  completed_sources: number;
  counts: ProfessionalRoutingCounts;
  decisions: ProfessionalSourceRoutingDecision[];
  explanation: string;
};

type OpportunityImportCandidate = {
  title: string;
  company: string;
  location: string;
  posting_id: string;
  identity_status: string;
  recommendation: string;
  ranking_score: number;
};

type OpportunityImportResult = {
  capture_run_id: string;
  imported_count: number;
  skipped_count: number;
  candidates: OpportunityImportCandidate[];
  warnings: string[];
};

type Props = {
  apiBase: string;
  active: boolean;
  planRefreshKey: number;
  captureOptions: ProfessionalCaptureOptions;
  startRequestKey?: number;
};

const ROUTING_COUNT_LABELS: Array<[keyof ProfessionalRoutingCounts, string]> = [
  ["job_opportunities", "Review Inbox jobs"],
  ["linkedin_presence", "LinkedIn presence"],
  ["market_signals", "Market signals"],
  ["unclassified_evidence", "Needs review"],
  ["rejected_noise", "Rejected/noise"],
];

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

function isTerminalCapture(run: ProfessionalCaptureRun) {
  return run.status === "completed" || run.status === "completed_with_gaps";
}

export function ProfessionalCaptureRuns({
  apiBase,
  active,
  planRefreshKey,
  captureOptions,
  startRequestKey = 0,
}: Props) {
  const [runs, setRuns] = useState<ProfessionalCaptureRun[]>([]);
  const [routingSummaries, setRoutingSummaries] = useState<Record<string, ProfessionalCaptureRoutingSummary>>({});
  const [opportunityImports, setOpportunityImports] = useState<Record<string, OpportunityImportResult>>({});
  const [importingRunId, setImportingRunId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const [deletePhrase, setDeletePhrase] = useState("");
  const [error, setError] = useState("");
  const ledgerRef = useRef<HTMLElement | null>(null);
  const previousStartRequestKey = useRef(startRequestKey);

  const loadRoutingSummaries = useCallback(async (nextRuns: ProfessionalCaptureRun[]) => {
    const entries = await Promise.all(
      nextRuns.map(async (run) => {
        const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs/${run.id}/routing-summary`);
        if (!response.ok) return null;
        const summary = (await response.json()) as ProfessionalCaptureRoutingSummary;
        return [run.id, summary] as const;
      }),
    );
    setRoutingSummaries(Object.fromEntries(entries.filter((entry): entry is readonly [string, ProfessionalCaptureRoutingSummary] => entry !== null)));
  }, [apiBase]);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`);
      if (!response.ok) throw new Error("Unable to load the Capture & Evidence run ledger.");
      const nextRuns = (await response.json()) as ProfessionalCaptureRun[];
      setRuns(nextRuns);
      await loadRoutingSummaries(nextRuns);
      setLoaded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Run ledger failed.");
    } finally {
      setLoading(false);
    }
  }, [apiBase, loadRoutingSummaries]);

  useEffect(() => {
    if (!active || loaded) return;
    void loadRuns();
  }, [active, loadRuns, loaded]);

  useEffect(() => {
    if (startRequestKey === previousStartRequestKey.current) return;
    previousStartRequestKey.current = startRequestKey;
    if (active) void startNewCapture();
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
    void loadRoutingSummaries([changed]);
  }

  async function authorizeAndStart(run: ProfessionalCaptureRun): Promise<ProfessionalCaptureRun> {
    let ready = run;
    if (ready.status === "planned" || ready.status === "expired") {
      const authorization = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${ready.id}/authorize`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmation_phrase: AUTHORIZATION_PHRASE, user_present: true }),
        },
      );
      if (!authorization.ok) {
        const payload = (await authorization.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The capture could not be authorized.");
      }
      ready = (await authorization.json()) as ProfessionalCaptureRun;
      replaceRun(ready);
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ options: captureOptions }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The supervised capture could not be prepared.");
      }
      const created = (await response.json()) as ProfessionalCaptureRun;
      setRuns((current) => [created, ...current]);
      await loadRoutingSummaries([created]);
      const queued = await authorizeAndStart(created);
      replaceRun(queued);
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
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs/${runId}/cancel`, { method: "POST" });
      if (!response.ok) throw new Error("The capture could not be cancelled.");
      replaceRun((await response.json()) as ProfessionalCaptureRun);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture cancellation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function importOpportunities(runId: string) {
    setImportingRunId(runId);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/opportunity-candidates/import`,
        { method: "POST" },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "Opportunity candidates could not be imported.");
      }
      const result = (await response.json()) as OpportunityImportResult;
      setOpportunityImports((current) => ({ ...current, [runId]: result }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Opportunity import failed.");
    } finally {
      setImportingRunId(null);
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
      setRoutingSummaries((current) => {
        const next = { ...current };
        delete next[runId];
        return next;
      });
      setOpportunityImports((current) => {
        const next = { ...current };
        delete next[runId];
        return next;
      });
      setDeletingRunId(null);
      setDeletePhrase("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Capture deletion failed.");
    } finally {
      setBusy(false);
    }
  }

  function renderRoutingSummary(run: ProfessionalCaptureRun) {
    const summary = routingSummaries[run.id];
    if (!summary) return <p>Routing summary is loading…</p>;
    return (
      <details className="professional-routing-summary" open>
        <summary>Routing summary / evidence inbox</summary>
        <p>{summary.explanation}</p>
        <div className="professional-routing-counts">
          {ROUTING_COUNT_LABELS.map(([key, label]) => (
            <span key={key}><strong>{summary.counts[key]}</strong> {label}</span>
          ))}
        </div>
        <ol>
          {summary.decisions.map((decision) => (
            <li key={decision.source_id}>
              <strong>{decision.label}</strong>: {humanize(decision.target_bucket)} → {decision.target_workspace} · {humanize(decision.routing_status)}
              <p>{decision.reason}</p>
            </li>
          ))}
        </ol>
      </details>
    );
  }

  function renderOpportunityImport(run: ProfessionalCaptureRun) {
    const result = opportunityImports[run.id];
    return (
      <section className="professional-opportunity-import" aria-label="Opportunity candidate import">
        <button
          type="button"
          disabled={importingRunId === run.id || !isTerminalCapture(run)}
          onClick={() => void importOpportunities(run.id)}
        >
          {importingRunId === run.id ? "Importing candidates…" : "Import opportunity candidates to Review Inbox"}
        </button>
        <p>Use this after a completed career/job-source capture to create reviewed opportunity candidates from rendered evidence.</p>
        {result && (
          <div role="status">
            <strong>{result.imported_count} opportunity candidates imported to Review Inbox.</strong>
            {result.skipped_count > 0 && <p>{result.skipped_count} duplicate candidates skipped.</p>}
            {result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            {result.candidates.length > 0 && (
              <ol>
                {result.candidates.map((candidate) => (
                  <li key={candidate.posting_id}>
                    <strong>{candidate.title}</strong> · {candidate.company} · {candidate.location || "location not found"} · {candidate.recommendation} · score {candidate.ranking_score}
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </section>
    );
  }

  return (
    <section id="professional-run-ledger" ref={ledgerRef} className="panel professional-run-ledger" aria-labelledby="professional-run-ledger-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Capture operations</p>
          <h2 id="professional-run-ledger-heading">Capture history</h2>
          <p>Review completed captures, routing evidence, import opportunity candidates, or remove a bad batch.</p>
        </div>
        <button type="button" className="secondary" disabled={busy || !active} onClick={() => void startNewCapture()}>
          {busy ? "Capturing…" : "Start another capture"}
        </button>
      </div>
      <p className="professional-ledger-note">
        Current source revision: {planRefreshKey}. Each batch records the exact limits used. Job evidence must route to Review Inbox; LinkedIn presence evidence must route to LinkedIn Command Center.
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
                <strong>{humanize(run.status)}</strong>
                <span>{new Date(run.requested_at).toLocaleString()}</span>
              </div>
              <p>{run.planned_sources.length} sources · {run.artifact_count} artifacts</p>
              <p>Limits: {run.capture_options.max_sources} sources · {run.capture_options.max_scroll_batches} scroll batches · {run.capture_options.max_items_per_source} items/source · {run.capture_options.timeout_seconds}s timeout</p>
              <p>
                Progress: {progressSummary(run)}
                {run.current_source_id ? ` · Current: ${sourceLabel(run, run.current_source_id)}` : ""}
                {run.cancel_requested ? " · cancellation requested" : ""}
              </p>
              {run.progress_updated_at && <p>Progress updated: {formatDate(run.progress_updated_at)}</p>}
              {renderRoutingSummary(run)}
              {isTerminalCapture(run) && renderOpportunityImport(run)}
              {run.source_progress.length > 0 && (
                <details className="professional-source-progress" open={run.status === "running" || run.status === "completed_with_gaps" || run.status === "failed"}>
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
              {(run.status === "planned" || run.status === "authorized" || run.status === "expired") && (
                <button type="button" disabled={busy} onClick={() => void resumeRun(run)}>Start capture</button>
              )}
              {run.status === "running" && (
                <button type="button" className="secondary" disabled={busy} onClick={() => void cancelRun(run.id)}>Request cancellation</button>
              )}
              {isTerminalCapture(run) && <ProfessionalEvidenceReview apiBase={apiBase} runId={run.id} />}
              {run.stop_reason && <p>{humanize(run.stop_reason)}</p>}
              {run.status !== "running" && deletingRunId !== run.id && (
                <button type="button" className="danger" disabled={busy} onClick={() => { setDeletingRunId(run.id); setDeletePhrase(""); }}>
                  Delete this capture batch
                </button>
              )}
              {deletingRunId === run.id && (
                <div className="professional-delete-confirmation">
                  <strong>Delete this capture batch?</strong>
                  <p>This removes only this run and its governed local evidence. It cannot be undone.</p>
                  <label>
                    Type {DELETE_PHRASE}
                    <input aria-label={`Deletion phrase for ${run.id}`} value={deletePhrase} onChange={(event) => setDeletePhrase(event.target.value)} />
                  </label>
                  <div className="professional-source-editor-actions">
                    <button type="button" className="danger" disabled={busy || deletePhrase !== DELETE_PHRASE} onClick={() => void deleteRun(run.id)}>Permanently delete batch</button>
                    <button type="button" className="secondary" disabled={busy} onClick={() => { setDeletingRunId(null); setDeletePhrase(""); }}>Keep batch</button>
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
