import { useCallback, useEffect, useState } from "react";

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

function displayValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function InsightSection({ title, data, empty }: { title: string; data: Record<string, unknown>; empty: string }) {
  const entries = Object.entries(data);
  return (
    <section className="market-card market-ranking-card">
      <h3>{title}</h3>
      {entries.length === 0 ? <p>{empty}</p> : (
        <dl className="market-ai-insights">
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{readable(key)}</dt>
              <dd>{Array.isArray(value) ? (
                <ul>{value.map((item, index) => <li key={`${key}-${index}`}>{displayValue(item)}</li>)}</ul>
              ) : displayValue(value)}</dd>
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
    <main className="market-intelligence" aria-labelledby="market-insights-heading">
      <section className="panel market-control-panel">
        <div className="section-heading market-heading-row">
          <div>
            <p className="eyebrow">ChatGPT reasoning · JOLT evidence</p>
            <h2 id="market-insights-heading">Market Insights</h2>
            <p>Market conclusions come from the latest imported AI analysis. JOLT supplies deterministic evidence and provenance.</p>
          </div>
          <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>{loading ? "Refreshing…" : "Refresh view"}</button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </section>

      {!data ? <section className="panel"><p role="status">{loading ? "Loading market intelligence…" : "No market intelligence loaded."}</p></section> : (
        <>
          <section className="market-summary-grid" aria-label="Market intelligence status">
            <article className="market-card"><span>Authority</span><strong>{data.authority === "chatgpt" ? "ChatGPT" : data.authority}</strong></article>
            <article className="market-card"><span>Analysis status</span><strong>{readable(data.freshness.status)}</strong></article>
            <article className="market-card"><span>Evidence observations</span><strong>{data.evidence_provenance.observation_count}</strong></article>
            <article className="market-card"><span>Canonical roles</span><strong>{data.evidence_provenance.canonical_role_count}</strong></article>
          </section>

          <section className="panel market-card">
            <h3>{data.freshness.needs_analysis ? "Market analysis needs refresh" : "Market analysis is current"}</h3>
            <p>{data.freshness.reason}</p>
            <p>
              Latest capture: {data.freshness.latest_capture_at ? new Date(data.freshness.latest_capture_at).toLocaleString() : "None"}
              {" · "}
              Latest AI context: {data.freshness.ai_updated_at ? new Date(data.freshness.ai_updated_at).toLocaleString() : "None"}
            </p>
            {data.freshness.needs_analysis && <p><strong>Next:</strong> export a new AI work package from Data tools, analyze it in ChatGPT, then import the returned AI update.</p>}
          </section>

          <section className="market-overview-grid">
            <section className="market-card market-ranking-card">
              <h3>Evidence provenance</h3>
              <p>{data.evidence_provenance.observation_count} observations · {data.evidence_provenance.canonical_role_count} canonical roles · {data.evidence_provenance.duplicate_observation_count} repeated observations · {data.evidence_provenance.capture_run_count} capture runs</p>
              <p>
                Oldest: {data.evidence_provenance.oldest_evidence_at ? new Date(data.evidence_provenance.oldest_evidence_at).toLocaleDateString() : "None"}
                {" · "}
                Newest: {data.evidence_provenance.newest_evidence_at ? new Date(data.evidence_provenance.newest_evidence_at).toLocaleDateString() : "None"}
              </p>
            </section>
            <InsightSection title="Market summary" data={data.market_summary} empty="No ChatGPT market summary has been imported yet." />
          </section>

          <section className="market-demand-grid">
            <InsightSection title="Skills & evidence gaps" data={data.skills_gap_summary} empty="No AI-derived skills-gap summary is available." />
            <InsightSection title="Capture strategy" data={data.capture_strategy} empty="No AI-derived capture strategy is available." />
            <InsightSection title="Application strategy" data={data.application_strategy} empty="No AI-derived application strategy is available." />
            <InsightSection title="Profile implications" data={data.profile_strategy} empty="No AI-derived profile strategy is available." />
          </section>

          <section className="panel market-card">
            <h3>Pending market recommendations</h3>
            {data.recommendations.length === 0 ? <p>No explicit recommendations in the latest market analysis.</p> : (
              <div className="market-recommendations">
                {data.recommendations.map((item) => (
                  <article className="market-card" key={`${item.entity_type}-${item.entity_id}`}>
                    <strong>{displayValue(item.payload.title ?? readable(item.feedback_type))}</strong>
                    {item.payload.rationale != null && <p>{displayValue(item.payload.rationale)}</p>}
                    {item.payload.proposed_action != null && <p><strong>Action:</strong> {displayValue(item.payload.proposed_action)}</p>}
                    {item.confidence != null && <span>Confidence {item.confidence}%</span>}
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
