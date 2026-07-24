import { useEffect, useState } from "react";

type EvidencePolicy = {
  allowed_artifact_types: string[];
  page_completeness_statuses: string[];
  default_retention_days: number;
  maximum_retention_days: number;
  text_extraction_policy: string[];
  prohibited_evidence: string[];
};

type ExecutionReadiness = {
  ready: boolean;
  execution_available: boolean;
  blockers: string[];
  required_user_actions: string[];
  evidence_policy: EvidencePolicy;
};

type Props = {
  apiBase: string;
  active: boolean;
};

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

export function ProfessionalExecutionReadiness({ apiBase, active }: Props) {
  const [readiness, setReadiness] = useState<ExecutionReadiness | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return;
    setError("");
    fetch(`${apiBase}/api/professional-intelligence/execution-readiness`)
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load execution readiness.");
        return response.json() as Promise<ExecutionReadiness>;
      })
      .then(setReadiness)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Readiness failed."));
  }, [active, apiBase]);

  if (!active) return null;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!readiness) return <p role="status">Checking execution readiness…</p>;

  return (
    <section className="panel professional-execution-readiness" aria-labelledby="professional-execution-readiness-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Execution contract</p>
          <h2 id="professional-execution-readiness-heading">Supervised capture readiness</h2>
          <p>Capture remains blocked until every explicit safety and local-evidence requirement is implemented.</p>
        </div>
        <span className="professional-plan-status">{readiness.ready ? "Ready" : "Blocked"}</span>
      </div>
      <div className="professional-plan-columns">
        <section>
          <h3>Current blockers</h3>
          <ul>{readiness.blockers.map((item) => <li key={item}>{humanize(item)}</li>)}</ul>
        </section>
        <section>
          <h3>Required user actions</h3>
          <ul>{readiness.required_user_actions.map((item) => <li key={item}>{humanize(item)}</li>)}</ul>
        </section>
        <section>
          <h3>Evidence policy</h3>
          <p>{readiness.evidence_policy.allowed_artifact_types.length} permitted artifact types.</p>
          <p>Default retention: {readiness.evidence_policy.default_retention_days} days.</p>
          <p>Maximum retention: {readiness.evidence_policy.maximum_retention_days} days.</p>
          <p>Rendered DOM text is primary; OCR is fallback-only and must be marked derived.</p>
        </section>
      </div>
    </section>
  );
}
