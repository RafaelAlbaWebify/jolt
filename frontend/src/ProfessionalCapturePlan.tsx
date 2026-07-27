import { useCallback, useEffect, useRef, useState } from "react";

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);

  const loadPlan = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-plan`);
      if (!response.ok) throw new Error("Unable to build the supervised capture plan.");
      const loaded = (await response.json()) as CapturePlan;
      if (mountedRef.current && requestIdRef.current === requestId) setPlan(loaded);
    } catch (caught) {
      if (mountedRef.current && requestIdRef.current === requestId) {
        setError(caught instanceof Error ? caught.message : "Capture plan failed.");
      }
    } finally {
      if (mountedRef.current && requestIdRef.current === requestId) setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (!active) return;
    void loadPlan();
  }, [active, loadPlan, refreshKey]);

  useEffect(() => () => {
    mountedRef.current = false;
  }, []);

  if (error && !plan) {
    return (
      <section className="panel professional-capture-plan" aria-labelledby="professional-capture-plan-heading">
        <h2 id="professional-capture-plan-heading">Supervised capture plan</h2>
        <p className="error" role="alert">{error}</p>
        <button type="button" className="secondary" disabled={loading} onClick={() => void loadPlan()}>
          Retry capture plan
        </button>
      </section>
    );
  }
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
          {loading ? "Refreshing" : plan.execution_available ? "Explicit start available" : "Execution blocked"}
        </span>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {error && (
        <button type="button" className="secondary" disabled={loading} onClick={() => void loadPlan()}>
          Retry capture plan
        </button>
      )}
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
