import { useEffect, useState } from "react";

import type { ProfessionalIntelligenceSource } from "./ProfessionalIntelligence";

type CaptureExclusion = {
  source: ProfessionalIntelligenceSource;
  reason: "disabled_by_user" | "deferred_scope";
};

type CapturePlan = {
  mode: "supervised_read_only";
  execution_available: boolean;
  planned_sources: ProfessionalIntelligenceSource[];
  excluded_sources: CaptureExclusion[];
  safety_constraints: string[];
};

type Props = {
  apiBase: string;
  active: boolean;
  refreshKey: number;
};

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

export function ProfessionalCapturePlan({ apiBase, active, refreshKey }: Props) {
  const [plan, setPlan] = useState<CapturePlan | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return;
    setError("");
    fetch(`${apiBase}/api/professional-intelligence/capture-plan`)
      .then((response) => {
        if (!response.ok) throw new Error("Unable to build the supervised capture plan.");
        return response.json() as Promise<CapturePlan>;
      })
      .then(setPlan)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Capture plan failed."));
  }, [active, apiBase, refreshKey]);

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!plan) return <p role="status">Building supervised capture plan…</p>;

  return (
    <section className="panel professional-capture-plan" aria-labelledby="professional-capture-plan-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Supervised read-only</p>
          <h2 id="professional-capture-plan-heading">Supervised capture plan</h2>
          <p>
            {plan.planned_sources.length} approved sources are included. A browser opens only after
            an explicit run is recorded, authorized, and started while the user remains present.
          </p>
        </div>
        <span className="professional-plan-status">
          {plan.execution_available ? "Explicit start available" : "Execution blocked"}
        </span>
      </div>
      <div className="professional-plan-columns">
        <section>
          <h3>Planned sources</h3>
          <ol>
            {plan.planned_sources.map((source) => <li key={source.source_id}>{source.label}</li>)}
          </ol>
        </section>
        <section>
          <h3>Excluded sources</h3>
          <ul>
            {plan.excluded_sources.map((item) => (
              <li key={item.source.source_id}>{item.source.label} · {humanize(item.reason)}</li>
            ))}
          </ul>
        </section>
        <section>
          <h3>Safety constraints</h3>
          <ul>
            {plan.safety_constraints.map((constraint) => <li key={constraint}>{humanize(constraint)}</li>)}
          </ul>
        </section>
      </div>
    </section>
  );
}
