import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

type CaptureCategory = "profile" | "public_profile" | "analytics" | "activity" | "network_contact" | "network_request" | "target_company" | "target_recruiter" | "job_search" | "other";
type RecommendationType = "profile_update" | "network_decision" | "content_action" | "outreach" | "lead_research" | "cleanup";
type Priority = "high" | "medium" | "low";
type RecommendationStatus = "pending" | "accepted" | "rejected" | "implemented" | "snoozed";

type LinkedInCapture = {
  id: string;
  category: CaptureCategory;
  title: string;
  source_url: string;
  visible_text: string;
  notes: string;
  content_hash: string;
  previous_capture_id: string | null;
  changed_since_previous: boolean;
  captured_at: string;
};

type LinkedInRecommendation = {
  id: string;
  capture_id: string | null;
  recommendation_type: RecommendationType;
  target_area: string;
  title: string;
  rationale: string;
  proposed_action: string;
  proposed_text: string;
  priority: Priority;
  status: RecommendationStatus;
  created_at: string;
  updated_at: string;
};

type LinkedInCommandCenterData = {
  capture_count: number;
  recommendation_count: number;
  open_recommendation_count: number;
  categories: Record<string, number>;
  recommendation_statuses: Record<string, number>;
  recommendation_types?: Record<string, number>;
  captures: LinkedInCapture[];
  recommendations: LinkedInRecommendation[];
};

type CaptureTarget = {
  id: string;
  name: string;
  category: CaptureCategory;
  url: string;
  enabled: boolean;
};

type Props = { apiBase: string; active: boolean };

const CAPTURE_CATEGORIES: CaptureCategory[] = [
  "profile",
  "public_profile",
  "analytics",
  "activity",
  "network_contact",
  "network_request",
  "target_company",
  "target_recruiter",
  "job_search",
  "other",
];
const RECOMMENDATION_TYPES: RecommendationType[] = ["profile_update", "network_decision", "content_action", "outreach", "lead_research", "cleanup"];
const PRIORITIES: Priority[] = ["high", "medium", "low"];
const STATUSES: RecommendationStatus[] = ["pending", "accepted", "rejected", "implemented", "snoozed"];
const TARGETS_STORAGE_KEY = "jolt.linkedin.captureTargets.v1";

