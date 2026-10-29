import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
    verified_source_identities: number;
    verified_source_observations: number;
    verified_postings: number;
    verified_by_portal: Record<string, { identities: number; observations: number }>;
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

type AutomaticMarket = {
  total_unique_roles: number;
  target_role_count: number;
  evaluation_coverage: { evaluated_count: number; missing_count: number };
  all: { top_skills: Array<{ label: string; count: number }>; role_families: Array<{ label: string; count: number }> };
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

function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("The AI review file could not be read."));
    };
    reader.onerror = () => reject(new Error("The AI review file could not be read."));
    reader.readAsText(file);
  });
}

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

function marketNarrativeSignals(summary: Record<string, unknown>): string[] {
  const result: string[] = [];
  const add = (value: unknown) => {
    const text = primitive(value).trim();
    if (text && !result.includes(text)) result.push(text);
  };
  add(summary.executive_summary);
  const explicitSignals =
    summary.high_confidence_conclusions ??
    summary.high_confidence_signals ??
    summary.market_signals ??
    summary.signals;
  if (Array.isArray(explicitSignals)) {
    for (const signal of explicitSignals) {
      if (typeof signal === "string") add(signal);
      else if (signal && typeof signal === "object") {
        const item = signal as Record<string, unknown>;
        add(item.conclusion ?? item.signal ?? item.summary ?? item.title ?? item.description);
      }
      if (result.length >= 3) break;
    }
  }
  add(summary.interpretation);
  return result.slice(0, 3);
}

function strategyValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (typeof item === "string" || typeof item === "number") return String(item);
      if (!item || typeof item !== "object") return "";
      const row = item as Record<string, unknown>;
      const skill = primitive(row.skill ?? row.label ?? row.title ?? row.name);
      if (!skill) return "";
      const details = [
        row.capability_state ? `capability: ${primitive(row.capability_state)}` : "",
        row.demand != null ? `demand: ${primitive(row.demand)} roles` : "",
        (row.required_mentions ?? row.required_count) != null
          ? `required: ${primitive(row.required_mentions ?? row.required_count)}`
          : "",
        (row.preferred_mentions ?? row.preferred_count) != null
          ? `preferred: ${primitive(row.preferred_mentions ?? row.preferred_count)}`
          : "",
        (row.jolt_gap_signal ?? row.gap_count) != null
          ? `gap signal: ${primitive(row.jolt_gap_signal ?? row.gap_count)}`
          : "",
        row.count != null ? `count: ${primitive(row.count)}` : "",
      ].filter(Boolean);
      return details.length ? `${skill} — ${details.join("; ")}` : skill;
    }).filter(Boolean).join("\n");
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !isTechnicalKey(key) && !["evidence_refs", "source_context_version"].includes(key))
      .map(([key, item]) => {
        const text = primitive(item);
        return text ? `${readable(key)}: ${text}` : "";
      }).filter(Boolean).join("\n");
  }
  return primitive(value);
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
  const hiddenFields = new Set(["status", "evidence_refs", "source_context_version", "updated_at", "generated_at"]);
  const entries = Object.entries(data)
    .filter(([key]) => !isTechnicalKey(key) && !hiddenFields.has(key))
    .slice(0, 8);

  if (entries.length === 0) return <p>{empty}</p>;

  return (
    <div className="market-pro-strategy-list">
      {entries.map(([key, value]) => {
        const text = strategyValue(value);
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
  const [automatic, setAutomatic] = useState<AutomaticMarket | null>(null);
  const [automaticError, setAutomaticError] = useState("");
  const [activeTab, setActiveTab] = useState<MarketTab>("skills");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [importNotice, setImportNotice] = useState("");
  const importRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!active) return;
    setLoading(true);
    setError("");
    try {
      const [marketResponse, applicationResponse, automaticResponse] = await Promise.all([
        fetch(`${apiBase}/api/ai-market/view`, { signal }),
        fetch(`${apiBase}/api/application-index`, { signal }),
        fetch(`${apiBase}/api/ai-market/automatic`, { signal }),
      ]);
      if (!marketResponse.ok) throw new Error("Unable to load market intelligence.");
      setData(await marketResponse.json() as MarketData);
      if (automaticResponse.ok) {
        setAutomatic(await automaticResponse.json() as AutomaticMarket);
        setAutomaticError("");
      } else {
        setAutomatic(null);
        setAutomaticError("Automatic indicators are temporarily unavailable.");
      }
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

  const importReviewedUpdate = useCallback(async (file: File) => {
    setImporting(true);
    setError("");
    setImportNotice("");
    try {
      let payload: unknown;
      try {
        payload = JSON.parse(await readTextFile(file));
      } catch {
        throw new Error("The selected file is not valid JSON.");
      }

      const response = await fetch(`${apiBase}/api/ai-work-package/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const problem = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(problem?.detail || "The reviewed intelligence update could not be imported.");
      }

      setImportNotice("Reviewed intelligence update imported successfully.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The reviewed intelligence update could not be imported.");
    } finally {
      if (importRef.current) importRef.current.value = "";
      setImporting(false);
    }
  }, [apiBase, load]);

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
    () => data ? marketNarrativeSignals(data.market_summary) : [],
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

    const firstText = (source: Record<string, unknown>, keys: string[]) => {
      for (const key of keys) {
        const text = primitive(source[key]).trim();
        if (text) return text;
      }
      return "";
    };
    return [
      firstText(data.application_strategy, ["next_step", "priority", "recommendation"]),
      firstText(data.capture_strategy, ["next_experiment", "rule", "recommendation"]),
      firstText(data.profile_strategy, ["recommendation", "positioning"]),
    ].filter(Boolean).slice(0, 3).map((text) => ({ title: text, detail: "" }));
  }, [data]);

  return (
    <main className="market-pro" aria-labelledby="market-insights-heading">
      <section className="market-pro-header">
        <div>
          <p className="eyebrow">Market feedback</p>
          <h2 id="market-insights-heading">Market Insights</h2>
          <p>What is working in your job search — and what to change next.</p>
          {error && <p className="market-pro-notice market-pro-notice-error" role="alert">{error}</p>}
          {importNotice && (
            <div className="market-pro-notice market-pro-notice-success" role="status">
              <span>{importNotice}</span>
              <button type="button" className="market-pro-notice-dismiss" onClick={() => setImportNotice("")}>
                Dismiss
              </button>
            </div>
          )}
          {automaticError && <p className="market-pro-notice" role="status">{automaticError}</p>}
        </div>
        <div className="market-pro-header-actions">
          <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>
            {loading ? "Refreshing…" : "Refresh view"}
          </button>
          <span>Strategy updated: {formatDate(data?.freshness.ai_updated_at ?? null)}</span>
          <span>Latest evidence: {formatDate(data?.evidence_provenance.newest_evidence_at ?? null)}</span>
        </div>
      </section>

remove flow notices      {!data ? (
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
                <strong>ChatGPT strategic analysis needs an update</strong>
                <span>Automatic indicators remain available. Strategic recommendations require a separate ChatGPT review.</span>
              </div>
              <div className="button-row">
                <a
                  className="secondary"
                  href={`${apiBase}/api/ai-work-package/market-export`}
                  download="JOLT_MARKET_STRATEGY.json"
                >
                  Download strategic market package
                </a>
                <input
                  ref={importRef}
                  type="file"
                  accept="application/json,.json"
                  hidden
                  aria-label="Import reviewed intelligence update"
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    if (file) void importReviewedUpdate(file);
                  }}
                />
                <button
                  type="button"
                  className="secondary"
                  disabled={importing}
                  onClick={() => importRef.current?.click()}
                >
                  {importing ? "Importing…" : "Import reviewed update"}
                </button>
              </div>
            </section>
          )}

          <section className="market-pro-detail" aria-label="Automatic market indicators">
            <article className="market-pro-detail-card">
              <header><span>▤</span><h3>Automatic market indicators</h3></header>
              {automatic ? (
                <>
                  <p>Calculated from saved JOLT evidence. No ChatGPT import required.</p>
                  <dl className="market-pro-indicator-grid">
                    <div><dt>Unique roles</dt><dd>{automatic.total_unique_roles.toLocaleString()}</dd></div>
                    <div><dt>Target roles</dt><dd>{automatic.target_role_count.toLocaleString()}</dd></div>
                    <div><dt>Evaluated observations</dt><dd>{automatic.evaluation_coverage.evaluated_count.toLocaleString()}</dd></div>
                    <div><dt>Pending evaluation</dt><dd>{automatic.evaluation_coverage.missing_count.toLocaleString()}</dd></div>
                  </dl>
                  <h4>Most mentioned skills</h4>
                  <ol className="market-pro-skill-list">
                    {automatic.all.top_skills.slice(0, 6).map((skill) => {
                      const maximum = Math.max(1, ...automatic.all.top_skills.map((item) => item.count));
                      const width = Math.round((skill.count / maximum) * 100);
                      return (
                        <li key={skill.label}>
                          <div><span>{skill.label}</span><strong>{skill.count.toLocaleString()} roles</strong></div>
                          <span className="market-pro-skill-track" aria-hidden="true">
                            <span style={{ width: `${width}%` }} />
                          </span>
                        </li>
                      );
                    })}
                  </ol>
                </>
              ) : <p>{loading ? "Calculating local market indicators…" : "Automatic indicators are unavailable."}</p>}
            </article>
          </section>

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
                      <small>Aggregate evidence</small>
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
                      <div>
                        <strong>{action.title}</strong>
                        {action.detail && (
                          <>
                            <small className="market-pro-action-preview">{action.detail}</small>
                            <details className="market-pro-action-details">
                              <summary>Read full recommendation</summary>
                              <p>{action.detail}</p>
                            </details>
                          </>
                        )}
                      </div>
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
                    <div><dt>Verified portal identities</dt><dd>{(data.evidence_provenance.verified_source_identities ?? 0).toLocaleString()}</dd></div>
                    <div><dt>Unique verified postings</dt><dd>{(data.evidence_provenance.verified_postings ?? 0).toLocaleString()}</dd></div>
                    <div><dt>Verified capture receipts</dt><dd>{(data.evidence_provenance.verified_source_observations ?? 0).toLocaleString()}</dd></div>
                    {Object.entries(data.evidence_provenance.verified_by_portal ?? {}).map(([portal, counts]) => (
                      <div key={portal}><dt>{portal} (identities / receipts)</dt><dd>{counts.identities} / {counts.observations}</dd></div>
                    ))}

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
                  <div><strong>{data.evidence_provenance.observation_count.toLocaleString()}</strong><span>captured observations</span></div>
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
