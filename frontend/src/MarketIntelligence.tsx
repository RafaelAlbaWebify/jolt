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
type LinkedInRecommendation = {
  id: string;
  recommendation_type: string;
  target_area: string;
  title: string;
  rationale: string;
  proposed_action: string;
  proposed_text: string;
  priority: string;
  status: string;
};
type LinkedInCommandCenterData = {
  capture_count: number;
  recommendation_count: number;
  open_recommendation_count: number;
  categories: Record<string, number>;
  recommendations: LinkedInRecommendation[];
};
type JobSearchPreferences = {
  target_titles: string[];
  preferred_work_modes: string[];
  base_locality: string;
  max_hybrid_distance_km: number;
  countries: string[];
  languages: string[];
  expected_salary_eur_min: number | null;
  expected_salary_eur_target: number | null;
  preferred_shifts: string[];
  excluded_shifts: string[];
  preferred_workload: string;
  excluded_keywords: string[];
  preferred_keywords: string[];
  notes: string;
};
type PreparationItem = {
  title: string;
  reason: string;
  study: string;
  practice: string;
  linkedin: string;
  proof: string;
  source: string;
  priority: "High" | "Medium";
};

type Props = { apiBase: string; active: boolean };
type Scope = "target" | "all";

const EMPTY_PREFERENCES: JobSearchPreferences = {
  target_titles: [],
  preferred_work_modes: [],
  base_locality: "",
  max_hybrid_distance_km: 0,
  countries: [],
  languages: [],
  expected_salary_eur_min: null,
  expected_salary_eur_target: null,
  preferred_shifts: [],
  excluded_shifts: [],
  preferred_workload: "normal",
  excluded_keywords: [],
  preferred_keywords: [],
  notes: "",
};

const PREPARATION_RULES: Record<string, Omit<PreparationItem, "source">> = {
  sql: { title: "SQL troubleshooting", reason: "Target support roles frequently need data investigation, error triage, and evidence for engineering handoff.", study: "SELECT/JOIN/GROUP BY, reading SQL errors, basic slow-query symptoms, and data-quality checks.", practice: "Create 3 support-ticket scenarios where logs point to a SQL/data issue and write the triage notes.", linkedin: "Make SQL troubleshooting visible in About, Skills, and one experience bullet.", proof: "Add a short JOLT/WATCH-style case study: application support SQL triage from symptom to evidence.", priority: "High" },
  api: { title: "APIs, JSON, and integration troubleshooting", reason: "Application Support and SaaS Support roles often sit between users, APIs, logs, and product engineering.", study: "HTTP status codes, JSON payloads, auth failures, Postman basics, webhooks, and retry/failure patterns.", practice: "Build a small broken-API lab and document how you isolate request, response, payload, and ownership.", linkedin: "Add API/log troubleshooting language to About and technical support positioning.", proof: "Publish a small support runbook or workflow screenshot from JOLT showing evidence-based escalation.", priority: "High" },
  logs: { title: "Logs and RCA evidence", reason: "The market and LinkedIn feedback both reward clear incident evidence, not only tool names.", study: "Timestamp correlation, error patterns, incident timelines, RCA structure, and escalation summaries.", practice: "Write 2 anonymized incident/RCA summaries: impact, signal, cause, action, prevention.", linkedin: "Rewrite experience bullets around incident triage, RCA, runbooks, escalation, and customer-facing support.", proof: "Add one Featured item with an anonymized troubleshooting/RCA template.", priority: "High" },
  powershell: { title: "PowerShell automation for support operations", reason: "Your profile already has IT operations credibility; automation turns that into practical support evidence.", study: "File parsing, service checks, HTTP calls, CSV/JSON handling, and safe read-only diagnostics.", practice: "Package one diagnostic script with sample output and a short explanation for support handoff.", linkedin: "Position PowerShell as support automation, not generic scripting.", proof: "Feature one read-only support diagnostic script or WATCH/JOLT utility.", priority: "Medium" },
  active_directory: { title: "Windows, AD, DNS, and identity support scenarios", reason: "Infrastructure support roles are in your target market, and this is a credible existing strength.", study: "AD user states, DNS lookup flow, DHCP basics, Entra ID/M365 support, and escalation boundaries.", practice: "Document 3 support scenarios: locked user, DNS failure, M365 access issue.", linkedin: "Keep AD/DNS/M365 visible but connect it to user/business support outcomes.", proof: "Add a homelab/support scenario summary rather than a raw technology list.", priority: "Medium" },
};

