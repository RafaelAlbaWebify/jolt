import { useCallback, useEffect, useMemo, useState } from "react";

type Metric = { label: string; count: number };
type SalaryMention = { title: string; company: string; mention: string };
type LearningSignal = {
  skill: string;
  demand: number;
  required_count: number;
  preferred_count: number;
  gap_count: number;
  average_fit_shortfall_proxy: number | null;
  role_family_count: number;
  role_family_split: Metric[];
  capability_state: "covered" | "partial" | "missing" | "unknown";
  interview_signal: "High" | "Medium" | "Low";
  preparation_hours: number | null;
  trend: string;
  evidence_priority_indicator: number;
};

type LearningRefresh = {
  baseline_label: string;
  baseline_at: string;
  jobs_since_baseline: number;
  days_since_baseline: number;
  refresh_due: boolean;
  trigger_reasons: string[];
  policy: string;
};

type ScopeData = {
  total_roles: number;
  role_families: Metric[];
  work_modes: Metric[];
  seniority: Metric[];
  top_companies: Metric[];
  top_locations: Metric[];
  top_skills: Metric[];
  required_skills: Metric[];
  preferred_skills: Metric[];
  mentioned_skills: Metric[];
  learning_signals: LearningSignal[];
  learning_signal_explanation: string;
  salary_mentions: SalaryMention[];
  salary_role_count: number;
  salary_coverage: number;
  salary_coverage_percent: number;
};
type Timeframe = "all" | "last_7_days" | "last_30_days";
type SourceScope = "all" | "capture_batches" | "manual_intake";
type EvidenceProvenance = {
  source_posting_count: number;
  canonical_role_count: number;
  duplicate_member_count: number;
  oldest_evidence_at: string | null;
  newest_evidence_at: string | null;
};
type MarketData = {
  filters?: { timeframe: Timeframe; source_scope: SourceScope };
  evidence_provenance: EvidenceProvenance;
  learning_refresh: LearningRefresh;
  total_unique_roles: number;
  target_role_count: number;
  outside_target_count: number;
  target: ScopeData;
  all: ScopeData;
  outside_title_examples: Metric[];
  fit_explanation: string;
};
type Scope = "target" | "all";
type MarketView = "overview" | "demand" | "learning" | "salary";
type Props = { apiBase: string; active: boolean };

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function Ranking({ title, items, empty }: { title: string; items: Metric[]; empty?: string }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="market-card market-ranking-card">
      <h3>{title}</h3>
      {items.length === 0 ? <p>{empty ?? "No evidence detected in this scope."}</p> : (
        <div className="market-ranking">
          {items.slice(0, 5).map((item) => (
            <div className="market-ranking-row" key={item.label}>
              <div><strong>{readable(item.label)}</strong><span>{item.count}</span></div>
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
  const [view, setView] = useState<MarketView>("overview");
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

  return (
    <main className="market-intelligence" aria-labelledby="market-insights-heading">
      <section className="panel market-control-panel">
        <div className="section-heading market-heading-row">
          <div>
            <p className="eyebrow">Search strategy evidence</p>
            <h2 id="market-insights-heading">Market Insights</h2>
            <p>Use retained job evidence to inspect role mix, demand signals, and salary evidence.</p>
          </div>
          <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>{loading ? "Refreshing…" : "Refresh insights"}</button>
        </div>

        <div className="market-filter-row">
          <div className="market-filters" aria-label="Market insight filters">
            <label>Timeframe<select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}><option value="all">All retained evidence</option><option value="last_30_days">Last 30 days</option><option value="last_7_days">Last 7 days</option></select></label>
            <label>Source<select value={sourceScope} onChange={(event) => setSourceScope(event.target.value as SourceScope)}><option value="all">All sources</option><option value="capture_batches">Captured jobs</option><option value="manual_intake">Manual intake</option></select></label>
            <label>Scope<select value={scope} onChange={(event) => setScope(event.target.value as Scope)}><option value="target">Target roles</option><option value="all">All retained roles</option></select></label>
          </div>
          <div className="market-view-tabs" role="tablist" aria-label="Market insight views">
            <button type="button" role="tab" aria-selected={view === "overview"} className={view === "overview" ? "workspace-nav-active" : "secondary"} onClick={() => setView("overview")}>Overview</button>
            <button type="button" role="tab" aria-selected={view === "demand"} className={view === "demand" ? "workspace-nav-active" : "secondary"} onClick={() => setView("demand")}>Demand signals</button>
            <button type="button" role="tab" aria-selected={view === "learning"} className={view === "learning" ? "workspace-nav-active" : "secondary"} onClick={() => setView("learning")}>Learning signals</button>
            <button type="button" role="tab" aria-selected={view === "salary"} className={view === "salary" ? "workspace-nav-active" : "secondary"} onClick={() => setView("salary")}>Salary evidence</button>
          </div>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {lastRefreshedAt && <p className="market-refresh-note">Last refreshed {new Date(lastRefreshedAt).toLocaleString()}.</p>}
      </section>

      {!current ? <section className="panel"><p role="status">{loading ? "Loading market evidence…" : "No market evidence loaded."}</p></section> : (
        <section className="market-view-panel" aria-live="polite">
          {view === "overview" && (
            <div role="tabpanel" aria-label="Overview">
              <section className="market-summary-grid" aria-label="Market summary">
                <article className="market-card"><span>Roles in scope</span><strong>{current.total_roles}</strong></article>
                <article className="market-card"><span>Salary evidence</span><strong>{current.salary_role_count} / {current.total_roles} · {current.salary_coverage_percent}%</strong></article>
              </section>
              <div className="market-overview-grid">
                <section className="market-card market-ranking-card">
                  <h3>Evidence provenance</h3>
                  <p>{data?.evidence_provenance.source_posting_count ?? 0} retained observations · {data?.evidence_provenance.canonical_role_count ?? 0} canonical roles · {data?.evidence_provenance.duplicate_member_count ?? 0} duplicate observations</p>
                  <p>
                    Oldest evidence: {data?.evidence_provenance.oldest_evidence_at ? new Date(data.evidence_provenance.oldest_evidence_at).toLocaleDateString() : "None"}
                    {" · "}
                    Newest evidence: {data?.evidence_provenance.newest_evidence_at ? new Date(data.evidence_provenance.newest_evidence_at).toLocaleDateString() : "None"}
                  </p>
                </section>
                <Ranking title="Role families" items={current.role_families} />
              </div>
            </div>
          )}

          {view === "demand" && (
            <div className="market-demand-grid" role="tabpanel" aria-label="Demand signals">
              <Ranking title="Work modes" items={current.work_modes} />
              <Ranking title="All skill mentions" items={current.top_skills} />
              <Ranking title="Explicitly required skills" items={current.required_skills} />
              <Ranking title="Explicitly preferred skills" items={current.preferred_skills} />
              <Ranking title="Other skill mentions" items={current.mentioned_skills} />
              <Ranking title="Locations" items={current.top_locations} />
              <Ranking title="Seniority" items={current.seniority} />
              <Ranking title="Companies" items={current.top_companies} />
            </div>
          )}

          {view === "learning" && (
            <div role="tabpanel" aria-label="Learning signals" className="market-learning-panel">
              <section className="market-card market-learning-baseline">
                <div>
                  <p className="eyebrow">Adaptive market baseline</p>
                  <h3>{data?.learning_refresh.baseline_label ?? "Market baseline"}</h3>
                  <p>{data?.learning_refresh.policy}</p>
                </div>
                <div className="market-learning-refresh-stats">
                  <span><strong>{data?.learning_refresh.jobs_since_baseline ?? 0}</strong> new relevant jobs</span>
                  <span><strong>{data?.learning_refresh.days_since_baseline ?? 0}</strong> days</span>
                  <span><strong>{data?.learning_refresh.refresh_due ? "Due" : "Current"}</strong> refresh</span>
                </div>
              </section>

              <section className="market-card">
                <h3>Learning evidence</h3>
                <p>{current.learning_signal_explanation}</p>
              </section>

              {current.learning_signals.length === 0 ? (
                <section className="market-card"><p>No learning evidence is available in this scope.</p></section>
              ) : (
                <div className="market-learning-table-wrap">
                  <table className="market-learning-table">
                    <thead>
                      <tr>
                        <th>Skill</th>
                        <th>Demand</th>
                        <th>Required</th>
                        <th>Preferred</th>
                        <th>Gap</th>
                        <th>Fit shortfall*</th>
                        <th>Roles helped</th>
                        <th>Capability</th>
                        <th>Interview signal</th>
                        <th>Prep</th>
                        <th>Trend</th>
                        <th>Evidence indicator</th>
                      </tr>
                    </thead>
                    <tbody>
                      {current.learning_signals.map((item) => (
                        <tr key={item.skill}>
                          <td><strong>{item.skill}</strong></td>
                          <td>{item.demand}</td>
                          <td>{item.required_count}</td>
                          <td>{item.preferred_count}</td>
                          <td>{item.gap_count}</td>
                          <td>{item.average_fit_shortfall_proxy == null ? "—" : `-${item.average_fit_shortfall_proxy}`}</td>
                          <td title={item.role_family_split.map((part) => `${part.label}: ${part.count}`).join(" · ")}>{item.role_family_count} families</td>
                          <td>{readable(item.capability_state)}</td>
                          <td>{item.interview_signal}</td>
                          <td>{item.preparation_hours == null ? "Evidence unavailable" : `${item.preparation_hours}h`}</td>
                          <td>{item.trend === "baseline" ? "Baseline" : readable(item.trend)}</td>
                          <td><strong>{item.evidence_priority_indicator.toFixed(1)} / 10</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="market-learning-footnote">
                    * Fit shortfall is the average distance to JOLT's 80-point technical-fit threshold for opportunities where saved gap evidence names that skill. It is not presented as a causal per-skill penalty.
                  </p>
                </div>
              )}
            </div>
          )}

          {view === "salary" && (
            <div role="tabpanel" aria-label="Salary evidence" className="market-salary-panel">
              <div className="market-salary-heading"><div><h3>Salary mentions</h3><p>{current.salary_role_count} of {current.total_roles} roles ({current.salary_coverage_percent}%) contain salary evidence.</p></div></div>
              {current.salary_mentions.length === 0 ? <p>No salary evidence in this scope.</p> : (
                <div className="market-salary-grid">
                  {current.salary_mentions.slice(0, 9).map((item, index) => <article className="market-card" key={`${item.title}-${index}`}><strong>{item.title}</strong><span>{item.company}</span><p>{item.mention}</p></article>)}
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
