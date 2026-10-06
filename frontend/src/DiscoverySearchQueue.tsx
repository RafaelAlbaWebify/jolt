import { useCallback, useEffect, useMemo, useState } from "react";

type DiscoverySourceId = "linkedin" | "indeed" | "jobgether" | "infojobs" | "adzuna";

type DiscoverySource = {
  source: DiscoverySourceId;
  label: string;
  transport: "api" | "browser";
  saved_search_backend: string;
  execution_available: boolean;
};

type DiscoverySearch = {
  id: string;
  source: DiscoverySourceId;
  label: string;
  definition: Record<string, unknown>;
  notes: string;
  enabled: boolean;
  max_jobs: number;
  created_at: string;
  updated_at: string;
  execution_available: boolean;
};

type SearchDraft = {
  id: string | null;
  source: DiscoverySourceId;
  label: string;
  search_url: string;
  notes: string;
  enabled: boolean;
  max_jobs: number;
  max_pages: number;
};

type Props = {
  apiBase: string;
  active: boolean;
};

function sourceLabel(source: DiscoverySourceId) {
  switch (source) {
    case "linkedin": return "LinkedIn";
    case "indeed": return "Indeed";
    case "jobgether": return "Jobgether";
    case "infojobs": return "InfoJobs";
    case "adzuna": return "Adzuna";
  }
}

function editorSupported(source: DiscoverySourceId) {
  return source === "linkedin" || source === "indeed";
}

function responseError(response: Response, fallback: string) {
  return response.json().catch(() => null).then((payload: { detail?: unknown } | null) => {
    if (typeof payload?.detail === "string" && payload.detail.trim()) {
      return new Error(payload.detail);
    }
    return new Error(fallback);
  });
}