const DEFAULT_CAPTURE_TARGETS: CaptureTarget[] = [
  { id: "profile", name: "Profile", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/", enabled: true },
  { id: "all-activity", name: "All Activity", category: "activity", url: "https://www.linkedin.com/in/rafael-alba-tech/recent-activity/all/", enabled: true },
  { id: "experience", name: "Experience", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/experience/", enabled: true },
  { id: "certifications", name: "Licenses & certifications", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/certifications/", enabled: true },
  { id: "skills", name: "Skills", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/skills/", enabled: true },
  { id: "recommendations", name: "Recommendations", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/recommendations/?detailScreenTabIndex=0", enabled: true },
  { id: "interests", name: "Interests", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/interests/?initialTabId=interest_top_voices", enabled: true },
  { id: "job-tracker", name: "Job Tracker", category: "job_search", url: "https://www.linkedin.com/jobs-tracker/?stage=applied", enabled: true },
  { id: "jobs-preferences", name: "Jobs Based on my Preferences", category: "job_search", url: "https://www.linkedin.com/jobs/search-results/?currentJobId=4445359749&keywords=Information%20Technology%20Operations%20Engineer%20or%20Information%20Technology%20Infrastructure%20Engineer%20or%20System%20Administrator%20or%20Information%20Technology%20Support%20Engineer%20or%20Technical%20Support%20Engineer%2C%20remote%20or%20hybrid&origin=PREFERENCES_LANDING&originToLandingJobPostings=4445359749%2C4445622133%2C4423231546&geoId=101165590%2C103644278%2C104524525%2C104738515", enabled: true },
  { id: "connections", name: "Connections", category: "network_contact", url: "https://www.linkedin.com/mynetwork/invite-connect/connections/", enabled: false },
  { id: "feed", name: "Feed", category: "activity", url: "https://www.linkedin.com/feed/", enabled: false },
  { id: "groups", name: "Groups", category: "activity", url: "https://www.linkedin.com/groups/", enabled: false },
];

const BOARD_LABELS: Record<RecommendationType, string> = {
  profile_update: "Profile updates",
  network_decision: "Network decisions",
  content_action: "Content and activity",
  outreach: "Outreach",
  lead_research: "Lead research",
  cleanup: "Cleanup",
};

function label(value: string) {
  return value.replaceAll("_", " ");
}

function loadStoredTargets(): CaptureTarget[] {
  if (typeof window === "undefined") return DEFAULT_CAPTURE_TARGETS;
  const raw = window.localStorage.getItem(TARGETS_STORAGE_KEY);
  if (!raw) return DEFAULT_CAPTURE_TARGETS;
  try {
    const parsed = JSON.parse(raw) as CaptureTarget[];
    if (!Array.isArray(parsed) || parsed.length === 0) return DEFAULT_CAPTURE_TARGETS;
    return parsed.map((item) => ({
      id: String(item.id || crypto.randomUUID()),
      name: String(item.name || "LinkedIn target"),
      category: CAPTURE_CATEGORIES.includes(item.category) ? item.category : "other",
      url: String(item.url || ""),
      enabled: Boolean(item.enabled),
    }));
  } catch {
    return DEFAULT_CAPTURE_TARGETS;
  }
}

function captureCommand(target: CaptureTarget) {
  return `uv --project backend run python .\\tools\\jolt-linkedin-user-present-capture.py --url "${target.url}" --category ${target.category} --title "${target.name}"`;
}

async function errorFromResponse(response: Response, fallback: string) {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  return new Error(payload?.detail || fallback);
}

export function LinkedInCommandCenter({ apiBase, active }: Props) {
  const [data, setData] = useState<LinkedInCommandCenterData | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showCaptureTargets, setShowCaptureTargets] = useState(true);
  const [showCaptureForm, setShowCaptureForm] = useState(false);
  const [showRecommendationForm, setShowRecommendationForm] = useState(false);
  const [showImportForm, setShowImportForm] = useState(false);
  const [captureTargets, setCaptureTargets] = useState<CaptureTarget[]>(loadStoredTargets);
  const [editingTargetId, setEditingTargetId] = useState<string | null>(null);
  const [category, setCategory] = useState<CaptureCategory>("profile");
  const [captureTitle, setCaptureTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [visibleText, setVisibleText] = useState("");
  const [notes, setNotes] = useState("");
  const [recommendationType, setRecommendationType] = useState<RecommendationType>("profile_update");
  const [targetArea, setTargetArea] = useState("");
  const [recommendationTitle, setRecommendationTitle] = useState("");
  const [rationale, setRationale] = useState("");
  const [proposedAction, setProposedAction] = useState("");
  const [proposedText, setProposedText] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [importText, setImportText] = useState("");

  useEffect(() => {
    window.localStorage.setItem(TARGETS_STORAGE_KEY, JSON.stringify(captureTargets));
  }, [captureTargets]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center`);
      if (!response.ok) throw await errorFromResponse(response, "Unable to load LinkedIn Command Center.");
      setData((await response.json()) as LinkedInCommandCenterData);
      setLoaded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "LinkedIn Command Center failed.");
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (active && !loaded && !loading) void load();
  }, [active, load, loaded, loading]);

  const categorySummary = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.categories).sort((left, right) => right[1] - left[1]);
  }, [data]);

  const groupedRecommendations = useMemo(() => {
    const groups = new Map<RecommendationType, LinkedInRecommendation[]>();
    for (const type of RECOMMENDATION_TYPES) groups.set(type, []);
    for (const item of data?.recommendations ?? []) groups.get(item.recommendation_type)?.push(item);
    return [...groups.entries()].filter(([, items]) => items.length > 0);
  }, [data]);

  function updateTarget(id: string, patch: Partial<CaptureTarget>) {
    setCaptureTargets((items) => items.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  function addTarget() {
    const id = crypto.randomUUID();
    setCaptureTargets((items) => [
      ...items,
      { id, name: "New LinkedIn target", category: "other", url: "", enabled: true },
    ]);
    setEditingTargetId(id);
  }

  function resetTargets() {
    setCaptureTargets(DEFAULT_CAPTURE_TARGETS);
    setEditingTargetId(null);
    setNotice("LinkedIn capture targets reset to Rafael's defaults.");
  }

  async function copyCommand(target: CaptureTarget) {
    await navigator.clipboard.writeText(captureCommand(target));
    setNotice(`Capture command copied for ${target.name}.`);
  }

  function useTargetInForm(target: CaptureTarget) {
    setCategory(target.category);
    setCaptureTitle(target.name);
    setSourceUrl(target.url);
    setShowCaptureForm(true);
    setNotice(`Capture form prepared for ${target.name}.`);
  }

  async function submitCapture(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center/captures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, title: captureTitle, source_url: sourceUrl, visible_text: visibleText, notes }),
      });
      if (!response.ok) throw await errorFromResponse(response, "Unable to save LinkedIn capture.");
      setCaptureTitle("");
      setSourceUrl("");
      setVisibleText("");
      setNotes("");
      setShowCaptureForm(false);
      setNotice("LinkedIn evidence snapshot saved.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "LinkedIn capture failed.");
    } finally {
      setBusy(false);
    }
  }

  async function submitRecommendation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recommendation_type: recommendationType,
          target_area: targetArea,
          title: recommendationTitle,
          rationale,
          proposed_action: proposedAction,
          proposed_text: proposedText,
          priority,
        }),
      });
      if (!response.ok) throw await errorFromResponse(response, "Unable to save LinkedIn recommendation.");
      setTargetArea("");
      setRecommendationTitle("");
      setRationale("");
      setProposedAction("");
      setProposedText("");
      setPriority("medium");
      setShowRecommendationForm(false);
      setNotice("LinkedIn recommendation saved.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "LinkedIn recommendation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const parsed = JSON.parse(importText) as unknown;
      const payload = Array.isArray(parsed) ? { source: "chatgpt_package", recommendations: parsed } : parsed;
      const response = await fetch(`${apiBase}/api/linkedin-command-center/recommendations/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw await errorFromResponse(response, "Unable to import LinkedIn recommendations.");
      const imported = (await response.json()) as { imported_count: number };
      setImportText("");
      setShowImportForm(false);
      setNotice(`${imported.imported_count} LinkedIn recommendations imported.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "LinkedIn recommendation import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(item: LinkedInRecommendation, status: RecommendationStatus) {
    if (item.status === status) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center/recommendations/${item.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) throw await errorFromResponse(response, "Unable to update recommendation status.");
      setNotice("LinkedIn recommendation status updated.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update recommendation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel linkedin-command-center" aria-labelledby="linkedin-command-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">LinkedIn presence and networking</p>
          <h2 id="linkedin-command-heading">LinkedIn Command Center</h2>
          <p>Track user-approved LinkedIn evidence, profile improvements, network decisions, activity ideas, and outreach actions. JOLT never sends LinkedIn actions for you.</p>
        </div>
        <div className="professional-source-editor-actions">
          <button type="button" disabled={!active || loading} onClick={() => void load()} className="secondary">
            {loading ? "Refreshing…" : loaded ? "Refresh" : "Load"}
          </button>
          <button type="button" onClick={() => setShowCaptureTargets((value) => !value)} disabled={busy}>Capture targets</button>
          <button type="button" onClick={() => setShowCaptureForm((value) => !value)} disabled={busy}>Capture LinkedIn</button>
          <button type="button" className="secondary" onClick={() => setShowRecommendationForm((value) => !value)} disabled={busy}>Add recommendation</button>
          <button type="button" className="secondary" onClick={() => setShowImportForm((value) => !value)} disabled={busy}>Import analysis JSON</button>
          <a href={`${apiBase}/api/linkedin-command-center/export`} download="JOLT_LINKEDIN_COMMAND_CENTER.zip">Export package</a>
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="application-move-notice" role="status">{notice}</p>}
      {loading && !data && <p role="status">Loading LinkedIn Command Center…</p>}

      {data && (
        <>
          <div className="market-summary">
            <div><strong>{data.capture_count}</strong><span>Evidence snapshots</span></div>
            <div><strong>{data.recommendation_count}</strong><span>Recommendations</span></div>
            <div><strong>{data.open_recommendation_count}</strong><span>Open actions</span></div>
            <div><strong>{categorySummary.length}</strong><span>Capture categories</span></div>
          </div>
          {categorySummary.length > 0 && (
            <p className="confidence">Captured categories: {categorySummary.map(([name, count]) => `${label(name)} (${count})`).join(" · ")}</p>
          )}
        </>
      )}

      {showCaptureTargets && (
        <section className="panel manual-intake-panel" aria-labelledby="linkedin-targets-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Editable capture list</p>
              <h3 id="linkedin-targets-heading">LinkedIn capture targets</h3>
              <p>Edit URLs only when needed. The list is stored locally in this browser.</p>
            </div>
            <div className="professional-source-editor-actions">
              <button type="button" className="secondary" onClick={addTarget}>Add target</button>
              <button type="button" className="secondary" onClick={resetTargets}>Reset defaults</button>
            </div>
          </div>
          <div className="queue reviewed-decisions">
            {captureTargets.map((target) => {
              const editing = editingTargetId === target.id;
              return (
                <article key={target.id}>
                  <div>
                    <p className="eyebrow">{target.enabled ? "Enabled" : "Disabled"} · {label(target.category)}</p>
                    <h3>{target.name || "Untitled LinkedIn target"}</h3>
                    <p className="confidence">{target.url.trim() ? "URL configured" : "URL missing"}</p>
                    {editing && (
                      <div className="workspace-view-stack" aria-label={`Edit ${target.name || "LinkedIn target"}`}>
                        <label>Name
                          <input value={target.name} onChange={(event) => updateTarget(target.id, { name: event.target.value })} />
                        </label>
                        <label>Category
                          <select value={target.category} onChange={(event) => updateTarget(target.id, { category: event.target.value as CaptureCategory })}>
                            {CAPTURE_CATEGORIES.map((item) => <option value={item} key={item}>{label(item)}</option>)}
                          </select>
                        </label>
                        <label>URL
                          <input value={target.url} onChange={(event) => updateTarget(target.id, { url: event.target.value })} />
                        </label>
                      </div>
                    )}
                  </div>
                  <div className="professional-source-editor-actions">
                    <label className="decision-control"><span>Enabled</span>
                      <input type="checkbox" checked={target.enabled} onChange={(event) => updateTarget(target.id, { enabled: event.target.checked })} />
                    </label>
                    <button type="button" className="secondary" onClick={() => setEditingTargetId(editing ? null : target.id)}>{editing ? "Done" : "Edit"}</button>
                    <button type="button" className="secondary" disabled={!target.url.trim()} onClick={() => void copyCommand(target)}>Copy command</button>
                    <button type="button" disabled={!target.url.trim()} onClick={() => useTargetInForm(target)}>Use</button>
                    <button type="button" className="secondary" onClick={() => setCaptureTargets((items) => items.filter((item) => item.id !== target.id))}>Remove</button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {showCaptureForm && (
        <section className="panel manual-intake-panel" aria-labelledby="linkedin-capture-form-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">User-approved evidence</p>
              <h3 id="linkedin-capture-form-heading">Capture LinkedIn snapshot</h3>
              <p>Paste visible text from a LinkedIn page you opened yourself, or use a capture target command for screenshot capture.</p>
            </div>
            <button type="button" className="secondary" onClick={() => setShowCaptureForm(false)}>Close</button>
          </div>
          <form onSubmit={submitCapture}>
            <label>Category
              <select value={category} onChange={(event) => setCategory(event.target.value as CaptureCategory)}>
                {CAPTURE_CATEGORIES.map((item) => <option value={item} key={item}>{label(item)}</option>)}
              </select>
            </label>
            <label>Title
              <input value={captureTitle} onChange={(event) => setCaptureTitle(event.target.value)} placeholder="Profile baseline, activity snapshot, recruiter profile..." />
            </label>
            <label>LinkedIn URL <span>(optional)</span>
              <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} type="url" />
            </label>
            <label>Visible text
              <textarea value={visibleText} onChange={(event) => setVisibleText(event.target.value)} rows={8} placeholder="Paste visible text from the page snapshot." />
            </label>
            <label>Notes <span>(optional)</span>
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} />
            </label>
            <button type="submit" disabled={busy || (!visibleText.trim() && !notes.trim() && !sourceUrl.trim())}>{busy ? "Saving…" : "Save LinkedIn capture"}</button>
          </form>
        </section>
      )}

      {showRecommendationForm && (
        <section className="panel manual-intake-panel" aria-labelledby="linkedin-recommendation-form-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Manual / imported action</p>
              <h3 id="linkedin-recommendation-form-heading">Add LinkedIn recommendation</h3>
              <p>Track profile updates, contact decisions, content actions, outreach, and cleanup ideas.</p>
            </div>
            <button type="button" className="secondary" onClick={() => setShowRecommendationForm(false)}>Close</button>
          </div>
          <form onSubmit={submitRecommendation}>
            <label>Type
              <select value={recommendationType} onChange={(event) => setRecommendationType(event.target.value as RecommendationType)}>
                {RECOMMENDATION_TYPES.map((item) => <option value={item} key={item}>{label(item)}</option>)}
              </select>
            </label>
            <label>Priority
              <select value={priority} onChange={(event) => setPriority(event.target.value as Priority)}>
                {PRIORITIES.map((item) => <option value={item} key={item}>{label(item)}</option>)}
              </select>
            </label>
            <label>Target area
              <input value={targetArea} onChange={(event) => setTargetArea(event.target.value)} placeholder="Headline, About, recruiter, contact, post topic..." />
            </label>
            <label>Title
              <input value={recommendationTitle} onChange={(event) => setRecommendationTitle(event.target.value)} required />
            </label>
            <label>Rationale
              <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} rows={3} />
            </label>
            <label>Proposed action
              <textarea value={proposedAction} onChange={(event) => setProposedAction(event.target.value)} rows={3} />
            </label>
            <label>Proposed text <span>(optional)</span>
              <textarea value={proposedText} onChange={(event) => setProposedText(event.target.value)} rows={4} />
            </label>
            <button type="submit" disabled={busy || !recommendationTitle.trim()}>{busy ? "Saving…" : "Save recommendation"}</button>
          </form>
        </section>
      )}

      {showImportForm && (
        <section className="panel manual-intake-panel" aria-labelledby="linkedin-import-form-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Analysis import</p>
              <h3 id="linkedin-import-form-heading">Import ChatGPT recommendations</h3>
              <p>Paste the returned <code>linkedin_recommendations.json</code>. JOLT will add each item as a pending, reviewable action.</p>
            </div>
            <button type="button" className="secondary" onClick={() => setShowImportForm(false)}>Close</button>
          </div>
          <form onSubmit={submitImport}>
            <label>Recommendations JSON
              <textarea value={importText} onChange={(event) => setImportText(event.target.value)} rows={10} placeholder={'{"source":"chatgpt_package","recommendations":[...]}'}/>
            </label>
            <button type="submit" disabled={busy || !importText.trim()}>{busy ? "Importing…" : "Import recommendations"}</button>
          </form>
        </section>
      )}

      {data && (
        <div className="workspace-view-stack">
          <section className="panel" aria-labelledby="linkedin-recommendations-heading">
            <div className="section-heading"><h3 id="linkedin-recommendations-heading">Action boards</h3></div>
            {data.recommendations.length === 0 ? <p>No LinkedIn recommendations yet.</p> : (
              groupedRecommendations.map(([type, items]) => (
                <section key={type} className="market-card" aria-labelledby={`linkedin-board-${type}`}>
                  <h4 id={`linkedin-board-${type}`}>{BOARD_LABELS[type]} ({items.length})</h4>
                  <div className="queue reviewed-decisions">
                    {items.map((item) => (
                      <article key={item.id}>
                        <div>
                          <p className="eyebrow">{label(item.recommendation_type)} · {item.priority}</p>
                          <h3>{item.title}</h3>
                          {item.target_area && <p>{item.target_area}</p>}
                          {item.rationale && <p>{item.rationale}</p>}
                          {item.proposed_action && <p><strong>Action:</strong> {item.proposed_action}</p>}
                          {item.proposed_text && <pre className="evidence-json">{item.proposed_text}</pre>}
                        </div>
                        <label className="decision-control"><span>Status</span>
                          <select value={item.status} disabled={busy} onChange={(event) => void updateStatus(item, event.target.value as RecommendationStatus)}>
                            {STATUSES.map((status) => <option value={status} key={status}>{label(status)}</option>)}
                          </select>
                        </label>
                      </article>
                    ))}
                  </div>
                </section>
              ))
            )}
          </section>

          <section className="panel" aria-labelledby="linkedin-captures-heading">
            <div className="section-heading"><h3 id="linkedin-captures-heading">Evidence timeline</h3></div>
            {data.captures.length === 0 ? <p>No LinkedIn evidence snapshots yet.</p> : (
              <div className="capture-history-list">
                {data.captures.map((item) => (
                  <article key={item.id}>
                    <div>
                      <p className="eyebrow">{label(item.category)} · {new Date(item.captured_at).toLocaleString()}</p>
                      <h3>{item.title || "Untitled LinkedIn snapshot"}</h3>
                      {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Open source URL</a>}
                      <p>{item.changed_since_previous ? "Changed since previous capture in this category." : "No previous change detected for this category."}</p>
                      {item.visible_text && <details><summary>Visible text</summary><pre className="evidence-json">{item.visible_text}</pre></details>}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
