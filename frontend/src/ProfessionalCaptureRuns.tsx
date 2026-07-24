import { useCallback, useEffect, useState } from "react";

import type { ProfessionalIntelligenceSource } from "./ProfessionalIntelligence";

type ProfessionalCaptureRun = {
  id: string;
  mode: "preview_only";
  status: "planned" | "cancelled";
  planned_sources: ProfessionalIntelligenceSource[];
  safety_constraints: string[];
  requested_at: string;
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

  async function cancelRun(runId: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/cancel`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("The preview run could not be cancelled.");
      const changed = (await response.json()) as ProfessionalCaptureRun;
      setRuns((current) => current.map((run) => (run.id === changed.id ? changed : run)));
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
          <p>Record the current approved plan as an immutable local snapshot. This does not launch a browser.</p>
        </div>
        <button type="button" disabled={busy || !active} onClick={() => void recordPreviewRun()}>
          {busy ? "Saving…" : "Record preview run"}
        </button>
      </div>
      <p className="professional-ledger-note">
        Current plan revision: {planRefreshKey}. Execution and evidence artifacts are unavailable.
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
              {run.status === "planned" && (
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void cancelRun(run.id)}
                >
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
