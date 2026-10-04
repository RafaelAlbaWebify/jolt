import { useCallback, useEffect, useMemo, useState } from "react";

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

type ApplicationIndexItem = {
  application_id?: string | null;
  application_status?: string | null;
  outcome_type?: string | null;
};

type MarketTab = "skills" | "search" | "applications" | "evidence";

type Props = { apiBase: string; active: boolean };

const INTERVIEW_STATUSES = new Set([
  "recruiter_screen",
  "technical_interview",
  "hiring_manager_interview",
  "final_interview",
]);

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function isTechnicalKey(value: string) {
  return /(^|_)(id|ids|uuid|uuids|posting_id|posting_ids|capture_run|source_job|processing_mode|evidence_refs?)($|_)/i.test(value);
}

function primitive(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function collectNarrativeSignals(source: unknown, limit: number, result: string[] = []): string[] {
  if (result.length >= limit || source == null) return result;

  if (typeof source === "string") {
    const text = source.trim();
    if (text && !result.includes(text)) result.push(text);
    return result;
  }

  if (Array.isArray(source)) {
    for (const item of source) {
      collectNarrativeSignals(item, limit, result);
      if (result.length >= limit) break;
    }
    return result;
  }

  if (typeof source === "object") {
    for (const [key, value] of Object.entries(source as Record<string, unknown>)) {
      if (isTechnicalKey(key) || /^(analyzed_at|reviewed_at|generated_at|as_of)$/i.test(key)) continue;
      collectNarrativeSignals(value, limit, result);
      if (result.length >= limit) break;
    }
  }

  return result;
}

function numericDecisionCount(data: Record<string, unknown>, key: string): number | null {
  const direct = data.decision_counts;
  if (direct && typeof direct === "object" && !Array.isArray(direct)) {
    const value = (direct as Record<string, unknown>)[key];
    return typeof value === "number" ? value : null;
  }
  return null;
}

function recommendationTitle(item: FeedbackItem) {
  return primitive(item.payload.title) || readable(item.feedback_type);
}

function recommendationAction(item: FeedbackItem) {
  return primitive(item.payload.proposed_action) || primitive(item.payload.rationale);
}

function formatDate(value: string | null) {
  if (!value) return "Not yet";
  return new Date(value).toLocaleDateString();
}

function StrategyRows({ data, empty }: { data: Record<string, unknown>; empty: string }) {
  const entries = Object.entries(data)
    .filter(([key]) => !isTechnicalKey(key))
    .slice(0, 6);

  if (entries.length === 0) return <p>{empty}</p>;

  return (
    <div className="market-pro-strategy-list">
      {entries.map(([key, value]) => {
        const text = Array.isArray(value)
          ? value.map(primitive).filter(Boolean).join(" · ")
          : typeof value === "object" && value !== null
            ? collectNarrativeSignals(value, 3).join(" · ")
            : primitive(value);
        return (
          <div key={key}>
            <span>{readable(key)}</span>
            <strong>{text || "—"}</strong>
          </div>
        );
      })}
    </div>
  );
}

export function MarketIntelligence({ apiBase, active }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
  const [applications, setApplications] = useState<ApplicationIndexItem[]>([]);
  const [activeTab, setActiveTab] = useState<MarketTab>("skills");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!active) return;
    setLoading(true);
    setError("");
    try {
      const [marketResponse, applicationResponse] = await Promise.all([
        fetch(`${apiBase}/api/ai-market/view`, { signal }),
        fetch(`${apiBase}/api/application-index`, { signal }),
      ]);
      if (!marketResponse.ok) throw new Error("Unable to load market intelligence.");
      setData(await marketResponse.json() as MarketData);
      if (applicationResponse.ok) {
        setApplications(await applicationResponse.json() as ApplicationIndexItem[]);
      } else {
        setApplications([]);
      }
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

  const metrics = useMemo(() => {
    if (!data) return null;
    const strong = numericDecisionCount(data.market_summary, "strong_pursue") ?? 0;
    const pursue = numericDecisionCount(data.market_summary, "pursue") ?? 0;
    const hasDecisionCounts = data.market_summary.decision_counts != null;
    const activeApplications = applications.filter((item) => Boolean(item.application_id));
    const interviewing = activeApplications.filter((item) =>
      item.application_status ? INTERVIEW_STATUSES.has(item.application_status) : false
    );
    return {
      goodMatches: hasDecisionCounts ? strong + pursue : null,
      applications: activeApplications.length,
      interviewing: interviewing.length,
    };
  }, [applications, data]);

  const marketSignals = useMemo(
    () => data ? collectNarrativeSignals(data.market_summary, 3) : [],
    [data],
  );

  const nextActions = useMemo(() => {
    if (!data) return [];
    if (data.recommendations.length > 0) {
      return data.recommendations.slice(0, 3).map((item) => ({
        title: recommendationTitle(item),
        detail: recommendationAction(item),
      }));
    }

    return [
      ...collectNarrativeSignals(data.application_strategy, 1),
      ...collectNarrativeSignals(data.capture_strategy, 1),
      ...collectNarrativeSignals(data.profile_strategy, 1),
    ].slice(0, 3).map((text) => ({ title: text, detail: "" }));
  }, [data]);

  return (
    <main className="market-pro" aria-labelledby="market-insights-heading">
      <section className="market-pro-header">
        <div>
          <p className="eyebrow">Market feedback</p>
          <h2 id="market-insights-heading">Market Insights</h2>
          <p>What is working in your job search — and what to change next.</p>
        </div>
        <div className="market-pro-header-actions">
          <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>
            {loading ? "Refreshing…" : "Refresh view"}
          </button>
          <span>Last updated: {formatDate(data?.freshness.ai_updated_at ?? null)}</span>
        </div>
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      {!data ? (
        <section className="panel">
          <p role="status">{loading ? "Loading market insights…" : "No market insights loaded."}</p>
        </section>
      ) : (
        <>
          <section className="market-pro-kpis" aria-label="Market overview metrics">
            <article>
              <span className="market-pro-kpi-icon">▤</span>
              <div><span>Jobs analyzed</span><strong>{data.evidence_provenance.observation_count.toLocaleString()}</strong><small>Total captured observations</small></div>
            </article>
            <article>
              <span className="market-pro-kpi-icon market-pro-kpi-good">◎</span>
              <div><span>Good matches</span><strong>{metrics?.goodMatches ?? "—"}</strong><small>{metrics?.goodMatches == null ? "Awaiting decision counts" : "Strong + good fit"}</small></div>
            </article>
            <article>
              <span className="market-pro-kpi-icon market-pro-kpi-apps">▣</span>
              <div><span>Applications</span><strong>{metrics?.applications ?? 0}</strong><small>Tracked in Applications</small></div>
            </article>
            <article>
              <span className="market-pro-kpi-icon market-pro-kpi-interview">●</span>
              <div><span>Interviewing</span><strong>{metrics?.interviewing ?? 0}</strong><small>Currently in interview stages</small></div>
            </article>
          </section>

          {data.freshness.needs_analysis && (
            <section className="market-pro-update" role="status">
              <div>
                <strong>Market analysis needs an update</strong>
                <span>New job evidence is available. Export the current intelligence package, review it with ChatGPT, then import the returned update.</span>
              </div>
              <a
                className="secondary"
                href={`${apiBase}/api/ai-work-package/export`}
                download="JOLT_AI_WORK_PACKAGE.json"
              >
                Download intelligence package
              </a>
            </section>
          )}

          <section className="market-pro-main-grid">
            <article className="market-pro-panel market-pro-signals">
              <header><span>▥</span><h3>What the market is telling you</h3></header>
              {marketSignals.length === 0 ? (
                <p>No market signals are stored yet.</p>
              ) : (
                <div className="market-pro-signal-list">
                  {marketSignals.map((signal, index) => (
                    <div key={signal}>
                      <span className="market-pro-signal-number">{index + 1}</span>
                      <strong>{signal}</strong>
                      <small>Market signal</small>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="market-pro-panel market-pro-actions">
              <header><span>☷</span><h3>What to do next</h3></header>
              {nextActions.length === 0 ? (
                <p>No pending recommendations.</p>
              ) : (
                <div className="market-pro-action-list">
                  {nextActions.map((action, index) => (
                    <div key={`${action.title}-${index}`}>
                      <span>{index + 1}</span>
                      <div><strong>{action.title}</strong>{action.detail && <small>{action.detail}</small>}</div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </section>

          <nav className="market-pro-tabs" aria-label="Market insight sections">
            {([
              ["skills", "Skills & demand"],
              ["search", "Search performance"],
              ["applications", "Application performance"],
              ["evidence", "Evidence"],
            ] as Array<[MarketTab, string]>).map(([value, label]) => (
              <button
                type="button"
                key={value}
                className={activeTab === value ? "active" : ""}
                aria-pressed={activeTab === value}
                onClick={() => setActiveTab(value)}
              >
                {label}
              </button>
            ))}
          </nav>

          <section className="market-pro-detail">
            {activeTab === "skills" && (
              <div className="market-pro-detail-grid">
                <article className="market-pro-detail-card">
                  <header><span>▥</span><h3>Skills & demand signals</h3></header>
                  <StrategyRows data={data.skills_gap_summary} empty="No skills-gap analysis is stored yet." />
                </article>
                <article className="market-pro-detail-card">
                  <header><span>!</span><h3>Profile actions</h3></header>
                  <StrategyRows data={data.profile_strategy} empty="No profile actions are stored yet." />
                </article>
              </div>
            )}

            {activeTab === "search" && (
              <div className="market-pro-detail-grid">
                <article className="market-pro-detail-card">
                  <header><span>⌕</span><h3>Search strategy</h3></header>
                  <StrategyRows data={data.capture_strategy} empty="No search-strategy guidance is stored yet." />
                </article>
                <article className="market-pro-detail-card market-pro-evidence-summary">
                  <header><span>▤</span><h3>Search evidence</h3></header>
                  <dl>
                    <div><dt>Observations</dt><dd>{data.evidence_provenance.observation_count.toLocaleString()}</dd></div>
                    <div><dt>Unique roles</dt><dd>{data.evidence_provenance.canonical_role_count.toLocaleString()}</dd></div>
                    <div><dt>Search runs</dt><dd>{data.evidence_provenance.capture_run_count.toLocaleString()}</dd></div>
                    <div><dt>Repeated observations</dt><dd>{data.evidence_provenance.duplicate_observation_count.toLocaleString()}</dd></div>
                  </dl>
                </article>
              </div>
            )}

            {activeTab === "applications" && (
              <div className="market-pro-detail-grid">
                <article className="market-pro-detail-card">
                  <header><span>▣</span><h3>Application strategy</h3></header>
                  <StrategyRows data={data.application_strategy} empty="No application-strategy guidance is stored yet." />
                </article>
                <article className="market-pro-detail-card market-pro-evidence-summary">
                  <header><span>◎</span><h3>Current pipeline</h3></header>
                  <dl>
                    <div><dt>Applications</dt><dd>{metrics?.applications ?? 0}</dd></div>
                    <div><dt>Interviewing</dt><dd>{metrics?.interviewing ?? 0}</dd></div>
                    <div><dt>Good matches</dt><dd>{metrics?.goodMatches ?? "—"}</dd></div>
                    <div><dt>Analysis</dt><dd>{data.freshness.needs_analysis ? "Update available" : "Up to date"}</dd></div>
                  </dl>
                </article>
              </div>
            )}

            {activeTab === "evidence" && (
              <article className="market-pro-detail-card market-pro-evidence-wide">
                <header><span>▤</span><h3>Evidence & provenance</h3></header>
                <div className="market-pro-evidence-strip">
                  <div><strong>{data.evidence_provenance.observation_count.toLocaleString()}</strong><span>observations</span></div>
                  <div><strong>{data.evidence_provenance.canonical_role_count.toLocaleString()}</strong><span>unique roles</span></div>
                  <div><strong>{data.evidence_provenance.capture_run_count.toLocaleString()}</strong><span>search runs</span></div>
                  <div><strong>{formatDate(data.evidence_provenance.oldest_evidence_at)}</strong><span>oldest evidence</span></div>
                  <div><strong>{formatDate(data.evidence_provenance.newest_evidence_at)}</strong><span>newest evidence</span></div>
                </div>
                <p>{data.freshness.reason}</p>
              </article>
            )}
          </section>
        </>
      )}
    </main>
  );
}