function Ranking({ title, items, empty }: { title: string; items: Metric[]; empty?: string }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return <section className="market-card"><h3>{title}</h3>{items.length === 0 ? <p>{empty ?? "No evidence detected in this scope."}</p> : <div className="market-ranking">{items.map((item) => <div className="market-ranking-row" key={item.label}><div><strong>{item.label}</strong><span>{item.count}</span></div><div className="market-bar"><span style={{ width: `${(item.count / maximum) * 100}%` }} /></div></div>)}</div>}</section>;
}
function readable(value: string) { return value.replaceAll("_", " "); }
function normalized(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, "_"); }
function lines(value: string) { return value.split("\n").map((item) => item.trim()).filter(Boolean); }
function comma(value: string) { return value.split(",").map((item) => item.trim()).filter(Boolean); }
function asMultiline(values: string[] | undefined) { return (values ?? []).join("\n"); }

function buildPreparationPlan(scope: ScopeData, linkedin: LinkedInCommandCenterData | null): PreparationItem[] {
  const tokens = new Set<string>();
  for (const item of [...scope.top_skills, ...scope.top_gaps, ...scope.study_priorities]) {
    const key = normalized(item.label);
    if (key.includes("sql")) tokens.add("sql");
    if (key.includes("api") || key.includes("rest") || key.includes("integration")) tokens.add("api");
    if (key.includes("log") || key.includes("rca") || key.includes("incident") || key.includes("escalation")) tokens.add("logs");
    if (key.includes("powershell")) tokens.add("powershell");
    if (key.includes("active_directory") || key.includes("dns") || key.includes("microsoft_365") || key.includes("windows")) tokens.add("active_directory");
  }
  for (const recommendation of linkedin?.recommendations ?? []) {
    const text = `${recommendation.title} ${recommendation.target_area} ${recommendation.rationale} ${recommendation.proposed_action}`.toLowerCase();
    if (text.includes("sql")) tokens.add("sql");
    if (text.includes("api") || text.includes("integration") || text.includes("json")) tokens.add("api");
    if (text.includes("log") || text.includes("rca") || text.includes("incident") || text.includes("escalation")) tokens.add("logs");
    if (text.includes("powershell") || text.includes("automation")) tokens.add("powershell");
    if (text.includes("active directory") || text.includes("dns") || text.includes("microsoft 365") || text.includes("windows")) tokens.add("active_directory");
  }
  if (tokens.size === 0 && linkedin?.recommendation_count) { tokens.add("logs"); tokens.add("sql"); }
  return [...tokens].slice(0, 5).map((token) => ({ ...PREPARATION_RULES[token], source: linkedin?.recommendation_count ? "Market demand + LinkedIn feedback" : "Market demand" }));
}

