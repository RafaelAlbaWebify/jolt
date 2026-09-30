import { useEffect, useState } from "react";

type AISectionState = "no_evidence" | "not_analyzed" | "stale" | "current";

type AIStatus = {
  sections: Record<string, {
    state: AISectionState;
    evidence_at: string | null;
    analyzed_at: string | null;
    reason: string;
    operator_relevant: boolean;
  }>;
};

type Props = {
  apiBase: string;
  active: boolean;
  importRevision?: number;
};

function formatDate(value?: string | null) {
  if (!value) return "Never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function LinkedInAIAnalysisStatus({ apiBase, active, importRevision = 0 }: Props) {
  const [status, setStatus] = useState<AIStatus["sections"][string] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return;

    let cancelled = false;
    setError("");

    void fetch(`${apiBase}/api/ai-status`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to read LinkedIn AI analysis status.");
        return await response.json() as AIStatus;
      })
      .then((result) => {
        if (cancelled) return;
        setStatus(result.sections.linkedin_profile ?? null);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : "Unable to read LinkedIn AI status.");
      });

    return () => {
      cancelled = true;
    };
  }, [active, apiBase, importRevision]);

  const state = status?.state ?? "no_evidence";
  const statusLabel = {
    no_evidence: "No profile evidence yet",
    not_analyzed: "Analysis needed",
    stale: "Update available",
    current: "Up to date",
  }[state];

  return (
    <section className="panel linkedin-analysis-summary" aria-labelledby="linkedin-ai-analysis-heading">
      <div>
        <p className="eyebrow">Profile analysis</p>
        <h3 id="linkedin-ai-analysis-heading">Analysis status</h3>
        <p>{status?.reason ?? "Reading JOLT's persisted LinkedIn intelligence state."}</p>
      </div>
      <div className="linkedin-analysis-meta">
        <span className="linkedin-analysis-status">{statusLabel}</span>
        <span>Latest profile: {formatDate(status?.evidence_at)}</span>
        <span>Latest analysis: {formatDate(status?.analyzed_at)}</span>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
