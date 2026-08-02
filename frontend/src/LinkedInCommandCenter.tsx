import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

type CaptureCategory = "profile" | "public_profile" | "analytics" | "activity" | "network_contact" | "network_request" | "target_company" | "target_recruiter" | "other";
type RecommendationStatus = "pending" | "accepted" | "rejected" | "implemented" | "snoozed";

type LinkedInCapture = {
  id: string;
  category: CaptureCategory;
  title: string;
  source_url: string;
  visible_text: string;
  notes: string;
  changed_since_previous: boolean;
  captured_at: string;
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
  status: RecommendationStatus;
};

type LinkedInProfileData = {
  capture_count: number;
  recommendation_count: number;
  open_recommendation_count: number;
  categories: Record<string, number>;
  captures: LinkedInCapture[];
  recommendations: LinkedInRecommendation[];
};

type CaptureTarget = {
  id: string;
  name: string;
  category: CaptureCategory;
  url: string;
  enabled: boolean;
  isDefault: boolean;
};

type Props = { apiBase: string; active: boolean };

const TARGETS_STORAGE_KEY = "jolt.linkedin.profileTargets.v1";
const LEGACY_STORAGE_KEY = "jolt.linkedin.captureTargets.v2";
const CATEGORIES: CaptureCategory[] = ["profile", "public_profile", "analytics", "activity", "network_contact", "network_request", "target_company", "target_recruiter", "other"];
const STATUSES: RecommendationStatus[] = ["pending", "accepted", "rejected", "implemented", "snoozed"];

