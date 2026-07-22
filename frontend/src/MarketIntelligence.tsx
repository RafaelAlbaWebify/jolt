import { useEffect, useState } from "react";

type Metric = { label: string; count: number };
type SalaryMention = { title: string; company: string; mention: string };
type MarketData = {
  total_unique_roles: number;
  role_families: Metric[];
  work_modes: Metric[];
  seniority: Metric[];
  top_companies: Metric[];
  top_locations: Metric[];
  top_skills: Metric[];
  fit_distribution: Metric[];
  salary_mentions: SalaryMention[];
  salary_coverage: number;
};

type Props = { apiBase: string };

function Ranking({ title, items }: { title: string; items: Metric[] }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="market-card">
      <h3>{title}</h3>
      <div className="market-ranking">
        {items.map((item) => (
          <div className="market-ranking-row" key={item.label}>
            <div><strong>{item.label}</strong><span>{item.count}</span></div>
            <div className="market-bar"><span style={{ width: `${(item.count / maximum) * 100}%` }} /></div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function MarketIntelligence({ apiBase }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
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

  return (
    <section className="panel market-workspace" aria-labelledby="market-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Capture-derived intelligence</p>
          <h2 id="market-heading">Market intelligence</h2>
          <p>Use the captured market to focus applications, positioning, and study effort.</p>
        </div>
      </div>

      {loading && <p role="status">Loading market intelligence…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {data && (
        <>
          <div className="market-summary">
            <div><strong>{data.total_unique_roles}</strong><span>Unique roles</span></div>
            <div><strong>{data.work_modes.find((item) => item.label === "Remote")?.count ?? 0}</strong><span>Remote roles</span></div>
            <div><strong>{data.fit_distribution.find((item) => item.label === "80–100")?.count ?? 0}</strong><span>High-fit roles</span></div>
            <div><strong>{data.salary_coverage}</strong><span>Roles with salary evidence</span></div>
          </div>

          <div className="market-grid">
            <Ranking title="Role families" items={data.role_families} />
            <Ranking title="Work mode" items={data.work_modes} />
            <Ranking title="Most requested skills" items={data.top_skills} />
            <Ranking title="Fit distribution" items={data.fit_distribution} />
            <Ranking title="Seniority" items={data.seniority} />
            <Ranking title="Companies hiring repeatedly" items={data.top_companies.filter((item) => item.count > 1)} />
            <Ranking title="Top locations" items={data.top_locations} />
          </div>

          <section className="market-card market-salary">
            <div className="market-card-heading">
              <h3>Salary evidence</h3>
              <span>{data.salary_coverage} of {data.total_unique_roles} roles contain detectable salary text</span>
            </div>
            {data.salary_mentions.length === 0 ? (
              <p>No salary ranges were detected. JOLT does not estimate missing salaries.</p>
            ) : (
              <div className="market-salary-list">
                {data.salary_mentions.map((item, index) => (
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
