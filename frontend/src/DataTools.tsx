import { useState } from "react";

import { CaptureHistory } from "./CaptureHistory";

type Props = {
  apiBase: string;
};

export function DataTools({ apiBase }: Props) {
  const [error, setError] = useState("");

  return (
    <details className="panel operations-tools workspace-sidebar-operations">
      <summary>Data tools: capture batches and exports</summary>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="operations-grid">
        <section aria-labelledby="export-heading">
          <h2 id="export-heading">Analysis and feedback</h2>
          <p>Export the complete evidence chain as JSON, CSV, and Markdown.</p>
          <a href={`${apiBase}/api/exports/analysis-pack`} download="JOLT_ANALYSIS_PACK.zip">
            Download analysis pack
          </a>
        </section>
      </div>
      <CaptureHistory apiBase={apiBase} onError={setError} />
    </details>
  );
}
