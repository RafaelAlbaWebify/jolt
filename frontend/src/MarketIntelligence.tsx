import { useCallback, useEffect, useRef, useState } from "react";

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
type MarketData = {
  total_unique_roles: number;
  target_role_count: number;
  outside_target_count: number;
  target: ScopeData;
  all: ScopeData;
  outside_title_examples: Metric[];
  fit_explanation: string;
};

type Props = { apiBase: string; active: boolean };
type Scope = "target" | "all";

function Ranking({ title, items, empty }: { title: string; items: Metric[]; empty?: string }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="market-card">
      <h3>{title}</h3>
      {items.length === 0 ? <p>{empty ?? "No evidence detected in this scope."}</p> : (
        <div className="market-ranking">
          {items.map((item) => (
            <div className="market-ranking-row" key={item.label}>
              <div><strong>{item.label}</strong><span>{item.count}</span></div>
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const hasActivatedRef = useRef(false);

  const load = useCallback(async () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/market-intelligence`, { signal: controller.signal });
      if (!response.ok) throw new Error("Unable to load market intelligence.");
      const loaded = (await response.json()) as MarketData;
      if (requestRef.current !== controller) return;
      setData(loaded);
      setLastRefreshedAt(new Date().toISOString());
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      if (requestRef.current === controller) {
        setError(caught instanceof Error ? caught.message : "Market intelligence failed.");
      }
    } finally {
      if (requestRef.current === controller) setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (!active || hasActivatedRef.current) return;
    hasActivatedRef.current = true;
    void load();
  }, [active, load]);

  useEffect(() => () => requestRef.current?.abort(), []);

  const selected = data?.[scope] ?? null;

  return (
    <section className="panel market-workspace" aria-labelledby="market-heading">
      <div className="section-heading market-heading">
        <div>
          <p className="eyebrow">Market intelligence</p>
          <h2 id="market-heading">Market</h2>
          <p>Separate your target market from search noise, then focus applications and study effort.</p>
          {lastRefreshedAt && <p className="market-refreshed">Last refreshed {new Date(lastRefreshedAt).toLocaleString()}</p>}
        </div>
        <div className="market-heading-actions">
          <button type="button" className="secondary" disabled={!active || loading} onClick={() => void load()}>
            {loading ? "Refreshing…" : data ? "Refresh market" : "Load market"}
          </button>
          {data && (
            <div className="market-scope" aria-label="Market scope">
              <button type="button" className={scope === "target" ? "filter-active" : "secondary"} onClick={() => setScope("target")}>Target roles ({data.target_role_count})</button>
              <button type="button" className={scope === "all" ? "filter-active" : "secondary"} onClick={() => setScope("all")}>All captured ({data.total_unique_roles})</button>
            </div>
          )}
        </div>
      </div>

      {loading && !data && <p role="status">Loading market intelligence…</p>}
      {error && (
        <div className="market-load-error">
          <p className="error" role="alert">{error}</p>
          <button type="button" className="secondary" disabled={loading || !active} onClick={() => void load()}>Retry market load</button>
        </div>
      )}
      {data && selected && (
        <>
          <div className="market-summary">
            <div><strong>{selected.total_roles}</strong><span>{scope === "target" ? "Target roles" : "Captured roles"}</span></div>
            <div><strong>{selected.strong_roles}</strong><span>Strong matches</span></div>
            <div><strong>{selected.viable_roles}</strong><span>Strong or viable</span></div>
            <div><strong>{selected.salary_coverage}</strong><span>With salary evidence</span></div>
          </div>

          <div className="market-guidance">
            <strong>How to read fit</strong>
            <p>{data.fit_explanation}</p>
            {scope === "target" && <p><strong>{data.outside_target_count}</strong> captured roles are outside your target path and are excluded from this view.</p>}
          </div>

          <div className="market-grid">
            <Ranking title="Target role families" items={selected.role_families} />
            <Ranking title="Work mode" items={selected.work_modes} />
            <Ranking title="Fit distribution" items={selected.fit_distribution} />
            <Ranking title="Most requested skills" items={selected.top_skills} />
            <Ranking title="Most common capability gaps" items={selected.top_gaps} empty="No strategy-profile gaps were found in this scope." />
            <Ranking title="Highest-return study topics" items={selected.study_priorities} empty="No preparation topics were generated for this scope." />
            <Ranking title="Seniority" items={selected.seniority} />
            <Ranking title="Companies hiring repeatedly" items={selected.top_companies.filter((item) => item.count > 1)} empty="No employer appears more than once in this scope." />
            <Ranking title="Top locations" items={selected.top_locations} />
          </div>

          {scope === "target" && (
            <Ranking title="Outside-target titles to remove from future searches" items={data.outside_title_examples} empty="No outside-target captures were detected." />
          )}

          <section className="market-card market-salary">
            <div className="market-card-heading">
              <h3>Salary evidence</h3>
              <span>{selected.salary_coverage} of {selected.total_roles} roles contain detectable salary text</span>
            </div>
            {selected.salary_mentions.length === 0 ? (
              <p>No salary ranges were detected. JOLT does not estimate missing salaries.</p>
            ) : (
              <div className="market-salary-list">
                {selected.salary_mentions.map((item, index) => (
                  <div key={`${item.title}-${item.company}-${index}`}>
                    <strong>{item.mention}</strong>
                    <span>{item.title} · {item.company}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