const DEFAULT_TARGETS: CaptureTarget[] = [
  { id: "profile", name: "Profile", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/", enabled: true, isDefault: true },
  { id: "experience", name: "Experience", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/experience/", enabled: true, isDefault: true },
  { id: "skills", name: "Skills", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/skills/", enabled: true, isDefault: true },
  { id: "certifications", name: "Licenses & certifications", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/certifications/", enabled: true, isDefault: true },
  { id: "recommendations", name: "Recommendations", category: "profile", url: "https://www.linkedin.com/in/rafael-alba-tech/details/recommendations/?detailScreenTabIndex=0", enabled: true, isDefault: true },
  { id: "activity", name: "All activity", category: "activity", url: "https://www.linkedin.com/in/rafael-alba-tech/recent-activity/all/", enabled: true, isDefault: true },
  { id: "connections", name: "Connections", category: "network_contact", url: "https://www.linkedin.com/mynetwork/invite-connect/connections/", enabled: false, isDefault: true },
];

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function normalizeTarget(value: Partial<CaptureTarget>): CaptureTarget | null {
  const id = String(value.id || crypto.randomUUID());
  const url = String(value.url || "");
  const name = String(value.name || "LinkedIn target");
  const category = CATEGORIES.includes(value.category as CaptureCategory) ? value.category as CaptureCategory : "other";
  if (category === "other" && /linkedin\.com\/jobs|jobs-tracker/i.test(url)) return null;
  return { id, name, category, url, enabled: Boolean(value.enabled), isDefault: Boolean(value.isDefault) };
}

function loadTargets(): CaptureTarget[] {
  if (typeof window === "undefined") return DEFAULT_TARGETS;
  const current = window.localStorage.getItem(TARGETS_STORAGE_KEY);
  const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
  for (const raw of [current, legacy]) {
    if (!raw) continue;
    try {
      const parsed = JSON.parse(raw) as Partial<CaptureTarget>[];
      const targets = parsed.map(normalizeTarget).filter((item): item is CaptureTarget => item !== null);
      if (targets.length > 0) return targets;
    } catch {
      // Ignore malformed browser state and restore safe defaults.
    }
  }
  return DEFAULT_TARGETS;
}

async function responseError(response: Response, fallback: string) {
  const payload = await response.json().catch(() => null) as { detail?: string } | null;
  return new Error(payload?.detail || fallback);
}

function targetPayload(target: CaptureTarget) {
  return { category: target.category, title: target.name, url: target.url, wait_seconds: 4, full_page_screenshot: false };
}

export function LinkedInCommandCenter({ apiBase, active }: Props) {
  const [data, setData] = useState<LinkedInProfileData | null>(null);
  const [targets, setTargets] = useState<CaptureTarget[]>(loadTargets);
  const [showTargets, setShowTargets] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [capturingId, setCapturingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [manualCategory, setManualCategory] = useState<CaptureCategory>("profile");
  const [manualTitle, setManualTitle] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const [manualText, setManualText] = useState("");
  const [manualNotes, setManualNotes] = useState("");

  const load = useCallback(async () => {
    if (!active) return;
    setError("");
    const response = await fetch(`${apiBase}/api/linkedin-command-center`);
    if (!response.ok) throw await responseError(response, "Unable to load LinkedIn profile evidence.");
    setData(await response.json() as LinkedInProfileData);
  }, [active, apiBase]);

  useEffect(() => {
    if (active) void load().catch((caught) => setError(caught instanceof Error ? caught.message : "LinkedIn profile load failed."));
  }, [active, load]);

  useEffect(() => {
    window.localStorage.setItem(TARGETS_STORAGE_KEY, JSON.stringify(targets));
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  }, [targets]);

  const enabledTargets = useMemo(() => targets.filter((target) => target.enabled && target.url.trim()), [targets]);

  function patchTarget(id: string, patch: Partial<CaptureTarget>) {
    setTargets((items) => items.map((item) => item.id === id ? { ...item, ...patch } : item));
  }

  function addTarget() {
    const id = crypto.randomUUID();
    setTargets((items) => [...items, { id, name: "Custom profile target", category: "other", url: "", enabled: true, isDefault: false }]);
    setEditingId(id);
  }

  async function captureTarget(target: CaptureTarget) {
    setBusy(true); setCapturingId(target.id); setError(""); setNotice(`Opening ${target.name} in the managed browser…`);
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center/captures/playwright`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(targetPayload(target)),
      });
      if (!response.ok) throw await responseError(response, `Unable to capture ${target.name}.`);
      setNotice(`${target.name} captured and stored as LinkedIn profile evidence.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `${target.name} capture failed.`);
    } finally {
      setBusy(false); setCapturingId(null);
    }
  }

  async function captureEnabled() {
    if (enabledTargets.length === 0) return;
    setBusy(true); setCapturingId("batch"); setError(""); setNotice(`Capturing ${enabledTargets.length} enabled profile sections…`);
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center/captures/playwright-batch`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ targets: enabledTargets.map(targetPayload) }),
      });
      if (!response.ok) throw await responseError(response, "Unable to refresh LinkedIn profile evidence.");
      const result = await response.json() as { captured_count: number };
      setNotice(`${result.captured_count} LinkedIn profile sections captured.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "LinkedIn profile refresh failed.");
    } finally {
      setBusy(false); setCapturingId(null);
    }
  }

  async function saveManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center/captures`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: manualCategory, title: manualTitle, source_url: manualUrl, visible_text: manualText, notes: manualNotes }),
      });
      if (!response.ok) throw await responseError(response, "Unable to save manual LinkedIn evidence.");
      setManualTitle(""); setManualUrl(""); setManualText(""); setManualNotes(""); setShowManual(false);
      setNotice("Manual LinkedIn evidence saved.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Manual LinkedIn evidence failed.");
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(id: string, status: RecommendationStatus) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${apiBase}/api/linkedin-command-center/recommendations/${id}/status`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
      });
      if (!response.ok) throw await responseError(response, "Unable to update recommendation status.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Recommendation update failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="linkedin-command-center" aria-labelledby="linkedin-profile-heading">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Professional positioning</p>
            <h2 id="linkedin-profile-heading">LinkedIn Profile</h2>
            <p>One profile workflow: choose profile sections, capture evidence, review changes, and act on recommendations.</p>
          </div>
          <button type="button" disabled={busy || enabledTargets.length === 0} onClick={() => void captureEnabled()}>
            {capturingId === "batch" ? "Refreshing profile…" : "Refresh enabled profile evidence"}
          </button>
        </div>
        <div className="professional-safety-boundary" role="note">
          <strong>Read-only boundary</strong>
          <span>JOLT captures visible evidence. It does not message, react, connect, apply, or edit LinkedIn.</span>
        </div>
        <div className="button-row">
          <button type="button" className="secondary" onClick={() => setShowTargets((value) => !value)}>Capture targets</button>
          <button type="button" className="secondary" onClick={() => setShowManual((value) => !value)}>Manual evidence</button>
          <button type="button" className="secondary" onClick={() => void load()} disabled={busy}>Refresh results</button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
      </section>

      {showTargets && (
        <section className="panel" role="region" aria-label="Capture targets">
          <div className="section-heading">
            <div><h3>Authoritative profile targets</h3><p>Job searches and application tracking do not belong in this registry.</p></div>
            <div className="button-row">
              <button type="button" className="secondary" onClick={addTarget}>Add target</button>
              <button type="button" className="secondary" onClick={() => { setTargets(DEFAULT_TARGETS); setEditingId(null); }}>Reset defaults</button>
            </div>
          </div>
          <div className="professional-source-grid">
            {targets.map((target) => (
              <article key={target.id} className="professional-source-card">
                {editingId === target.id ? (
                  <div className="form-grid">
                    <label>Name<input value={target.name} onChange={(event) => patchTarget(target.id, { name: event.target.value })} /></label>
                    <label>Category<select value={target.category} onChange={(event) => patchTarget(target.id, { category: event.target.value as CaptureCategory })}>{CATEGORIES.map((item) => <option key={item} value={item}>{readable(item)}</option>)}</select></label>
                    <label className="full-width">URL<input value={target.url} onChange={(event) => patchTarget(target.id, { url: event.target.value })} /></label>
                    <button type="button" className="secondary" onClick={() => setEditingId(null)}>Done</button>
                    {!target.isDefault && <button type="button" className="danger" onClick={() => setTargets((items) => items.filter((item) => item.id !== target.id))}>Remove</button>}
                  </div>
                ) : (
                  <>
                    <div><strong>{target.name}</strong><p>{readable(target.category)}</p><small>{target.url}</small></div>
                    <label><input type="checkbox" checked={target.enabled} onChange={(event) => patchTarget(target.id, { enabled: event.target.checked })} /> Include in profile refresh</label>
                    <div className="button-row">
                      <button type="button" className="secondary" onClick={() => setEditingId(target.id)}>Edit URL</button>
                      <button type="button" disabled={busy || !target.url.trim()} onClick={() => void captureTarget(target)}>{capturingId === target.id ? "Capturing…" : "Capture"}</button>
                    </div>
                  </>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {showManual && (
        <section className="panel">
          <h3>Manual evidence fallback</h3>
          <form onSubmit={saveManual} className="form-grid">
            <label>Category<select value={manualCategory} onChange={(event) => setManualCategory(event.target.value as CaptureCategory)}>{CATEGORIES.map((item) => <option key={item} value={item}>{readable(item)}</option>)}</select></label>
            <label>Title<input required value={manualTitle} onChange={(event) => setManualTitle(event.target.value)} /></label>
            <label className="full-width">Source URL<input value={manualUrl} onChange={(event) => setManualUrl(event.target.value)} /></label>
            <label className="full-width">Visible text<textarea required value={manualText} onChange={(event) => setManualText(event.target.value)} /></label>
            <label className="full-width">Notes<textarea value={manualNotes} onChange={(event) => setManualNotes(event.target.value)} /></label>
            <button type="submit" disabled={busy}>Save manual evidence</button>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="section-heading"><div><h3>Evidence snapshots</h3><p>{data?.capture_count ?? 0} retained snapshots.</p></div></div>
        {!data?.captures.length ? <p>No LinkedIn profile evidence yet.</p> : (
          <div className="professional-source-grid">
            {data.captures.map((capture) => (
              <article key={capture.id} className="professional-source-card">
                <strong>{capture.title}</strong>
                <p>{readable(capture.category)} · {new Date(capture.captured_at).toLocaleString()}</p>
                {capture.changed_since_previous && <span className="application-card-alert">Changed since previous capture</span>}
                {capture.visible_text && <p>{capture.visible_text.slice(0, 320)}</p>}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="section-heading"><div><h3>Profile improvements</h3><p>{data?.open_recommendation_count ?? 0} open recommendations.</p></div></div>
        {!data?.recommendations.length ? <p>No LinkedIn recommendations yet.</p> : (
          <div className="professional-source-grid">
            {data.recommendations.map((item) => (
              <article key={item.id} className="professional-source-card">
                <div><strong>{item.title}</strong><p>{item.target_area} · {item.priority}</p></div>
                <p>{item.rationale}</p>
                <p><b>Action:</b> {item.proposed_action}</p>
                {item.proposed_text && <blockquote>{item.proposed_text}</blockquote>}
                <label>Status<select value={item.status} disabled={busy} onChange={(event) => void updateStatus(item.id, event.target.value as RecommendationStatus)}>{STATUSES.map((status) => <option key={status} value={status}>{readable(status)}</option>)}</select></label>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
