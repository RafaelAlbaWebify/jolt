import { useState } from "react";

import { CaptureHistory } from "./CaptureHistory";
import { ReviewedDecisions } from "./ReviewedDecisions";

function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }

      reject(new Error("The AI update file could not be read."));
    };

    reader.onerror = () => {
      reject(new Error("The AI update file could not be read."));
    };

    reader.readAsText(file);
  });
}

type Props = {
  apiBase: string;
  onImported?: () => void | Promise<void>;
};

export function DataTools({
  apiBase,
  onImported,
}: Props) {
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState("");

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
        throw new Error("The AI update file is not valid JSON.");
      }

      const response = await fetch(`${apiBase}/api/ai-work-package/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const problem = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;

        throw new Error(problem?.detail || "The AI update could not be imported.");
      }

      const result = (await response.json()) as {
        imported_sections: string[];
        review_inbox_imported: boolean;
      };

      const sectionCount = result.imported_sections.length;
      const reviewText = result.review_inbox_imported ? "Review Inbox updated. " : "";
      setImportNotice(
        `${reviewText}${sectionCount} intelligence section${sectionCount === 1 ? "" : "s"} imported.`,
      );

      await onImported?.();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "The AI update could not be imported.",
      );
    } finally {
      setImporting(false);
    }
  }

  return (
    <details className="panel operations-tools workspace-sidebar-operations">
      <summary>Data tools: AI exchange, capture history, and decisions</summary>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {importNotice && <p role="status">{importNotice}</p>}

      <div className="operations-grid">
        <section aria-labelledby="ai-exchange-heading">
          <h2 id="ai-exchange-heading">AI exchange</h2>

          <p>
            Export one JOLT work package, analyze it in ChatGPT, then import the single returned
            update. The package includes current JOLT context and evidence while keeping human-owned
            decisions and preferences protected.
          </p>

          <ol>
            <li>
              <a
                href={`${apiBase}/api/ai-work-package/export`}
                download="JOLT_AI_WORK_PACKAGE.json"
              >
                <strong>Export AI work package</strong>
              </a>
            </li>
            <li>
              <label>
                <strong>Import AI update</strong>
                <input
                  aria-label="Import AI update"
                  type="file"
                  accept=".json,application/json"
                  disabled={importing}
                  onChange={(event) => {
                    const file = event.target.files?.[0];

                    if (file) {
                      void importAIUpdate(file);
                    }

                    event.currentTarget.value = "";
                  }}
                />
              </label>
            </li>
          </ol>

          <p>
            {importing
              ? "Importing AI update…"
              : "JOLT validates the returned file before applying AI-derived intelligence."}
          </p>

          <details>
            <summary>Advanced / compatibility exports</summary>
            <p>
              These older Review-Inbox-only formats remain available for troubleshooting or archive
              compatibility. The unified AI work package above is the normal workflow.
            </p>
            <ul>
              <li>
                <a href={`${apiBase}/api/exports/ai-review-json`} download="JOLT_AI_REVIEW_INPUT.json">
                  Legacy AI review JSON
                </a>
              </li>
              <li>
                <a href={`${apiBase}/api/exports/ai-review-pack`} download="JOLT_AI_REVIEW_INPUT.zip">
                  Legacy full review ZIP
                </a>
              </li>
            </ul>
          </details>
        </section>
      </div>

      <ReviewedDecisions apiBase={apiBase} onError={setError} />

      <CaptureHistory apiBase={apiBase} onError={setError} />
    </details>
  );
}
