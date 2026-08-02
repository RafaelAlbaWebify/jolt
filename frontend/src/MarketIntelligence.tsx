import { useCallback, useEffect, useMemo, useState } from "react";

type Metric = { label: string; count: number };
type SalaryMention = { title: string; company: string; mention: string };
type ScopeData = {
  total_roles: number;
  strong_roles: number;
  viable_roles: number;
  role_families: Metric[];
  work_modes: Metric[];
  seniority: Metric[];
  top_companies: Metric[];
  top_locations: Metric[];
  top_skills: Metric[];
  fit_distribution: Metric[];
  top_gaps: Metric[];
  study_priorities: Metric[];
  salary_mentions: SalaryMention[];
  salary_coverage: number;
};
type Timeframe = "all" | "last_7_days" | "last_30_days";
type SourceScope = "all" | "capture_batches" | "manual_intake";
type MarketData = {
  filters?: { timeframe: Timeframe; source_scope: SourceScope };
  total_unique_roles: number;
  target_role_count: number;
  outside_target_count: number;
  target: ScopeData;
  all: ScopeData;
  outside_title_examples: Metric[];
  fit_explanation: string;
};
type Scope = "target" | "all";
type Props = { apiBase: string; active: boolean };

function Ranking({ title, items, empty }: { title: string; items: Metric[]; empty?: string }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="market-card">
      <h3>{title}</h3>
      {items.length === 0 ? <p>{empty ?? "No evidence detected in this scope."}</p> : (
        <div className="market-ranking">
          {items.slice(0, 10).map((item) => (
            <div className="market-ranking-row" key={item.label}>
              <div><strong>{item.label.replaceAll("_", " ")}</strong><span>{item.count}</span></div>
              <div className="market-bar"><span style={{ width: `${(item.count / maximum) * 100}%` }} /></div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function MarketIntelligence({ apiBase, active }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
  const [scope, setScope] = useState<Scope>("target");
  const [timeframe, setTimeframe] = useState<Timeframe>("all");
  const [sourceScope, setSourceScope] = useState<SourceScope>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!active) return;
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ timeframe, source_scope: sourceScope });
      const response = await fetch(`${apiBase}/api/market-intelligence?${params.toString()}`, { signal });
      if (!response.ok) throw new Error("Unable to load market insights.");
      setData(await response.json() as MarketData);
      setLastRefreshedAt(new Date().toISOString());
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(caught instanceof Error ? caught.message : "Market insights failed.");
    } finally {
      setLoading(false);
    }
  }, [active, apiBase, sourceScope, timeframe]);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [active, load]);

  const current = useMemo(() => scope === "target" ? data?.target : data?.all, [data, scope]);
  const strongest = current?.top_skills.slice(0, 3) ?? [];
  const priorities = current?.study_priorities.length ? current.study_priorities : current?.top_gaps ?? [];

  return (
    <main className="market-intelligence" aria-labelledby="market-insights-heading">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Search strategy evidence</p>
            <h2 id="market-insights-heading">Market Insights</h2>
            <p>Only retained job evidence is analysed here. Use it to change search scope, preparation priorities, or application decisions.</p>
          </div>
          <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>{loading ? "Refreshing…" : "Refresh insights"}</button>
        </div>

        <div className="market-filters" aria-label="Market insight filters">
          <label>Timeframe<select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}><option value="all">All retained evidence</option><option value="last_30_days">Last 30 days</option><option value="last_7_days">Last 7 days</option></select></label>
          <label>Source<select value={sourceScope} onChange={(event) => setSourceScope(event.target.value as SourceScope)}><option value="all">All sources</option><option value="capture_batches">Captured jobs</option><option value="manual_intake">Manual intake</option></select></label>
          <label>Scope<select value={scope} onChange={(event) => setScope(event.target.value as Scope)}><option value="target">Target roles</option><option value="all">All retained roles</option></select></label>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {lastRefreshedAt && <p className="market-refresh-note">Last refreshed {new Date(lastRefreshedAt).toLocaleString()}.</p>}
      </section>

      {!current ? <section className="panel"><p role="status">{loading ? "Loading market evidence…" : "No market evidence loaded."}</p></section> : (
        <>
          <section className="market-summary-grid" aria-label="Market summary">
            <article className="market-card"><span>Roles in scope</span><strong>{current.total_roles}</strong></article>
            <article className="market-card"><span>Strong fit</span><strong>{current.strong_roles}</strong></article>
            <article className="market-card"><span>Viable fit</span><strong>{current.viable_roles}</strong></article>
            <article className="market-card"><span>Salary evidence</span><strong>{Math.round(current.salary_coverage * 100)}%</strong></article>
          </section>

          <section className="panel">
            <div className="section-heading"><div><h3>What to do next</h3><p>{data?.fit_explanation}</p></div></div>
            <div className="market-action-grid">
              <article className="market-card"><h3>Double down on</h3>{strongest.length ? <ul>{strongest.map((item) => <li key={item.label}>{item.label.replaceAll("_", " ")} ({item.count})</li>)}</ul> : <p>No repeated strength signal yet.</p>}</article>
              <article className="market-card"><h3>Prepare next</h3>{priorities.length ? <ol>{priorities.slice(0, 5).map((item) => <li key={item.label}>{item.label.replaceAll("_", " ")} ({item.count})</li>)}</ol> : <p>No repeated preparation gap yet.</p>}</article>
            </div>
          </section>

          <div className="market-grid">
            <Ranking title="Fit distribution" items={current.fit_distribution} />
            <Ranking title="Role families" items={current.role_families} />
            <Ranking title="Work modes" items={current.work_modes} />
            <Ranking title="Most requested skills" items={current.top_skills} />
            <Ranking title="Repeated blockers and gaps" items={current.top_gaps} />
            <Ranking title="Locations" items={current.top_locations} />
          </div>

          <section className="panel">
            <h3>Salary mentions</h3>
            {current.salary_mentions.length === 0 ? <p>No salary evidence in this scope.</p> : (
              <div className="professional-source-grid">
                {current.salary_mentions.slice(0, 12).map((item, index) => <article className="professional-source-card" key={`${item.title}-${index}`}><strong>{item.title}</strong><p>{item.company}</p><p>{item.mention}</p></article>)}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
