import { useState } from "react";

import { CaptureHistory } from "./CaptureHistory";
import { ReviewedDecisions } from "./ReviewedDecisions";

const AI_IMPORT_RECEIPT_KEY = "jolt.ai.lastImportReceipt.v1";

type AIImportReceipt = {
  fileName: string;
  importedAt: string;
  importedSections: string[];
  reviewInboxImported: boolean;
};

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
    reader.onerror = () => reject(new Error("The AI update file could not be read."));
    reader.readAsText(file);
  });
}

function loadImportReceipt(): AIImportReceipt | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(AI_IMPORT_RECEIPT_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<AIImportReceipt>;
    if (!value.fileName || !value.importedAt || !Array.isArray(value.importedSections)) return null;
    return {
      fileName: value.fileName,
      importedAt: value.importedAt,
      importedSections: value.importedSections.map(String),
      reviewInboxImported: Boolean(value.reviewInboxImported),
    };
  } catch {
    return null;
  }
}

type Props = {
  apiBase: string;
  onImported?: () => void | Promise<void>;
};

export function DataTools({ apiBase, onImported }: Props) {
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState("");
  const [lastImport, setLastImport] = useState<AIImportReceipt | null>(loadImportReceipt);

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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const problem = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(problem?.detail || "The AI update could not be imported.");
      }

      const result = (await response.json()) as {
        imported_sections: string[];
        review_inbox_imported: boolean;
      };

      const receipt: AIImportReceipt = {
        fileName: file.name,
        importedAt: new Date().toISOString(),
        importedSections: result.imported_sections,
        reviewInboxImported: result.review_inbox_imported,
      };
      window.localStorage.setItem(AI_IMPORT_RECEIPT_KEY, JSON.stringify(receipt));
      setLastImport(receipt);

      const sectionCount = result.imported_sections.length;
      const reviewText = result.review_inbox_imported ? "Review Inbox updated. " : "";
      setImportNotice(
        `AI update imported successfully. ${reviewText}${sectionCount} intelligence section${sectionCount === 1 ? "" : "s"} imported.`,
      );
      await onImported?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The AI update could not be imported.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <>
      <section className="panel" aria-labelledby="ai-import-status-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">AI round trip</p>
            <h2 id="ai-import-status-heading">AI update status</h2>
            <p>
              {lastImport
                ? "The most recent reviewed package was accepted by JOLT. This receipt remains visible after navigation or reload."
                : "No successful AI update import has been recorded in this browser yet."}
            </p>
          </div>
          <strong>{lastImport ? "Imported" : "No import yet"}</strong>
        </div>

        {lastImport && (
          <div className="market-summary-grid">
            <article className="market-card"><span>File</span><strong>{lastImport.fileName}</strong></article>
            <article className="market-card"><span>Imported at</span><strong>{new Date(lastImport.importedAt).toLocaleString()}</strong></article>
            <article className="market-card"><span>Intelligence sections</span><strong>{lastImport.importedSections.length}</strong></article>
            <article className="market-card"><span>Review Inbox</span><strong>{lastImport.reviewInboxImported ? "Updated" : "Not included"}</strong></article>
          </div>
        )}
        {lastImport?.importedSections.length ? (
          <p><strong>Updated:</strong> {lastImport.importedSections.join(", ")}</p>
        ) : null}
      </section>

      <details className="panel operations-tools workspace-sidebar-operations">
        <summary>Data tools: AI exchange, capture history, and decisions</summary>
        {error && <p className="error" role="alert">{error}</p>}
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
              <li><a href={`${apiBase}/api/ai-work-package/export`} download="JOLT_AI_WORK_PACKAGE.json"><strong>Export AI work package</strong></a></li>
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
                      if (file) void importAIUpdate(file);
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
              </li>
            </ol>
            <p>{importing ? "Importing AI update…" : "JOLT validates the returned file before applying AI-derived intelligence."}</p>
            <details>
              <summary>Advanced / compatibility exports</summary>
              <p>
                These older Review-Inbox-only formats remain available for troubleshooting or archive
                compatibility. The unified AI work package above is the normal workflow.
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