export function DiscoverySearchQueue({ apiBase, active }: Props) {
  const [sources, setSources] = useState<DiscoverySource[]>([]);
  const [searches, setSearches] = useState<DiscoverySearch[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [sourceFilter, setSourceFilter] = useState<"all" | DiscoverySourceId>("all");
  const [draft, setDraft] = useState<SearchDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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

  const editorSources = useMemo(() => sources.filter((source) => editorSupported(source.source)), [sources]);

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

  function beginAdd() {
    const source = sourceFilter !== "all" && editorSupported(sourceFilter) ? sourceFilter : "indeed";
    setDraft({
      id: null,
      source,
      label: "",
      search_url: "",
      notes: "",
      enabled: true,
      max_jobs: source === "linkedin" ? 50 : 30,
      max_pages: source === "linkedin" ? 5 : 3,
    });
    setError("");
    setNotice("");
  }

  function beginEdit(search: DiscoverySearch) {
    if (!editorSupported(search.source)) return;
    setDraft({
      id: search.id,
      source: search.source,
      label: search.label,
      search_url: String(search.definition.search_url ?? ""),
      notes: search.notes,
      enabled: search.enabled,
      max_jobs: search.max_jobs,
      max_pages: Number(search.definition.max_pages ?? (search.source === "linkedin" ? 5 : 3)),
    });
    setError("");
    setNotice("");
  }

  async function saveDraft() {
    if (!draft || !draft.label.trim() || !draft.search_url.trim()) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      let response: Response;
      if (draft.source === "linkedin") {
        const url = draft.id
          ? `${apiBase}/api/linkedin-searches/${draft.id}`
          : `${apiBase}/api/linkedin-searches`;
        response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            label: draft.label.trim(),
            search_url: draft.search_url.trim(),
            notes: draft.notes,
            enabled: draft.enabled,
            max_jobs: draft.max_jobs,
            max_pages: draft.max_pages,
          }),
        });
      } else {
        const url = draft.id
          ? `${apiBase}/api/discovery-searches/${draft.id}`
          : `${apiBase}/api/discovery-searches`;
        response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source: draft.source,
            label: draft.label.trim(),
            definition: {
              search_url: draft.search_url.trim(),
              max_pages: draft.max_pages,
            },
            notes: draft.notes,
            enabled: draft.enabled,
            max_jobs: draft.max_jobs,
          }),
        });
      }
      if (!response.ok) throw await responseError(response, "The saved search could not be saved.");
      setDraft(null);
      await load();
      setNotice("Saved search updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The saved search could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSearch(search: DiscoverySearch) {
    if (!editorSupported(search.source)) return;
    if (!window.confirm(`Delete "${search.label}"?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const url = search.source === "linkedin"
        ? `${apiBase}/api/linkedin-searches/${search.id}/delete`
        : `${apiBase}/api/discovery-searches/${search.id}/delete`;
      const response = await fetch(url, { method: "POST" });
      if (!response.ok) throw await responseError(response, "The saved search could not be deleted.");
      setSelectedIds((current) => current.filter((id) => id !== search.id));
      await load();
      setNotice("Saved search deleted.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The saved search could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  const allExecutable = selected.length > 0 && selected.every((item) => item.execution_available);

  return (
    <section className="panel discovery-search-queue" aria-labelledby="discovery-search-queue-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Multi-source discovery</p>
          <h2 id="discovery-search-queue-heading">Discovery queue</h2>
          <p>Manage portal-specific searches, select the ones you want, and set their execution order.</p>
        </div>
        <div className="button-row">
          <span className="professional-plan-status">{sources.length} sources registered</span>
          <button type="button" className="secondary" onClick={beginAdd} disabled={busy}>
            Add search
          </button>
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="application-move-notice" role="status">{notice}</p>}

      {draft && (
        <div className="search-portfolio-editor discovery-search-editor" role="dialog" aria-modal="true" aria-label={draft.id ? "Edit discovery search" : "Add discovery search"}>
          <div className="form-grid">
            <label>
              Portal
              <select
                value={draft.source}
                disabled={Boolean(draft.id)}
                onChange={(event) => {
                  const source = event.target.value as DiscoverySourceId;
                  setDraft({ ...draft, source });
                }}
              >
                {editorSources.map((source) => (
                  <option key={source.source} value={source.source}>{source.label}</option>
                ))}
              </select>
            </label>
            <label>
              Name
              <input value={draft.label} onChange={(event) => setDraft({ ...draft, label: event.target.value })} />
            </label>
            <label className="full-width">
              {draft.source === "linkedin" ? "LinkedIn search URL" : "Indeed search URL"}
              <input
                type="url"
                value={draft.search_url}
                onChange={(event) => setDraft({ ...draft, search_url: event.target.value })}
                placeholder={draft.source === "linkedin" ? "https://www.linkedin.com/jobs/search/?..." : "https://es.indeed.com/jobs?q=..."}
              />
            </label>
            <label>
              Maximum jobs
              <input type="number" min={1} max={100} value={draft.max_jobs} onChange={(event) => setDraft({ ...draft, max_jobs: Number(event.target.value) })} />
            </label>
            <label>
              Maximum pages
              <input type="number" min={1} max={10} value={draft.max_pages} onChange={(event) => setDraft({ ...draft, max_pages: Number(event.target.value) })} />
            </label>
            <label>
              Enabled
              <select value={draft.enabled ? "yes" : "no"} onChange={(event) => setDraft({ ...draft, enabled: event.target.value === "yes" })}>
                <option value="yes">Enabled</option>
                <option value="no">Disabled</option>
              </select>
            </label>
            <label className="full-width">
              Notes
              <textarea rows={2} value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
            </label>
          </div>
          <div className="button-row">
            <button type="button" onClick={() => void saveDraft()} disabled={busy || !draft.label.trim() || !draft.search_url.trim()}>
              {busy ? "Saving…" : "Save search"}
            </button>
            <button type="button" className="secondary" onClick={() => setDraft(null)} disabled={busy}>Cancel</button>
          </div>
        </div>
      )}

      <div className="search-portfolio-toolbar">
        <label>
          Portal
          <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as "all" | DiscoverySourceId)}>
            <option value="all">All portals</option>
            {sources.map((source) => (
              <option key={source.source} value={source.source}>{source.label}</option>
            ))}
          </select>
        </label>
        <div className="button-row">
          <button type="button" className="secondary" disabled={!filtered.length} onClick={() => setSelectedIds(filtered.map((item) => item.id))}>Select visible</button>
          <button type="button" className="secondary" disabled={!selectedIds.length} onClick={() => setSelectedIds([])}>Clear</button>
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
        <div className="search-portfolio-empty">
          <strong>No enabled searches are saved for this portal yet.</strong>
          {sourceFilter !== "all" && editorSupported(sourceFilter) && (
            <button type="button" className="secondary" onClick={beginAdd}>Add {sourceLabel(sourceFilter)} search</button>
          )}
        </div>
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
                <div className="discovery-row-actions">
                  {editorSupported(search.source) && (
                    <>
                      <button type="button" className="secondary" onClick={() => beginEdit(search)} disabled={busy}>Edit</button>
                      <button type="button" className="secondary" onClick={() => void deleteSearch(search)} disabled={busy}>Delete</button>
                    </>
                  )}
                  {selectedIndex >= 0 && (
                    <div className="discovery-order-controls" aria-label={`Order ${search.label}`}>
                      <span>#{selectedIndex + 1}</span>
                      <button type="button" className="secondary" aria-label={`Move ${search.label} up`} disabled={selectedIndex === 0} onClick={() => move(search.id, -1)}>↑</button>
                      <button type="button" className="secondary" aria-label={`Move ${search.label} down`} disabled={selectedIndex === selectedIds.length - 1} onClick={() => move(search.id, 1)}>↓</button>
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      <div className="discovery-queue-preview">
        <strong>Execution order ({selected.length})</strong>
        {selected.length ? (
          <ol>{selected.map((search) => <li key={search.id}><span>{sourceLabel(search.source)}</span> · {search.label}</li>)}</ol>
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
