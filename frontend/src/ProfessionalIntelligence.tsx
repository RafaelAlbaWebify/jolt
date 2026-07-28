import { useCallback, useEffect, useMemo, useState } from "react";

import { ProfessionalCapturePlan } from "./ProfessionalCapturePlan";
import {
  ProfessionalCaptureRuns,
  type ProfessionalCaptureOptions,
} from "./ProfessionalCaptureRuns";
import { ProfessionalEvidenceRoot } from "./ProfessionalEvidenceRoot";
import { ProfessionalExecutionReadiness } from "./ProfessionalExecutionReadiness";
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
  const [readinessRefreshKey, setReadinessRefreshKey] = useState(0);
  const [captureStartRequestKey, setCaptureStartRequestKey] = useState(0);
  const [captureOptions, setCaptureOptions] = useState(DEFAULT_CAPTURE_OPTIONS);
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

  function setNumericCaptureOption(
    key: "max_sources" | "max_scroll_batches" | "max_items_per_source" | "timeout_seconds",
    value: string,
  ) {
    setCaptureOptions((current) => ({ ...current, [key]: Number(value) }));
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
          <p className="eyebrow">Approved LinkedIn source registry</p>
          <h2 id="professional-intelligence-heading">Professional</h2>
          <p>Capture the approved sources, keep the evidence locally, and review the result.</p>
        </div>
        <div className="professional-overview-actions">
          <div className="professional-capture-controls" aria-label="Capture settings">
            <div className="professional-capture-settings-grid">
              <label>
                Maximum sources
                <input
                  type="number"
                  min="1"
                  max="12"
                  value={captureOptions.max_sources}
                  onChange={(event) => setNumericCaptureOption("max_sources", event.target.value)}
                />
              </label>
              <label>
                Scroll batches per source
                <input
                  type="number"
                  min="0"
                  max="20"
                  value={captureOptions.max_scroll_batches}
                  onChange={(event) => setNumericCaptureOption("max_scroll_batches", event.target.value)}
                />
              </label>
              <label>
                Maximum items per source
                <input
                  type="number"
                  min="1"
                  max="200"
                  value={captureOptions.max_items_per_source}
                  onChange={(event) => setNumericCaptureOption("max_items_per_source", event.target.value)}
                />
              </label>
              <label>
                Timeout per source (seconds)
                <input
                  type="number"
                  min="10"
                  max="120"
                  value={captureOptions.timeout_seconds}
                  onChange={(event) => setNumericCaptureOption("timeout_seconds", event.target.value)}
                />
              </label>
            </div>
            <label className="professional-source-checkbox">
              <input
                type="checkbox"
                checked={captureOptions.stop_on_failure}
                onChange={(event) => setCaptureOptions((current) => ({
                  ...current,
                  stop_on_failure: event.target.checked,
                }))}
              />
              Stop the run after the first failed source.
            </label>
            <button
              type="button"
              disabled={!active}
              aria-controls="professional-run-ledger"
              onClick={() => setCaptureStartRequestKey((current) => current + 1)}
            >
              Start capture
            </button>
            <span>LinkedIn result lists use scrolling, so “scroll batches” is the page limit.</span>
          </div>
          <div className="professional-safety-boundary" role="note">
            <strong>Read-only boundary</strong>
            <span>No messages, reactions, applications, invitations, or account changes.</span>
          </div>
        </div>
      </section>

      {active && (
        <ProfessionalEvidenceRoot
          apiBase={apiBase}
          active={active}
          onChanged={() => setReadinessRefreshKey((current) => current + 1)}
        />
      )}
      {active && (
        <ProfessionalExecutionReadiness
          key={readinessRefreshKey}
          apiBase={apiBase}
          active={active}
        />
      )}
      {active && <ProfessionalCapturePlan apiBase={apiBase} active={active} refreshKey={planRefreshKey} />}
      {active && (
        <ProfessionalCaptureRuns
          apiBase={apiBase}
          active={active}
          planRefreshKey={planRefreshKey}
          captureOptions={captureOptions}
          startRequestKey={captureStartRequestKey}
        />
      )}
      {loading && <p role="status">Loading source registry…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {error && !loaded && <button type="button" className="secondary" disabled={loading} onClick={() => void loadSources()}>Retry source registry</button>}
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
