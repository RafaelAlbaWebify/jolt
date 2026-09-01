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

      reject(new Error("The AI review file could not be read."));
    };

    reader.onerror = () => {
      reject(new Error("The AI review file could not be read."));
    };

    reader.readAsText(file);
  });
}

type Props = {
  apiBase: string;
  onImported?: () => void | Promise<void>;
};

type AIExportFormat = "json" | "zip";

const AI_EXPORT_FORMAT_KEY = "jolt.aiReview.primaryExportFormat";
const AI_EXPORT_OTHER_KEY = "jolt.aiReview.includeOtherFormat";

function initialAIExportFormat(): AIExportFormat {
  try {
    return window.localStorage.getItem(AI_EXPORT_FORMAT_KEY) === "zip" ? "zip" : "json";
  } catch {
    return "json";
  }
}

function initialIncludeOtherFormat(): boolean {
  try {
    return window.localStorage.getItem(AI_EXPORT_OTHER_KEY) === "true";
  } catch {
    return false;
  }
}

export function DataTools({
  apiBase,
  onImported,
}: Props) {
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState("");
  const [aiExportFormat, setAIExportFormat] = useState<AIExportFormat>(initialAIExportFormat);
  const [includeOtherFormat, setIncludeOtherFormat] = useState(initialIncludeOtherFormat);

  function chooseAIExportFormat(format: AIExportFormat) {
    setAIExportFormat(format);
    try {
      window.localStorage.setItem(AI_EXPORT_FORMAT_KEY, format);
    } catch {
      // Browser storage is optional.
    }
  }

  function chooseIncludeOtherFormat(value: boolean) {
    setIncludeOtherFormat(value);
    try {
      window.localStorage.setItem(AI_EXPORT_OTHER_KEY, String(value));
    } catch {
      // Browser storage is optional.
    }
  }

  const jsonDownload = (
    <a
      href={`${apiBase}/api/exports/ai-review-json`}
      download="JOLT_AI_REVIEW_INPUT.json"
    >
      Download AI review JSON
    </a>
  );

  const zipDownload = (
    <a
      href={`${apiBase}/api/exports/ai-review-pack`}
      download="JOLT_AI_REVIEW_INPUT.zip"
    >
      Download AI review ZIP
    </a>
  );

  async function importAIReview(file: File) {
    setImporting(true);
    setError("");
    setImportNotice("");

    try {
      const text = await readTextFile(file);

      let payload: unknown;

      try {
        payload = JSON.parse(text);
      } catch {
        throw new Error("The AI review file is not valid JSON.");
      }

      const response = await fetch(`${apiBase}/api/ai-review/import`, {
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

        throw new Error(problem?.detail || "The AI review could not be imported.");
      }

      const result = (await response.json()) as {
        received_count: number;
        created_count: number;
        updated_count: number;
      };

      setImportNotice(
        `${result.received_count} AI-reviewed job${
          result.received_count === 1 ? "" : "s"
        } imported: ${result.created_count} new, ${result.updated_count} updated.`,
      );

      await onImported?.();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "The AI review could not be imported.",
      );
    } finally {
      setImporting(false);
    }
  }

  return (
    <details className="panel operations-tools workspace-sidebar-operations">
      <summary>Data tools: capture batches, decisions, and exports</summary>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {importNotice && <p role="status">{importNotice}</p>}

      <div className="operations-grid">
        <section aria-labelledby="export-heading">
          <h2 id="export-heading">AI review</h2>

          <p>
            Export the latest capture as clean source evidence for deep AI analysis. JOLT does not
            include its own recommendation, score, or eligibility decision.
          </p>

          <fieldset className="capture-export-format">
            <legend>AI review export</legend>
            <label>
              <input
                type="radio"
                name="ai-review-export-format"
                value="json"
                checked={aiExportFormat === "json"}
                onChange={() => chooseAIExportFormat("json")}
              />
              <span>
                <strong>JSON — Recommended</strong>
                <small>One structured file for ChatGPT and other AI tools.</small>
              </span>
            </label>
            <label>
              <input
                type="radio"
                name="ai-review-export-format"
                value="zip"
                checked={aiExportFormat === "zip"}
                onChange={() => chooseAIExportFormat("zip")}
              />
              <span>
                <strong>ZIP — Full package</strong>
                <small>Preserves the existing multi-file AI review package.</small>
              </span>
            </label>
            <label className="capture-export-other">
              <input
                type="checkbox"
                checked={includeOtherFormat}
                onChange={(event) => chooseIncludeOtherFormat(event.target.checked)}
              />
              Also show the other format
            </label>
          </fieldset>

          <p>
            {aiExportFormat === "json" ? jsonDownload : zipDownload}
            {includeOtherFormat && (
              <>
                {" · "}
                {aiExportFormat === "json" ? zipDownload : jsonDownload}
              </>
            )}
          </p>

          <label>
            Import reviewed JSON
            <input
              aria-label="Import AI review"
              type="file"
              accept=".json,application/json"
              disabled={importing}
              onChange={(event) => {
                const file = event.target.files?.[0];

                if (file) {
                  void importAIReview(file);
                }

                event.currentTarget.value = "";
              }}
            />
          </label>

          <p>
            {importing
              ? "Importing AI review…"
              : "The imported AI decision becomes the Review Inbox classification authority."}
          </p>
        </section>
      </div>

      <ReviewedDecisions apiBase={apiBase} onError={setError} />

      <CaptureHistory apiBase={apiBase} onError={setError} />
    </details>
  );
}
