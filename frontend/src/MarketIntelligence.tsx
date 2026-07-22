import { useEffect, useState } from "react";

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

type Props = { apiBase: string };
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

export function MarketIntelligence({ apiBase }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
  const [scope, setScope] = useState<Scope>("target");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch(`${apiBase}/api/market-intelligence`)
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load market intelligence.");
        return response.json() as Promise<MarketData>;
      })
      .then((loaded) => { if (!cancelled) setData(loaded); })
      .catch((caught) => { if (!cancelled) setError(caught instanceof Error ? caught.message : "Market intelligence failed."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiBase]);

  const selected = data?.[scope] ?? null;

  return (
    <section className="panel market-workspace" aria-labelledby="market-heading">
      <div className="section-heading market-heading">
        <div>
          <p className="eyebrow">Capture-derived intelligence</p>
          <h2 id="market-heading">Market intelligence</h2>
          <p>Separate your target market from search noise, then focus applications and study effort.</p>
        </div>
        {data && (
          <div className="market-scope" aria-label="Market scope">
            <button type="button" className={scope === "target" ? "filter-active" : "secondary"} onClick={() => setScope("target")}>Target roles ({data.target_role_count})</button>
            <button type="button" className={scope === "all" ? "filter-active" : "secondary"} onClick={() => setScope("all")}>All captured ({data.total_unique_roles})</button>
          </div>
        )}
      </div>

      {loading && <p role="status">Loading market intelligence…</p>}
      {error && <p className="error" role="alert">{error}</p>}
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
            <Ranking
              title="Outside-target titles to remove from future searches"
              items={data.outside_title_examples}
              empty="No outside-target captures were detected."
            />
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
