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

export function DataTools({
  apiBase,
  onImported,
}: Props) {
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState("");

  async function importAIReview(
    file: File,
  ) {
    setImporting(true);
    setError("");
    setImportNotice("");

    try {
      const text = await readTextFile(file);

      let payload: unknown;

      try {
        payload = JSON.parse(text);
      } catch {
        throw new Error(
          "The AI review file is not valid JSON.",
        );
      }

      const response = await fetch(
        `${apiBase}/api/ai-review/import`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      if (!response.ok) {
        const problem = (await response
          .json()
          .catch(() => null)) as {
          detail?: string;
        } | null;

        throw new Error(
          problem?.detail ||
            "The AI review could not be imported.",
        );
      }

      const result = (await response.json()) as {
        received_count: number;
        created_count: number;
        updated_count: number;
      };

      setImportNotice(
        `${result.received_count} AI-reviewed job${
          result.received_count === 1 ? "" : "s"
        } imported: ${result.created_count} new, ${
          result.updated_count
        } updated.`,
      );

      await onImported?.();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The AI review could not be imported.",
      );
    } finally {
      setImporting(false);
    }
  }

  return (
    <details className="panel operations-tools workspace-sidebar-operations">
      <summary>
        Data tools: capture batches, decisions, and exports
      </summary>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {importNotice && (
        <p role="status">{importNotice}</p>
      )}

      <div className="operations-grid">
        <section aria-labelledby="export-heading">
          <h2 id="export-heading">AI review</h2>

          <p>
            Export the latest capture as clean source evidence for
            deep AI analysis. JOLT does not include its own
            recommendation, score, or eligibility decision.
          </p>

          <a
            href={`${apiBase}/api/exports/ai-review-pack`}
            download="JOLT_AI_REVIEW_INPUT.zip"
          >
            Download AI review package
          </a>

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

      <ReviewedDecisions
        apiBase={apiBase}
        onError={setError}
      />

      <CaptureHistory
        apiBase={apiBase}
        onError={setError}
      />
    </details>
  );
}