function linkedInFitSignals(data: MarketData, linkedin: LinkedInCommandCenterData | null): string[] {
  const recommendations = linkedin?.recommendations ?? [];
  const signals: string[] = [];
  if (!linkedin || linkedin.capture_count === 0) return ["No LinkedIn evidence has been captured yet, so Market Insights cannot compare your profile against the target market."];
  if (recommendations.some((item) => item.title.toLowerCase().includes("headline") || item.target_area.toLowerCase().includes("headline"))) signals.push("LinkedIn headline/positioning needs to match the target roles more directly.");
  if (recommendations.some((item) => item.title.toLowerCase().includes("skill") || item.target_area.toLowerCase().includes("skill"))) signals.push("LinkedIn skills need reordering or strengthening against the most requested market skills.");
  if (data.target.top_skills.some((item) => item.label.toLowerCase().includes("sql")) && !recommendations.some((item) => `${item.title} ${item.rationale}`.toLowerCase().includes("sql"))) signals.push("SQL appears in target-market skills; verify it is visible in LinkedIn headline/About/Skills.");
  if (recommendations.some((item) => `${item.title} ${item.rationale}`.toLowerCase().includes("featured") || `${item.title} ${item.rationale}`.toLowerCase().includes("proof"))) signals.push("Profile proof-of-work should be more visible: JOLT/WATCH/TRACE need to support employability, not only exist as side projects.");
  if (signals.length === 0) signals.push("LinkedIn evidence is available. Imported recommendations can now be used to guide study, practice, and profile updates.");
  return signals.slice(0, 5);
}

