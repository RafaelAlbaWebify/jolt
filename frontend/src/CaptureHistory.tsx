import { useCallback, useEffect, useState } from "react";

export type CaptureRunSummary = {
  capture_run_id: string;
  source: string;
  mode: string;
  status: string;
  search_url: string;
  warnings: string[];
  requested_item_limit: number | null;
  observed_item_count: number;
  stop_reason: string;
  started_at: string;
  completed_at: string | null;
  total_items: number;
  verified_items: number;
  rejected_items: number;
};

type CaptureItem = {
  capture_item_id: string;
  source_job_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  detail_status: string;
  verification_reasons: string[];
  posting_id: string | null;
};

type CapturePage = {
  page_number: number;
  visible_job_ids: string[];
  next_control_present: boolean;
  next_control_enabled: boolean;
};

type CaptureRun = CaptureRunSummary & {
  pages: CapturePage[];
  items: CaptureItem[];
};

type Props = {
  apiBase: string;
  onError: (message: string) => void;
};

function readableReason(value: string): string {
  return value ? value.replaceAll("_", " ") : "not recorded";
}

function captureBound(run: CaptureRunSummary): string {
  const requested = run.requested_item_limit ?? "not recorded";
  return `${run.observed_item_count} observed · ${requested} requested`;
}

export function CaptureHistory({ apiBase, onError }: Props) {
  const [runs, setRuns] = useState<CaptureRunSummary[]>([]);
  const [selected, setSelected] = useState<CaptureRun | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/captures`);
    if (!response.ok) throw new Error("Unable to load capture history.");
    setRuns((await response.json()) as CaptureRunSummary[]);
  }, [apiBase]);

  useEffect(() => {
    refresh().catch((caught) => {
      onError(caught instanceof Error ? caught.message : "Unable to load capture history.");
    });
  }, [onError, refresh]);

  async function inspect(runId: string) {
    setBusy(true);
    try {
      const response = await fetch(`${apiBase}/api/captures/${runId}`);
      if (!response.ok) throw new Error("Unable to load capture diagnostics.");
      setSelected((await response.json()) as CaptureRun);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unable to load capture diagnostics.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="capture-history-heading">
      <div className="section-heading">
        <div>
          <h2 id="capture-history-heading">LinkedIn capture history</h2>
          <p>Inspect accepted and rejected evidence before relying on captured opportunities.</p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => refresh().catch(() => onError("Unable to refresh capture history."))}
        >
          Refresh captures
        </button>
      </div>

      {runs.length === 0 ? <p>No capture runs recorded yet.</p> : (
        <div className="queue capture-runs">
          {runs.map((run) => (
            <article key={run.capture_run_id}>
              <div>
                <h3>{run.source} · {run.mode}</h3>
                <p>{new Date(run.started_at).toLocaleString()} · {run.status.replaceAll("_", " ")}</p>
                <p>{run.verified_items} verified · {run.rejected_items} rejected · {run.total_items} total</p>
                <p>{captureBound(run)}</p>
                <p><strong>Stopped:</strong> {readableReason(run.stop_reason)}</p>
              </div>
              <button type="button" disabled={busy} onClick={() => inspect(run.capture_run_id)}>
                Inspect capture
              </button>
            </article>
          ))}
        </div>
      )}

      {selected && (
        <div className="capture-diagnostics" aria-live="polite">
          <h3>Capture diagnostics</h3>
          <p><strong>Capture bound:</strong> {captureBound(selected)}</p>
          <p><strong>Stop reason:</strong> {readableReason(selected.stop_reason)}</p>
          {selected.search_url && <p><a href={selected.search_url} target="_blank" rel="noreferrer">Open source search</a></p>}
          {selected.warnings.length > 0 && (
            <div>
              <strong>Warnings</strong>
              <ul>{selected.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </div>
          )}
          <p>{selected.pages.map((page) => `Page ${page.page_number}: ${page.visible_job_ids.length} visible jobs; next ${page.next_control_enabled ? "enabled" : "not enabled"}`).join(" · ")}</p>
          <div className="queue">
            {selected.items.map((item) => (
              <article key={item.capture_item_id}>
                <div>
                  <h4>{item.title || `LinkedIn job ${item.source_job_id}`}</h4>
                  <p>{[item.company, item.location].filter(Boolean).join(" · ")}</p>
                  {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Open job</a>}
                  {item.verification_reasons.length > 0 && (
                    <ul>{item.verification_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                  )}
                </div>
                <div className="queue-status">
                  <strong>{item.detail_status.replaceAll("_", " ")}</strong>
                  <span>{item.posting_id ? "canonical posting created" : "not ingested"}</span>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
