import { useCallback, useEffect, useMemo, useState } from "react";

type DiscoverySource = {
  source: "linkedin" | "indeed" | "jobgether" | "infojobs" | "adzuna";
  label: string;
  transport: "api" | "browser";
  saved_search_backend: string;
  execution_available: boolean;
};

type DiscoverySearch = {
  id: string;
  source: DiscoverySource["source"];
  label: string;
  definition: Record<string, unknown>;
  notes: string;
  enabled: boolean;
  max_jobs: number;
  created_at: string;
  updated_at: string;
  execution_available: boolean;
};

type Props = {
  apiBase: string;
  active: boolean;
};

function sourceLabel(source: DiscoverySearch["source"]) {
  switch (source) {
    case "linkedin": return "LinkedIn";
    case "indeed": return "Indeed";
    case "jobgether": return "Jobgether";
    case "infojobs": return "InfoJobs";
    case "adzuna": return "Adzuna";
  }
}

export function DiscoverySearchQueue({ apiBase, active }: Props) {
  const [sources, setSources] = useState<DiscoverySource[]>([]);
  const [searches, setSearches] = useState<DiscoverySearch[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [sourceFilter, setSourceFilter] = useState<"all" | DiscoverySearch["source"]>("all");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [sourcesResponse, searchesResponse] = await Promise.all([
      fetch(`${apiBase}/api/discovery-sources`),
      fetch(`${apiBase}/api/discovery-searches`),
    ]);
    if (!sourcesResponse.ok || !searchesResponse.ok) {
      throw new Error("Unable to load multi-source discovery searches.");
    }
    const loadedSources = (await sourcesResponse.json()) as DiscoverySource[];
    const loadedSearches = (await searchesResponse.json()) as DiscoverySearch[];
    setSources(loadedSources);
    setSearches(loadedSearches);
    setSelectedIds((current) => {
      const enabled = new Set(loadedSearches.filter((item) => item.enabled).map((item) => item.id));
      return current.filter((id) => enabled.has(id));
    });
  }, [apiBase]);

  useEffect(() => {
    if (!active) return;
    void load().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Unable to load discovery searches.");
    });
  }, [active, load]);

  const filtered = useMemo(
    () => searches.filter((item) => item.enabled && (sourceFilter === "all" || item.source === sourceFilter)),
    [searches, sourceFilter],
  );

  const selected = useMemo(
    () => selectedIds.map((id) => searches.find((item) => item.id === id)).filter((item): item is DiscoverySearch => Boolean(item)),
    [searches, selectedIds],
  );

  function toggle(search: DiscoverySearch, checked: boolean) {
    setSelectedIds((current) => {
      if (checked) return current.includes(search.id) ? current : [...current, search.id];
      return current.filter((id) => id !== search.id);
    });
  }

  function move(id: string, direction: -1 | 1) {
    setSelectedIds((current) => {
      const index = current.indexOf(id);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  const allExecutable = selected.length > 0 && selected.every((item) => item.execution_available);

  return (
    <section className="panel discovery-search-queue" aria-labelledby="discovery-search-queue-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Multi-source discovery</p>
          <h2 id="discovery-search-queue-heading">Discovery queue</h2>
          <p>Select independent saved searches from any portal and set the order in which JOLT should run them.</p>
        </div>
        <span className="professional-plan-status">{sources.length} sources registered</span>
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      <div className="search-portfolio-toolbar">
        <label>
          Portal
          <select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value as "all" | DiscoverySearch["source"])}
          >
            <option value="all">All portals</option>
            {sources.map((source) => (
              <option key={source.source} value={source.source}>{source.label}</option>
            ))}
          </select>
        </label>
        <div className="button-row">
          <button
            type="button"
            className="secondary"
            disabled={!filtered.length}
            onClick={() => setSelectedIds(filtered.map((item) => item.id))}
          >
            Select visible
          </button>
          <button type="button" className="secondary" disabled={!selectedIds.length} onClick={() => setSelectedIds([])}>
            Clear
          </button>
        </div>
      </div>

      <div className="discovery-source-status-grid" aria-label="Discovery source status">
        {sources.map((source) => (
          <div key={source.source}>
            <strong>{source.label}</strong>
            <span>{source.transport.toUpperCase()} · {source.execution_available ? "Ready" : "Connector pending"}</span>
          </div>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p>No enabled searches are saved for this portal yet.</p>
      ) : (
        <div className="search-portfolio-list">
          {filtered.map((search) => {
            const selectedIndex = selectedIds.indexOf(search.id);
            return (
              <article className="search-portfolio-row" key={search.id}>
                <label className="search-portfolio-check">
                  <input
                    type="checkbox"
                    checked={selectedIndex >= 0}
                    onChange={(event) => toggle(search, event.target.checked)}
                    aria-label={`Select ${sourceLabel(search.source)} · ${search.label}`}
                  />
                </label>
                <div className="search-portfolio-main">
                  <strong>{search.label}</strong>
                  <span>{sourceLabel(search.source)} · {search.max_jobs} jobs max · {search.execution_available ? "ready" : "connector pending"}</span>
                </div>
                {selectedIndex >= 0 && (
                  <div className="discovery-order-controls" aria-label={`Order ${search.label}`}>
                    <span>#{selectedIndex + 1}</span>
                    <button type="button" className="secondary" aria-label={`Move ${search.label} up`} disabled={selectedIndex === 0} onClick={() => move(search.id, -1)}>↑</button>
                    <button type="button" className="secondary" aria-label={`Move ${search.label} down`} disabled={selectedIndex === selectedIds.length - 1} onClick={() => move(search.id, 1)}>↓</button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      <div className="discovery-queue-preview">
        <strong>Execution order ({selected.length})</strong>
        {selected.length ? (
          <ol>
            {selected.map((search) => (
              <li key={search.id}><span>{sourceLabel(search.source)}</span> · {search.label}</li>
            ))}
          </ol>
        ) : (
          <p>Select searches above to build this run.</p>
        )}
      </div>

      <button type="button" disabled={!allExecutable} title={allExecutable ? "" : "Multi-source execution will unlock as portal connectors are attached."}>
        Run discovery ({selected.length})
      </button>
      {!allExecutable && selected.length > 0 && (
        <small>Selection and ordering are active now. Execution remains disabled while selected portal connectors are pending.</small>
      )}
    </section>
  );
}
