import { useEffect, useMemo, useState } from "react";

export type ProfessionalIntelligenceSource = {
  source_id: string;
  label: string;
  category: "profile" | "network" | "career";
  url: string;
  initial_scope: boolean;
  capture_mode: "supervised_read_only";
};

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
              <article className="professional-source-card" key={source.source_id}>
                <div>
                  <p className="eyebrow">{source.capture_mode.replaceAll("_", " ")}</p>
                  <h4>{source.label}</h4>
                </div>
                <a href={source.url} target="_blank" rel="noreferrer">Open approved source</a>
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
          <p>Review the exact user-approved sources before any supervised evidence capture is introduced.</p>
        </div>
        <div className="professional-safety-boundary" role="note">
          <strong>Read-only boundary</strong>
          <span>No login handling, stored credentials, cookies, messages, reactions, applications, invitations, or unattended account actions.</span>
        </div>
      </section>

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
