import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

type FeedbackItem = {
  feedback_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  confidence?: number | null;
  evidence_refs: string[];
};

type MarketData = {
  authority: string;
  context_version: string;
  market_summary: Record<string, unknown>;
  skills_gap_summary: Record<string, unknown>;
  capture_strategy: Record<string, unknown>;
  application_strategy: Record<string, unknown>;
  profile_strategy: Record<string, unknown>;
  evidence_provenance: {
    observation_count: number;
    canonical_role_count: number;
    duplicate_observation_count: number;
    capture_run_count: number;
    oldest_evidence_at: string | null;
    newest_evidence_at: string | null;
    latest_capture_at: string | null;
  };
  freshness: {
    status: string;
    ai_updated_at: string | null;
    latest_capture_at: string | null;
    needs_analysis: boolean;
    reason: string;
  };
  latest_feedback: FeedbackItem[];
  recommendations: FeedbackItem[];
};

type Props = { apiBase: string; active: boolean };

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function isTechnicalKey(value: string) {
  return /(^|_)(id|uuid|capture_run|source_job|processing_mode|evidence_refs?)($|_)/i.test(value);
}

function compactEntries(data: Record<string, unknown>, limit = 5) {
  return Object.entries(data)
    .filter(([key]) => !isTechnicalKey(key))
    .slice(0, limit);
}

function primitiveValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return "—";
}

function StructuredValue({ value, depth = 0 }: { value: unknown; depth?: number }): ReactNode {
  if (value == null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span className="market-ai-primitive">{primitiveValue(value)}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="market-ai-empty">None</span>;
    return (
      <ul className={`market-ai-list market-ai-list-depth-${Math.min(depth, 2)}`}>
        {value.map((item, index) => (
          <li key={index} className={typeof item === "object" && item !== null ? "market-ai-record-item" : undefined}>
            <StructuredValue value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object") {
    const entries = compactEntries(value as Record<string, unknown>, depth === 0 ? 5 : 4);
    if (entries.length === 0) return <span className="market-ai-empty">None</span>;
    return (
      <dl className={`market-ai-object market-ai-object-depth-${Math.min(depth, 2)}`}>
        {entries.map(([key, item]) => (
          <div key={key} className="market-ai-object-row">
            <dt>{readable(key)}</dt>
            <dd><StructuredValue value={item} depth={depth + 1} /></dd>
          </div>
        ))}
      </dl>
    );
  }

  return <span className="market-ai-primitive">{String(value)}</span>;
}

function InsightSection({ title, data, empty }: { title: string; data: Record<string, unknown>; empty: string }) {
  const entries = compactEntries(data);
  return (
    <section className="market-card market-ranking-card">
      <h3>{title}</h3>
      {entries.length === 0 ? <p>{empty}</p> : (
        <dl className="market-ai-insights">
          {entries.map(([key, value]) => (
            <div key={key} className="market-ai-insight-row">
              <dt>{readable(key)}</dt>
              <dd><StructuredValue value={value} /></dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

export function MarketIntelligence({ apiBase, active }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!active) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/ai-market/view`, { signal });
      if (!response.ok) throw new Error("Unable to load market intelligence.");
      setData(await response.json() as MarketData);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(caught instanceof Error ? caught.message : "Market intelligence failed.");
    } finally {
      setLoading(false);
    }
  }, [active, apiBase]);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [active, load]);

  return (
    <main className="market-intelligence market-intelligence-compact" aria-labelledby="market-insights-heading">
      <section className="panel market-control-panel">
        <div className="section-heading market-heading-row">
          <div>
            <p className="eyebrow">Market feedback</p>
            <h2 id="market-insights-heading">Market Insights</h2>
            <p>Turn job-search evidence into clear opportunities and next actions.</p>
          </div>
          <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>
            {loading ? "Refreshing…" : "Refresh view"}
          </button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </section>

      {!data ? (
        <section className="panel"><p role="status">{loading ? "Loading market insights…" : "No market insights loaded."}</p></section>
      ) : (
        <>
          <section className="market-summary-grid market-summary-grid-compact" aria-label="Market intelligence status">
            <article className="market-card"><span>Analysis</span><strong>{data.freshness.needs_analysis ? "Update available" : "Up to date"}</strong></article>
            <article className="market-card"><span>Jobs observed</span><strong>{data.evidence_provenance.observation_count}</strong></article>
            <article className="market-card"><span>Unique roles</span><strong>{data.evidence_provenance.canonical_role_count}</strong></article>
            <article className="market-card"><span>Last updated</span><strong>{data.freshness.ai_updated_at ? new Date(data.freshness.ai_updated_at).toLocaleDateString() : "Not yet"}</strong></article>
          </section>

          {data.freshness.needs_analysis && (
            <section className="market-update-notice" role="status">
              <div>
                <strong>Market analysis needs an update</strong>
                <span>New job evidence is available. Update the analysis from Settings & Data when convenient.</span>
              </div>
            </section>
          )}

          <section className="market-insight-dashboard">
            <InsightSection title="What this means now" data={data.market_summary} empty="No market summary yet." />
            <InsightSection title="Skills & gaps" data={data.skills_gap_summary} empty="No skills-gap summary yet." />
            <InsightSection title="Search strategy" data={data.capture_strategy} empty="No search-strategy summary yet." />
            <InsightSection title="Application strategy" data={data.application_strategy} empty="No application-strategy summary yet." />
            <InsightSection title="Profile actions" data={data.profile_strategy} empty="No profile actions yet." />
            <section className="market-card market-ranking-card market-recommendation-summary">
              <h3>Recommendations</h3>
              {data.recommendations.length === 0 ? (
                <p>No pending market recommendations.</p>
              ) : (
                <ul>
                  {data.recommendations.slice(0, 5).map((item) => (
                    <li key={`${item.entity_type}-${item.entity_id}`}>
                      <strong>{primitiveValue(item.payload.title ?? readable(item.feedback_type))}</strong>
                      {item.payload.proposed_action != null && <span>{primitiveValue(item.payload.proposed_action)}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </section>

          <details className="market-evidence-details">
            <summary>
              Evidence & provenance
              <span>
                {data.evidence_provenance.observation_count} observations · {data.evidence_provenance.canonical_role_count} roles
              </span>
            </summary>
            <div>
              <p>
                {data.evidence_provenance.capture_run_count} search runs · {data.evidence_provenance.duplicate_observation_count} repeated observations
              </p>
              <p>
                Oldest {data.evidence_provenance.oldest_evidence_at ? new Date(data.evidence_provenance.oldest_evidence_at).toLocaleDateString() : "—"}
                {" · "}
                Newest {data.evidence_provenance.newest_evidence_at ? new Date(data.evidence_provenance.newest_evidence_at).toLocaleDateString() : "—"}
              </p>
            </div>
          </details>
        </>
      )}
    </main>
  );}
