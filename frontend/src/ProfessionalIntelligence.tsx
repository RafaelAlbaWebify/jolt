import { useCallback, useEffect, useMemo, useState } from "react";

import { ProfessionalCapturePlan } from "./ProfessionalCapturePlan";
import {
  ProfessionalCaptureRuns,
  type ProfessionalCaptureOptions,
} from "./ProfessionalCaptureRuns";
import { ProfessionalEvidenceRoot } from "./ProfessionalEvidenceRoot";
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

const DEFAULT_CAPTURE_OPTIONS: ProfessionalCaptureOptions = {
  max_sources: 3,
  max_scroll_batches: 2,
  max_items_per_source: 25,
  timeout_seconds: 30,
  stop_on_failure: true,
};

export function ProfessionalIntelligence({ apiBase, active }: Props) {
  const [sources, setSources] = useState<ProfessionalIntelligenceSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [busySourceId, setBusySourceId] = useState<string | null>(null);
  const [planRefreshKey, setPlanRefreshKey] = useState(0);
  const [captureOptions] = useState(DEFAULT_CAPTURE_OPTIONS);
  const [error, setError] = useState("");

  const loadSources = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/sources`);
      if (!response.ok) throw new Error("Unable to load Professional Intelligence sources.");
      setSources((await response.json()) as ProfessionalIntelligenceSource[]);
      setLoaded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Source registry failed.");
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (!active || loaded) return;
    void loadSources();
  }, [active, loadSources, loaded]);

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
          <div className="professional-source-grid professional-source-grid-compact">
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
    <main className="professional-intelligence professional-intelligence-dashboard" aria-labelledby="professional-intelligence-heading">
      {active && (
        <ProfessionalCaptureRuns
          apiBase={apiBase}
          active={active}
          planRefreshKey={planRefreshKey}
          captureOptions={captureOptions}
        />
      )}

      <details className="panel professional-advanced-section">
        <summary>
          <span>
            <strong>Professional configuration and source registry</strong>
            <small>Evidence directory, capture plan, and approved source maintenance.</small>
          </span>
        </summary>

        <div className="professional-advanced-grid">
          {active && (
            <ProfessionalEvidenceRoot
              apiBase={apiBase}
              active={active}
              onChanged={() => setPlanRefreshKey((current) => current + 1)}
            />
          )}
          {active && <ProfessionalCapturePlan apiBase={apiBase} active={active} refreshKey={planRefreshKey} />}
        </div>

        <section className="professional-registry-panel" aria-labelledby="professional-registry-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Approved LinkedIn source registry</p>
              <h2 id="professional-registry-heading">Source maintenance</h2>
              <p>These approved sources are retained for maintenance, but they are not the primary capture workflow.</p>
            </div>
            {loading && <span className="professional-plan-status">Loading</span>}
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          {error && !loaded && (
            <button type="button" className="secondary" disabled={loading} onClick={() => void loadSources()}>
              Retry source registry
            </button>
          )}
          {loaded && (
            <>
              <details className="professional-source-registry-details">
                <summary>Initial supervised scope · {initialSources.length} sources</summary>
                {renderSources(initialSources)}
              </details>
              <details className="professional-source-registry-details">
                <summary>Deferred sources · {deferredSources.length} sources</summary>
                {renderSources(deferredSources)}
              </details>
            </>
          )}
        </section>
      </details>
    </main>
  );
}
