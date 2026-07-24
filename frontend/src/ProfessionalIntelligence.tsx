import { useEffect, useMemo, useState } from "react";

import { ProfessionalCapturePlan } from "./ProfessionalCapturePlan";
import { ProfessionalCaptureRuns } from "./ProfessionalCaptureRuns";
import { ProfessionalSourceEditor } from "./ProfessionalSourceEditor";

export type ProfessionalIntelligenceSource = {
  source_id: string;
  label: string;
  category: "profile" | "network" | "career";
  url: string;
  initial_scope: boolean;
  enabled: boolean;
  capture_mode: "supervised_read_only";
};

type SourceUpdate = Pick<
  ProfessionalIntelligenceSource,
  "label" | "url" | "initial_scope" | "enabled"
>;

type Props = {
  apiBase: string;
  active: boolean;
};

const CATEGORY_LABELS: Record<ProfessionalIntelligenceSource["category"], string> = {
  profile: "Profile and positioning",
  career: "Career signals",
  network: "Network and discovery",
};

export function ProfessionalIntelligence({ apiBase, active }: Props) {
  const [sources, setSources] = useState<ProfessionalIntelligenceSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [busySourceId, setBusySourceId] = useState<string | null>(null);
  const [planRefreshKey, setPlanRefreshKey] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active || loaded || loading) return;
    setLoading(true);
    setError("");
    fetch(`${apiBase}/api/professional-intelligence/sources`)
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load Professional Intelligence sources.");
        return response.json() as Promise<ProfessionalIntelligenceSource[]>;
      })
      .then((items) => {
        setSources(items);
        setLoaded(true);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Source registry failed."))
      .finally(() => setLoading(false));
  }, [active, apiBase, loaded, loading]);

  const initialSources = useMemo(() => sources.filter((source) => source.initial_scope), [sources]);
  const deferredSources = useMemo(() => sources.filter((source) => !source.initial_scope), [sources]);

  function replaceSource(changed: ProfessionalIntelligenceSource) {
    setSources((current) => current.map((source) => (
      source.source_id === changed.source_id ? changed : source
    )));
  }

  async function runSourceAction(sourceId: string, path: string, body?: SourceUpdate) {
    setBusySourceId(sourceId);
    setError("");
    try {
      const response = await fetch(`${apiBase}${path}`, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The source registry change could not be saved.");
      }
      replaceSource((await response.json()) as ProfessionalIntelligenceSource);
      setPlanRefreshKey((current) => current + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected source registry error.");
    } finally {
      setBusySourceId(null);
    }
  }

  async function saveSource(sourceId: string, update: SourceUpdate) {
    await runSourceAction(
      sourceId,
      `/api/professional-intelligence/sources/${sourceId}/update`,
      update,
    );
  }

  async function resetSource(sourceId: string) {
    await runSourceAction(sourceId, `/api/professional-intelligence/sources/${sourceId}/reset`);
  }

  function renderSources(items: ProfessionalIntelligenceSource[]) {
    const categories: ProfessionalIntelligenceSource["category"][] = ["profile", "career", "network"];
    return categories.map((category) => {
      const categorySources = items.filter((source) => source.category === category);
      if (categorySources.length === 0) return null;
      return (
        <section className="professional-source-group" key={category}>
          <h3>{CATEGORY_LABELS[category]}</h3>
          <div className="professional-source-grid">
            {categorySources.map((source) => (
              <article
                className={`professional-source-card${source.enabled ? "" : " professional-source-disabled"}`}
                key={source.source_id}
              >
                <div className="professional-source-card-heading">
                  <div>
                    <p className="eyebrow">{source.capture_mode.replaceAll("_", " ")}</p>
                    <h4>{source.label}</h4>
                  </div>
                  <span className="professional-source-status">
                    {source.enabled ? "Enabled" : "Disabled"}
                  </span>
                </div>
                <a href={source.url} target="_blank" rel="noreferrer">Open approved source</a>
                <ProfessionalSourceEditor
                  source={source}
                  busy={busySourceId === source.source_id}
                  onSave={saveSource}
                  onReset={resetSource}
                />
              </article>
            ))}
          </div>
        </section>
      );
    });
  }

  return (
    <main className="professional-intelligence" aria-labelledby="professional-intelligence-heading">
      <section className="panel professional-intelligence-overview">
        <div>
          <p className="eyebrow">Professional Intelligence</p>
          <h2 id="professional-intelligence-heading">Approved LinkedIn source registry</h2>
          <p>Edit only the confirmed source set before any supervised evidence capture is introduced. Every change is stored locally and can be reset to its verified default.</p>
        </div>
        <div className="professional-safety-boundary" role="note">
          <strong>Read-only boundary</strong>
          <span>No login handling, stored credentials, cookies, messages, reactions, applications, invitations, or unattended account actions.</span>
        </div>
      </section>

      {active && <ProfessionalCapturePlan apiBase={apiBase} active={active} refreshKey={planRefreshKey} />}
      {active && <ProfessionalCaptureRuns apiBase={apiBase} active={active} planRefreshKey={planRefreshKey} />}
      {loading && <p role="status">Loading source registry…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {loaded && (
        <>
          <section className="panel" aria-labelledby="initial-professional-sources-heading">
            <div className="section-heading">
              <div><h2 id="initial-professional-sources-heading">Initial supervised scope</h2><p>{initialSources.length} sources prioritised for profile positioning and career signals.</p></div>
            </div>
            {renderSources(initialSources)}
          </section>
          <section className="panel" aria-labelledby="deferred-professional-sources-heading">
            <div className="section-heading">
              <div><h2 id="deferred-professional-sources-heading">Deferred sources</h2><p>{deferredSources.length} broader network and feed sources retained but excluded from the first capture slice.</p></div>
            </div>
            {renderSources(deferredSources)}
          </section>
        </>
      )}
    </main>
  );
}
