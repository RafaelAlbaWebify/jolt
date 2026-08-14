import { useState } from "react";

import { CaptureHistory } from "./CaptureHistory";
import { ReviewedDecisions } from "./ReviewedDecisions";

type Props = {
  apiBase: string;
};

export function DataTools({ apiBase }: Props) {
  const [error, setError] = useState("");

  return (
    <details className="panel operations-tools workspace-sidebar-operations">
      <summary>Data tools: capture batches, decisions, and exports</summary>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="operations-grid">
        <section aria-labelledby="export-heading">
          <h2 id="export-heading">ChatGPT review</h2>
          <p>
            Export the latest capture, full job evidence, JOLT classifications,
            profile context, Market Intelligence observations, current Market
            Insights, and audit lineage in one ZIP.
          </p>
          <a href={`${apiBase}/api/exports/review-pack`} download="JOLT_REVIEW_PACK.zip">
            Download review pack
          </a>
        </section>
      </div>
      <ReviewedDecisions apiBase={apiBase} onError={setError} />
      <CaptureHistory apiBase={apiBase} onError={setError} />
    </details>
  );
}
