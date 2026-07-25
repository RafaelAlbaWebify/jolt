import { useState } from "react";

type ArtifactReview = {
  id: string;
  source_id: string;
  artifact_type: string;
  relative_path: string;
  completeness_status: string;
  retention_days: number;
  exists: boolean;
  integrity_valid: boolean;
  reviewable: boolean;
  content: Record<string, unknown> | unknown[] | string | null;
};

type SourceReview = {
  source_id: string;
  completeness_status: string;
  artifacts: ArtifactReview[];
};

type RunReview = {
  capture_run_id: string;
  run_status: string;
  integrity_valid: boolean;
  review_available: boolean;
  ready_for_analysis: boolean;
  sources: SourceReview[];
};

type Props = {
  apiBase: string;
  runId: string;
};

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

function renderContent(content: ArtifactReview["content"]) {
  if (content === null) return null;
  if (typeof content === "string") return <pre>{content}</pre>;
  return <pre>{JSON.stringify(content, null, 2)}</pre>;
}

export function ProfessionalEvidenceReview({ apiBase, runId }: Props) {
  const [review, setReview] = useState<RunReview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadReview() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/evidence-review`,
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "Evidence review could not be loaded.");
      }
      setReview((await response.json()) as RunReview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Evidence review failed.");
    } finally {
      setLoading(false);
    }
  }

  if (!review) {
    return (
      <div className="professional-evidence-review-launch">
        <button type="button" className="secondary" disabled={loading} onClick={() => void loadReview()}>
          {loading ? "Verifying evidence…" : "Review captured evidence"}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    );
  }

  return (
    <section className="professional-evidence-review" aria-label={`Evidence review for ${runId}`}>
      <div className="professional-evidence-review-summary">
        <strong>{review.integrity_valid ? "Integrity verified" : "Integrity problem detected"}</strong>
        <span>{review.ready_for_analysis ? "Ready for analysis" : "Analysis blocked"}</span>
      </div>
      {review.sources.map((source) => (
        <details key={source.source_id}>
          <summary>
            {source.source_id} · {humanize(source.completeness_status)} · {source.artifacts.length} artifacts
          </summary>
          <div className="professional-evidence-artifacts">
            {source.artifacts.map((artifact) => (
              <article key={artifact.id}>
                <div>
                  <strong>{humanize(artifact.artifact_type)}</strong>
                  <span>{artifact.integrity_valid ? "Hash verified" : "Missing or modified"}</span>
                </div>
                <code>{artifact.relative_path}</code>
                {artifact.reviewable && artifact.integrity_valid && renderContent(artifact.content)}
              </article>
            ))}
          </div>
        </details>
      ))}
    </section>
  );
}
