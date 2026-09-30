import { useCallback, useEffect, useState } from "react";

import { CaptureHistory } from "./CaptureHistory";
import { ReviewedDecisions } from "./ReviewedDecisions";

type AISectionState = "no_evidence" | "not_analyzed" | "stale" | "current";

type AIStatus = {
  overall_status: "no_evidence" | "update_available" | "current";
  last_intelligence_update_at: string | null;
  context_updated_at: string | null;
  current_sections: number;
  attention_sections: number;
  sections: Record<string, {
    state: AISectionState;
    evidence_at: string | null;
    analyzed_at: string | null;
    reason: string;
    operator_relevant: boolean;
  }>;
};

function statusLabel(status: AIStatus | null) {
  if (!status) return "Checking…";
  if (status.overall_status === "current") return "Up to date";
  if (status.overall_status === "update_available") return "Update available";
  return "No analysis yet";
}

function statusDescription(status: AIStatus | null) {
  if (!status) return "Reading JOLT's persisted intelligence state.";
  if (status.overall_status === "current") {
    return "Stored intelligence reflects the latest operator-relevant evidence.";
  }
  if (status.overall_status === "update_available") {
    return "Some intelligence is older than the evidence currently stored in JOLT.";
  }
  return "JOLT does not have enough analyzed evidence yet.";
}

function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("The strategy update file could not be read."));
    };
    reader.onerror = () => reject(new Error("The strategy update file could not be read."));
    reader.readAsText(file);
  });
}

function formatImportProblem(problem: unknown): string {
  if (!problem || typeof problem !== "object") return "The strategy update could not be imported.";

  const detail = (problem as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const record = item as { msg?: unknown; loc?: unknown };
      if (typeof record.msg !== "string" || !record.msg.trim()) return [];
      const location = Array.isArray(record.loc)
        ? record.loc.map(String).filter(Boolean).join(" → ")
        : "";
      return [location ? `${location}: ${record.msg}` : record.msg];
    });
    if (messages.length) return messages.join("\n");
  }

  return "The strategy update could not be imported.";
}

type Props = {
  apiBase: string;
  active?: boolean;
  onImported?: () => void | Promise<void>;
};

export function DataTools({ apiBase, active = true, onImported }: Props) {
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState("");
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);

  const loadAIStatus = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/ai-status`);
    if (!response.ok) throw new Error("Unable to read JOLT intelligence status.");
    setAIStatus(await response.json() as AIStatus);
  }, [apiBase]);

  useEffect(() => {
    if (!active) return;
    void loadAIStatus().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Unable to read JOLT intelligence status.");
    });
  }, [active, loadAIStatus]);

  async function importAIUpdate(file: File) {
    setImporting(true);
    setError("");
    setImportNotice("");

    try {
      const text = await readTextFile(file);
      let payload: unknown;
      try {
        payload = JSON.parse(text);
      } catch {
        throw new Error("The strategy update file is not valid JSON.");
      }

      const response = await fetch(`${apiBase}/api/ai-work-package/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const problem = await response.json().catch(() => null);
        throw new Error(formatImportProblem(problem));
      }

      const result = (await response.json()) as {
        imported_sections: string[];
        review_inbox_imported: boolean;
      };

      const sectionCount = result.imported_sections.length;
      const reviewText = result.review_inbox_imported ? "Review Inbox updated. " : "";
      setImportNotice(
        `Strategy update imported successfully. ${reviewText}${sectionCount} intelligence section${sectionCount === 1 ? "" : "s"} imported.`,
      );
      await loadAIStatus();
      await onImported?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The strategy update could not be imported.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <>
      <section className="panel" aria-labelledby="ai-import-status-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Intelligence</p>
            <h2 id="ai-import-status-heading">Intelligence status</h2>
            <p>{statusDescription(aiStatus)}</p>
          </div>
          <strong>{statusLabel(aiStatus)}</strong>
        </div>

        {aiStatus && (
          <div className="market-summary-grid">
            <article className="market-card">
              <span>Last intelligence update</span>
              <strong>
                {aiStatus.last_intelligence_update_at
                  ? new Date(aiStatus.last_intelligence_update_at).toLocaleString()
                  : "Not yet"}
              </strong>
            </article>
            <article className="market-card">
              <span>Current sections</span>
              <strong>{aiStatus.current_sections}</strong>
            </article>
            <article className="market-card">
              <span>Updates needed</span>
              <strong>{aiStatus.attention_sections}</strong>
            </article>
            <article className="market-card">
              <span>Review Inbox</span>
              <strong>{aiStatus.sections.review_inbox?.state.replaceAll("_", " ") ?? "unknown"}</strong>
            </article>
          </div>
        )}
        {aiStatus && aiStatus.attention_sections > 0 && (
          <p>
            <strong>Needs attention:</strong>{" "}
            {Object.entries(aiStatus.sections)
              .filter(([, section]) => section.operator_relevant && ["stale", "not_analyzed"].includes(section.state))
              .map(([name]) => name.replaceAll("_", " "))
              .join(", ")}
          </p>
        )}
      </section>

      <details className="panel operations-tools workspace-sidebar-operations">
        <summary>Advanced data & diagnostics</summary>
        {error && <p className="error" role="alert" style={{ whiteSpace: "pre-line" }}>{error}</p>}
        {importNotice && <p role="status">{importNotice}</p>}

        <div className="operations-grid">
          <section aria-labelledby="ai-exchange-heading">
            <h2 id="ai-exchange-heading">Strategy update exchange</h2>
            <p>
              Use this only for a deliberate full-strategy refresh. Normal discovery review now updates job review and intelligence together from Capture Jobs.
            </p>
            <ol>
              <li>
                <a
                  href={`${apiBase}/api/ai-work-package/export`}
                  download="JOLT_AI_WORK_PACKAGE.json"
                  title="Export JOLT's full strategy context for a deliberate broad refresh."
                >
                  <strong>Export strategy update package</strong>
                </a>
              </li>
              <li>
                <label>
                  <strong>Import reviewed strategy update</strong>
                  <input
                    aria-label="Import reviewed strategy update"
                    type="file"
                    accept=".json,application/json"
                    disabled={importing}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void importAIUpdate(file);
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
              </li>
            </ol>
            <p>{importing ? "Importing strategy update…" : "JOLT validates the returned file before applying the reviewed update."}</p>
            <details>
              <summary>Legacy compatibility exports</summary>
              <p>
                Older export formats remain available only for troubleshooting or archive compatibility.
              </p>
              <ul>
                <li><a href={`${apiBase}/api/exports/ai-review-json`} download="JOLT_AI_REVIEW_INPUT.json">Legacy AI review JSON</a></li>
                <li><a href={`${apiBase}/api/exports/ai-review-pack`} download="JOLT_AI_REVIEW_INPUT.zip">Legacy full review ZIP</a></li>
              </ul>
            </details>
          </section>
        </div>
        <ReviewedDecisions apiBase={apiBase} onError={setError} />
        <CaptureHistory apiBase={apiBase} onError={setError} />
      </details>
    </>
  );
}