export function MarketIntelligence({ apiBase, active }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
  const [linkedin, setLinkedin] = useState<LinkedInCommandCenterData | null>(null);
  const [preferences, setPreferences] = useState<JobSearchPreferences | null>(null);
  const [preferenceDraft, setPreferenceDraft] = useState<JobSearchPreferences>(EMPTY_PREFERENCES);
  const [showPreferences, setShowPreferences] = useState(false);
  const [scope, setScope] = useState<Scope>("target");
  const [timeframe, setTimeframe] = useState<Timeframe>("all");
  const [sourceScope, setSourceScope] = useState<SourceScope>("all");
  const [loading, setLoading] = useState(false);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ timeframe, source_scope: sourceScope });
      const response = await fetch(`${apiBase}/api/market-intelligence?${params.toString()}`, { signal });
      if (!response.ok) throw new Error("Unable to load market insights.");
      setData((await response.json()) as MarketData);
      setLastRefreshedAt(new Date().toISOString());
      const linkedinResponse = await fetch(`${apiBase}/api/linkedin-command-center`, { signal }).catch(() => null);
      if (linkedinResponse?.ok) setLinkedin((await linkedinResponse.json()) as LinkedInCommandCenterData);
      const preferenceResponse = await fetch(`${apiBase}/api/job-search-preferences`, { signal }).catch(() => null);
      if (preferenceResponse?.ok) { const loaded = (await preferenceResponse.json()) as JobSearchPreferences; setPreferences(loaded); setPreferenceDraft(loaded); }
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(caught instanceof Error ? caught.message : "Market insights failed.");
    } finally { setLoading(false); }
  }, [apiBase, sourceScope, timeframe]);

  useEffect(() => { if (!active) return undefined; const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [active, load]);

  const selected = data?.[scope] ?? null;
  const appliedTimeframe = data?.filters?.timeframe ?? timeframe;
  const appliedSource = data?.filters?.source_scope ?? sourceScope;
  const preparationPlan = useMemo(() => selected ? buildPreparationPlan(selected, linkedin) : [], [selected, linkedin]);
  const linkedinSignals = useMemo(() => data ? linkedInFitSignals(data, linkedin) : [], [data, linkedin]);

  async function savePreferences() {
    setSavingPreferences(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/job-search-preferences`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(preferenceDraft) });
      if (!response.ok) throw new Error("Unable to save job search preferences.");
      const saved = (await response.json()) as JobSearchPreferences;
      setPreferences(saved); setPreferenceDraft(saved); setNotice("Job search preferences saved.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to save job search preferences."); }
    finally { setSavingPreferences(false); }
  }

  function patchPreferences(patch: Partial<JobSearchPreferences>) { setPreferenceDraft((current) => ({ ...current, ...patch })); }

  return (
    <section className="panel market-workspace" aria-labelledby="market-heading">
      <div className="section-heading market-heading">
        <div><p className="eyebrow">Market insights</p><h2 id="market-heading">Market Insights</h2><p>Learn from active retained records and compare market demand with LinkedIn positioning.</p>{lastRefreshedAt && <p className="market-refreshed">Last refreshed {new Date(lastRefreshedAt).toLocaleString()}</p>}</div>
        <div className="market-heading-actions"><button type="button" className="secondary" disabled={!active || loading} onClick={() => void load()}>{loading ? "Refreshing…" : data ? "Refresh insights" : "Load insights"}</button><button type="button" className="secondary" disabled={!data} onClick={() => setShowPreferences((value) => !value)}>Job preferences</button><a href={`${apiBase}/api/market-intelligence/preparation-pack`} download="JOLT_MARKET_LINKEDIN_PREPARATION.zip">Export Market + LinkedIn pack</a>{data && <div className="market-scope" aria-label="Market scope"><button type="button" className={scope === "target" ? "filter-active" : "secondary"} onClick={() => setScope("target")}>Active target roles ({data.target_role_count})</button><button type="button" className={scope === "all" ? "filter-active" : "secondary"} onClick={() => setScope("all")}>Active retained records ({data.total_unique_roles})</button></div>}</div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}{notice && <p className="application-move-notice" role="status">{notice}</p>}

      <div className="opportunity-query-tools" aria-label="Market filters"><label><span>Timeframe</span><select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}><option value="all">All active records</option><option value="last_30_days">Last 30 days</option><option value="last_7_days">Last 7 days</option></select></label><label><span>Source</span><select value={sourceScope} onChange={(event) => setSourceScope(event.target.value as SourceScope)}><option value="all">All sources</option><option value="capture_batches">Capture batches</option><option value="manual_intake">Manual intake</option></select></label></div>

      {showPreferences && <section className="market-card job-preferences" aria-labelledby="job-preferences-heading"><div className="market-card-heading"><h3 id="job-preferences-heading">Editable job search preferences</h3><span>{preferences ? "Loaded from JOLT" : "Defaults"}</span></div><div className="preparation-grid"><label>Target titles<textarea rows={5} value={asMultiline(preferenceDraft.target_titles)} onChange={(event) => patchPreferences({ target_titles: lines(event.target.value) })} /></label><label>Preferred keywords<textarea rows={5} value={asMultiline(preferenceDraft.preferred_keywords)} onChange={(event) => patchPreferences({ preferred_keywords: lines(event.target.value) })} /></label><label>Excluded keywords<textarea rows={4} value={asMultiline(preferenceDraft.excluded_keywords)} onChange={(event) => patchPreferences({ excluded_keywords: lines(event.target.value) })} /></label><label>Countries<input value={(preferenceDraft.countries ?? []).join(", ")} onChange={(event) => patchPreferences({ countries: comma(event.target.value) })} /></label><label>Work modes<input value={(preferenceDraft.preferred_work_modes ?? []).join(", ")} onChange={(event) => patchPreferences({ preferred_work_modes: comma(event.target.value) })} /></label><label>Base locality<input value={preferenceDraft.base_locality} onChange={(event) => patchPreferences({ base_locality: event.target.value })} /></label><label>Max hybrid distance km<input type="number" value={preferenceDraft.max_hybrid_distance_km} onChange={(event) => patchPreferences({ max_hybrid_distance_km: Number(event.target.value) })} /></label><label>Min salary EUR<input type="number" value={preferenceDraft.expected_salary_eur_min ?? ""} onChange={(event) => patchPreferences({ expected_salary_eur_min: event.target.value ? Number(event.target.value) : null })} /></label><label>Target salary EUR<input type="number" value={preferenceDraft.expected_salary_eur_target ?? ""} onChange={(event) => patchPreferences({ expected_salary_eur_target: event.target.value ? Number(event.target.value) : null })} /></label><label>Excluded shifts<input value={(preferenceDraft.excluded_shifts ?? []).join(", ")} onChange={(event) => patchPreferences({ excluded_shifts: comma(event.target.value) })} /></label><label>Notes<textarea rows={4} value={preferenceDraft.notes} onChange={(event) => patchPreferences({ notes: event.target.value })} /></label></div><button type="button" disabled={savingPreferences} onClick={() => void savePreferences()}>{savingPreferences ? "Saving…" : "Save job preferences"}</button></section>}

      {loading && !data && <p role="status">Loading market insights…</p>}
      {data && selected && <>
        <div className="market-summary"><div><strong>{selected.total_roles}</strong><span>{scope === "target" ? "Active target roles" : "Active records"}</span></div><div><strong>{selected.strong_roles}</strong><span>Strong matches</span></div><div><strong>{selected.viable_roles}</strong><span>Strong or viable</span></div><div><strong>{linkedin?.open_recommendation_count ?? 0}</strong><span>LinkedIn actions</span></div></div>
        <div className="market-guidance"><strong>How to read fit</strong><p>{data.fit_explanation}</p><p>Archived capture batches are excluded. Reviewed and application records remain included unless the application card itself is archived.</p><p>Applied filters: {readable(appliedTimeframe)} · {readable(appliedSource)}.</p>{scope === "target" && <p><strong>{data.outside_target_count}</strong> active records are outside your target path and are excluded from this view.</p>}</div>
        <section className="market-card linkedin-market-fit" aria-labelledby="linkedin-market-fit-heading"><div className="market-card-heading"><h3 id="linkedin-market-fit-heading">LinkedIn positioning vs market</h3><span>{linkedin?.capture_count ?? 0} captures · {linkedin?.recommendation_count ?? 0} recommendations</span></div><div className="linkedin-signal-list">{linkedinSignals.map((signal) => <p key={signal}>{signal}</p>)}</div></section>
        <section className="market-card preparation-plan" aria-labelledby="preparation-plan-heading"><div className="market-card-heading"><h3 id="preparation-plan-heading">Preparation plan: study, practice, publish</h3><span>{preparationPlan.length} priorities</span></div>{preparationPlan.length === 0 ? <p>No preparation priorities yet. Add target roles and LinkedIn recommendations to generate a plan.</p> : <div className="preparation-grid">{preparationPlan.map((item) => <article key={item.title} className="preparation-card"><p className="eyebrow">{item.priority} · {item.source}</p><h4>{item.title}</h4><p>{item.reason}</p><details><summary>Study / practice / LinkedIn action</summary><ul><li><strong>Study:</strong> {item.study}</li><li><strong>Practice:</strong> {item.practice}</li><li><strong>LinkedIn:</strong> {item.linkedin}</li><li><strong>Proof:</strong> {item.proof}</li></ul></details></article>)}</div>}</section>
        <div className="market-grid"><Ranking title="Target role families" items={selected.role_families} /><Ranking title="Work mode" items={selected.work_modes} /><Ranking title="Fit distribution" items={selected.fit_distribution} /><Ranking title="Most requested skills" items={selected.top_skills} /><Ranking title="Most common capability gaps" items={selected.top_gaps} empty="No strategy-profile gaps were found in this scope." /><Ranking title="Highest-return study topics" items={selected.study_priorities} empty="No preparation topics were generated for this scope." /><Ranking title="Seniority" items={selected.seniority} /><Ranking title="Companies hiring repeatedly" items={selected.top_companies.filter((item) => item.count > 1)} empty="No employer appears more than once in this scope." /><Ranking title="Top locations" items={selected.top_locations} /></div>
        {scope === "target" && <Ranking title="Outside-target titles to remove from future searches" items={data.outside_title_examples} empty="No outside-target records were detected." />}
        <section className="market-card market-salary"><div className="market-card-heading"><h3>Salary evidence</h3><span>{selected.salary_coverage} of {selected.total_roles} roles contain detectable salary text</span></div>{selected.salary_mentions.length === 0 ? <p>No salary ranges were detected. JOLT does not estimate missing salaries.</p> : <div className="market-salary-list">{selected.salary_mentions.map((item, index) => <div key={`${item.title}-${item.company}-${index}`}><strong>{item.mention}</strong><span>{item.title} · {item.company}</span></div>)}</div>}</section>
      </>}
    </section>
  );
}
