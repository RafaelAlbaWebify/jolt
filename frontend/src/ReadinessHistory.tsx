import { useState } from "react";

import type { ApplicationReadinessData } from "./ApplicationReadiness";

type ReadinessHistoryEntry = ApplicationReadinessData & {
  created_at: string;
  is_current: boolean;
  refresh_reason?: string | null;
  supersedes_report_id?: string | null;
};

type Props = {
  apiBase: string;
  postingId: string;
  title: string;
  disabled: boolean;
  onRefreshed: () => Promise<void>;
  onError: (message: string) => void;
};

export function ReadinessHistory({
  apiBase,
  postingId,
  title,
  disabled,
  onRefreshed,
  onError,
}: Props) {
  const [history, setHistory] = useState<ReadinessHistoryEntry[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadHistory() {
    setLoading(true);
    onError("");
    try {
      const response = await fetch(`${apiBase}/api/opportunities/${postingId}/readiness/history`);
      if (!response.ok) throw new Error("Readiness history could not be loaded.");
      setHistory((await response.json()) as ReadinessHistoryEntry[]);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unexpected readiness history error.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshReadiness() {
    setLoading(true);
    onError("");
    try {
      const response = await fetch(`${apiBase}/api/opportunities/${postingId}/readiness/refresh`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Readiness could not be recalculated.");
      await onRefreshed();
      await loadHistory();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unexpected readiness refresh error.");
      setLoading(false);
    }
  }

  return (
    <details className="readiness-history">
      <summary>Readiness report history</summary>
      <div className="readiness-history-actions">
        <button type="button" className="secondary" disabled={disabled || loading} onClick={loadHistory}>
          {loading ? "Loading…" : "Load history"}
        </button>
        <button type="button" className="secondary" disabled={disabled || loading} onClick={refreshReadiness}>
          Recalculate readiness
        </button>
      </div>
      {history && history.length === 0 && <p>No readiness reports exist for {title}.</p>}
      {history && history.length > 0 && (
        <ol className="readiness-history-list" aria-label={`Readiness history for ${title}`}>
          {history.map((entry) => (
            <li key={entry.report_id}>
              <div>
                <strong>{entry.is_current ? "Current report" : "Historical report"}</strong>
                <span>{entry.priority} priority · {entry.readiness_score}/100</span>
              </div>
              <small>
                {entry.engine_version} · {new Date(entry.created_at).toLocaleString()}
                {entry.refresh_reason ? ` · ${entry.refresh_reason.replaceAll("_", " ")}` : ""}
              </small>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}
