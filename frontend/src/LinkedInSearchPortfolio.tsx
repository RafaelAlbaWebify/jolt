import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type SavedSearch = {
  id: string;
  label: string;
  search_url: string;
  notes: string;
  enabled: boolean;
  max_jobs: number;
  max_pages: number;
  created_at: string;
  updated_at: string;
};

type BatchSearch = {
  id: string;
  saved_search_id: string;
  position: number;
  label: string;
  search_url: string;
  max_jobs: number;
  max_pages: number;
  status: string;
  capture_run_id: string | null;
  captured_count: number;
  verified_count: number;
  new_posting_count: number;
  duplicate_count: number;
  error: string;
  started_at: string | null;
  completed_at: string | null;
};

type DiscoveryBatch = {
  id: string;
  status: string;
  selected_search_count: number;
  completed_search_count: number;
  failed_search_count: number;
  captured_count: number;
  verified_count: number;
  new_posting_count: number;
  duplicate_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  searches: BatchSearch[];
};

type SearchPerformance = {
  saved_search_id: string;
  label: string;
  enabled: boolean;
  completed_runs: number;
  captured_count: number;
  verified_count: number;
  new_posting_count: number;
  duplicate_count: number;
  canonical_posting_count: number;
  ai_reviewed_count: number;
  ai_strong_pursue_count: number;
  ai_pursue_count: number;
  ai_conditional_count: number;
  ai_actionable_count: number;
  human_pursue_count: number;
  application_count: number;
  applied_count: number;
  interview_count: number;
  offer_count: number;
  accepted_offer_count: number;
};

type SearchDraft = {
  id: string | null;
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
  onAIImported?: () => void;
};

const EMPTY_DRAFT: SearchDraft = {
  id: null,
  label: "",
  search_url: "",
  notes: "",
  enabled: true,
  max_jobs: 100,
  max_pages: 10,
};

function terminalBatch(status: string) {
  return status === "completed" || status === "completed_with_failures" || status === "failed";
}

async function responseError(response: Response, fallback: string) {
  const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  if (typeof payload?.detail === "string" && payload.detail.trim()) {
    return new Error(payload.detail);
  }
  return new Error(fallback);
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ");
}

export function LinkedInSearchPortfolio({ apiBase, active, onAIImported }: Props) {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batch, setBatch] = useState<DiscoveryBatch | null>(null);
  const [performance, setPerformance] = useState<SearchPerformance[]>([]);
  const [performanceError, setPerformanceError] = useState("");
  const searchEditorNameRef = useRef<HTMLInputElement | null>(null);
  const searchEditorReturnFocusRef = useRef<HTMLElement | null>(null);
  const [draft, setDraft] = useState<SearchDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadSearches = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/linkedin-searches`);
    if (!response.ok) throw await responseError(response, "Unable to load saved LinkedIn searches.");
    const loaded = (await response.json()) as SavedSearch[];
    setSearches(loaded);
    setSelectedIds((current) => {
      const enabledIds = new Set(loaded.filter((item) => item.enabled).map((item) => item.id));
      return new Set([...current].filter((id) => enabledIds.has(id)));
    });
  }, [apiBase]);

  const loadPerformance = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/linkedin-search-performance`);
    if (!response.ok) throw await responseError(response, "Unable to load search performance.");
    setPerformance((await response.json()) as SearchPerformance[]);
    setPerformanceError("");
  }, [apiBase]);

  const loadBatches = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/linkedin-discovery-batches`);
    if (!response.ok) throw await responseError(response, "Unable to load discovery batches.");
    const batches = (await response.json()) as DiscoveryBatch[];
    const activeBatch = batches.find((item) => !terminalBatch(item.status));
    setBatch(activeBatch ?? batches[0] ?? null);
  }, [apiBase]);

  const editorOpen = Boolean(draft);

  useEffect(() => {
    if (!editorOpen) return;

    const timer = window.setTimeout(() => searchEditorNameRef.current?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        setDraft(null);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKeyDown);
      searchEditorReturnFocusRef.current?.focus();
    };
  }, [editorOpen, busy]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadSearches(),
        loadBatches(),
        loadPerformance().catch((caught) => {
          setPerformanceError(
            caught instanceof Error ? caught.message : "Unable to load search performance.",
          );
        }),
      ]);
    } finally {
      setLoading(false);
    }
  }, [loadBatches, loadPerformance, loadSearches]);

  useEffect(() => {
    if (!active) return;
    void refresh().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Unable to load LinkedIn search portfolio.");
    });
  }, [active, refresh]);

  useEffect(() => {
    if (!active || !batch || terminalBatch(batch.status)) return;
    const interval = window.setInterval(() => {
      void fetch(`${apiBase}/api/linkedin-discovery-batches/${batch.id}`)
        .then(async (response) => {
          if (!response.ok) throw await responseError(response, "Unable to refresh discovery batch.");
          const loaded = (await response.json()) as DiscoveryBatch;
          setBatch(loaded);
          if (terminalBatch(loaded.status)) {
            await Promise.all([loadSearches(), loadPerformance()]);
          }
        })
        .catch((caught) => {
          setError(caught instanceof Error ? caught.message : "Unable to refresh discovery batch.");
        });
    }, 2_000);
    return () => window.clearInterval(interval);
  }, [active, apiBase, batch, loadPerformance, loadSearches]);

  const enabledSearches = useMemo(
    () => searches.filter((item) => item.enabled),
    [searches],
  );
  const retiredSearches = useMemo(
    () => searches.filter((item) => !item.enabled),
    [searches],
  );
  const selectedSearches = useMemo(
    () => enabledSearches.filter((item) => selectedIds.has(item.id)),
    [enabledSearches, selectedIds],
  );

  const enabledPerformance = useMemo(
    () => performance.filter((item) => item.enabled),
    [performance],
  );

  function toggleSelected(id: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function beginEdit(search?: SavedSearch, trigger?: HTMLElement | null) {
    if (!search) {
      searchEditorReturnFocusRef.current =
      trigger ??
      (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    setDraft({ ...EMPTY_DRAFT });
      return;
    }
    setDraft({
      id: search.id,
      label: search.label,
      search_url: search.search_url,
      notes: search.notes,
      enabled: search.enabled,
      max_jobs: search.max_jobs,
      max_pages: search.max_pages,
    });
  }

  async function saveDraft() {
    if (!draft || !draft.label.trim() || !draft.search_url.trim()) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const url = draft.id
        ? `${apiBase}/api/linkedin-searches/${draft.id}`
        : `${apiBase}/api/linkedin-searches`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: draft.label,
          search_url: draft.search_url,
          notes: draft.notes,
          enabled: draft.enabled,
          max_jobs: draft.max_jobs,
          max_pages: draft.max_pages,
        }),
      });
      if (!response.ok) throw await responseError(response, "The saved search could not be saved.");
      const saved = (await response.json()) as SavedSearch;
      setDraft(null);
      await loadSearches();
      if (saved.enabled) {
        setSelectedIds((current) => new Set(current).add(saved.id));
      }
      setNotice(
        draft.id
          ? "Saved search updated."
          : saved.enabled
            ? "Saved search added and selected."
            : "Saved search added.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The saved search could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSearch(search: SavedSearch) {
    if (!window.confirm(`Delete "${search.label}"? Historical searches cannot be deleted; disable them instead.`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/linkedin-searches/${search.id}/delete`, {
        method: "POST",
      });
      if (!response.ok) throw await responseError(response, "The saved search could not be deleted.");
      await loadSearches();
      setNotice("Saved search deleted.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The saved search could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  async function startDiscovery() {
    if (selectedSearches.length === 0) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const createResponse = await fetch(`${apiBase}/api/linkedin-discovery-batches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ saved_search_ids: selectedSearches.map((item) => item.id) }),
      });
      if (!createResponse.ok) {
        throw await responseError(createResponse, "The search run could not be created.");
      }
      const created = (await createResponse.json()) as DiscoveryBatch;
      const startResponse = await fetch(
        `${apiBase}/api/linkedin-discovery-batches/${created.id}/start`,
        { method: "POST" },
      );
      if (!startResponse.ok) {
        throw await responseError(startResponse, "The search run could not start.");
      }
      setBatch((await startResponse.json()) as DiscoveryBatch);
      setNotice("Search run started. JOLT will use one visible LinkedIn session for the selected searches.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The search run could not start.");
    } finally {
      setBusy(false);
    }
  }

  async function importBatchReview(file: File) {
    if (!batch) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload = JSON.parse(await file.text()) as Record<string, unknown>;
      const response = await fetch(
        `${apiBase}/api/linkedin-discovery-batches/${batch.id}/ai-review-import`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (!response.ok) throw await responseError(response, "The reviewed jobs could not be imported.");
      const result = (await response.json()) as {
        received_count: number;
        created_count: number;
        updated_count: number;
      };
      setNotice(
        `Reviewed jobs imported: ${result.received_count} jobs · ${result.created_count} new · ${result.updated_count} updated.`,
      );
      await loadPerformance();
      onAIImported?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The reviewed jobs could not be imported.");
    } finally {
      setBusy(false);
    }
  }

  const batchIsActive = batch ? !terminalBatch(batch.status) : false;
  const canExportReview = batch?.status === "completed" || batch?.status === "completed_with_failures";

  return (
    <section className="panel linkedin-search-portfolio" aria-labelledby="linkedin-search-portfolio-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Job search</p>
          <h2 id="linkedin-search-portfolio-heading">Run LinkedIn searches</h2>
          <p>
            Choose the searches to run. JOLT checks them in one visible LinkedIn session, removes duplicates, and prepares only new jobs for review.
          </p>
        </div>
        <button
          type="button"
          className="secondary"
          onClick={(event) => beginEdit(undefined, event.currentTarget)}
          disabled={busy}
        >
          Add search
        </button>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="application-move-notice" role="status">{notice}</p>}

      {draft && (
        <div className="search-portfolio-editor" role="dialog" aria-modal="true" aria-label={draft.id ? "Edit saved search" : "Add saved search"}>
          <div className="form-grid">
            <label>
              Name
              <input
                ref={searchEditorNameRef}
                value={draft.label}
                onChange={(event) => setDraft({ ...draft, label: event.target.value })}
                placeholder="LinkedIn IT Support"
              />
            </label>
            <label>
              Enabled
              <select
                value={draft.enabled ? "yes" : "no"}
                onChange={(event) => setDraft({ ...draft, enabled: event.target.value === "yes" })}
              >
                <option value="yes">Enabled</option>
                <option value="no">Disabled</option>
              </select>
            </label>
            <label className="full-width">
              LinkedIn search URL
              <input
                type="url"
                value={draft.search_url}
                onChange={(event) => setDraft({ ...draft, search_url: event.target.value })}
                placeholder="https://www.linkedin.com/jobs/search/?..."
              />
            </label>
            <label>
              Maximum jobs
              <input
                type="number"
                min={1}
                max={100}
                value={draft.max_jobs}
                onChange={(event) => setDraft({ ...draft, max_jobs: Number(event.target.value) })}
              />
            </label>
            <label>
              Maximum pages
              <input
                type="number"
                min={1}
                max={10}
                value={draft.max_pages}
                onChange={(event) => setDraft({ ...draft, max_pages: Number(event.target.value) })}
              />
            </label>
            <label className="full-width">
              Notes
              <textarea
                rows={2}
                value={draft.notes}
                onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
              />
            </label>
          </div>
          <div className="button-row">
            <button type="button" onClick={() => void saveDraft()} disabled={busy || !draft.label.trim() || !draft.search_url.trim()}>
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" className="secondary" onClick={() => setDraft(null)} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="search-portfolio-toolbar">
        <div>
          <strong>{selectedSearches.length}</strong> of {enabledSearches.length} enabled searches selected
        </div>
        <div className="button-row">
          <button
            type="button"
            className="secondary"
            disabled={busy || enabledSearches.length === 0}
            onClick={() => setSelectedIds(new Set(enabledSearches.map((item) => item.id)))}
          >
            Select enabled
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy || selectedIds.size === 0}
            onClick={() => setSelectedIds(new Set())}
          >
            Clear
          </button>
          <button
            type="button"
            disabled={!active || busy || batchIsActive || selectedSearches.length === 0}
            onClick={() => void startDiscovery()}
          >
            {batchIsActive ? "Searches running…" : `Run searches (${selectedSearches.length})`}
          </button>
        </div>
      </div>

      {loading && searches.length === 0 ? (
        <p>Loading saved searches…</p>
      ) : searches.length === 0 ? (
        <div className="search-portfolio-empty">
          <strong>No saved searches yet.</strong>
          <p>Add your first LinkedIn job search URL, give it a useful name, then select it when you want to run it.</p>
        </div>
      ) : (
        <>
          <details className="active-searches-details" open={enabledSearches.length <= 8}>
            <summary>
              Search settings ({enabledSearches.length})
              <span>Advanced: names, URLs, limits, and search settings</span>
            </summary>
            <div className="search-portfolio-list">
            {enabledSearches.map((search) => (
              <article className="search-portfolio-row" key={search.id}>
                <label className="search-portfolio-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(search.id)}
                    disabled={busy || batchIsActive}
                    onChange={(event) => toggleSelected(search.id, event.target.checked)}
                    aria-label={`Select ${search.label}`}
                  />
                </label>
                <div className="search-portfolio-main">
                  <strong>{search.label}</strong>
                  <span>Enabled · {search.max_jobs} jobs · {search.max_pages} pages</span>
                  <details className="search-url-details">
                    <summary>Search URL</summary>
                    <a href={search.search_url} target="_blank" rel="noreferrer">Open LinkedIn search</a>
                  </details>
                  {search.notes && <p>{search.notes}</p>}
                </div>
                <details className="search-row-menu">
                  <summary aria-label={`Actions for ${search.label}`}>⋯</summary>
                  <div>
                    <button
                      type="button"
                      className="secondary"
                      onClick={(event) => beginEdit(search, event.currentTarget)}
                      disabled={busy || batchIsActive}
                    >
                      Edit
                    </button>
                    <button type="button" className="danger" onClick={() => void deleteSearch(search)} disabled={busy || batchIsActive}>
                      Delete
                    </button>
                  </div>
                </details>
              </article>
            ))}
            </div>
          </details>

          {retiredSearches.length > 0 && (
            <details className="retired-searches">
              <summary>Inactive searches ({retiredSearches.length})</summary>
              <p>Kept for history. They are excluded from normal search runs.</p>
              <div className="search-portfolio-list">
                {retiredSearches.map((search) => (
                  <article className="search-portfolio-row search-portfolio-row-disabled" key={search.id}>
                    <div className="search-portfolio-main search-portfolio-retired-main">
                      <strong>{search.label}</strong>
                      <span>Inactive · {search.max_jobs} jobs · {search.max_pages} pages</span>
                      <details className="search-url-details">
                        <summary>Search URL</summary>
                        <a href={search.search_url} target="_blank" rel="noreferrer">Open LinkedIn search</a>
                      </details>
                      {search.notes && <p>{search.notes}</p>}
                    </div>
                    <details className="search-row-menu">
                      <summary aria-label={`Actions for ${search.label}`}>⋯</summary>
                      <div>
                        <button type="button" className="secondary" onClick={() => beginEdit(search)} disabled={busy || batchIsActive}>
                          Edit
                        </button>
                        <button type="button" className="danger" onClick={() => void deleteSearch(search)} disabled={busy || batchIsActive}>
                          Delete
                        </button>
                      </div>
                    </details>
                  </article>
                ))}
              </div>
            </details>
          )}
        </>
      )}

      <details className="search-performance-details" open>
        <summary>
          Search performance ({enabledPerformance.length})
          <span>Observed funnel from capture to real application outcomes</span>
        </summary>
        {performanceError && <p className="error" role="alert">{performanceError}</p>}
        {enabledPerformance.length === 0 ? (
          <p className="search-performance-empty">
            No completed production search history yet. Metrics will appear after discoveries run.
          </p>
        ) : (
          <div className="search-performance-table-wrap">
            <table className="search-performance-table">
              <thead>
                <tr>
                  <th>Search</th>
                  <th>Captured</th>
                  <th>New</th>
                  <th>AI+</th>
                  <th>Human pursue</th>
                  <th>Applied</th>
                  <th>Interview</th>
                  <th>Offer</th>
                </tr>
              </thead>
              <tbody>
                {enabledPerformance.map((item) => (
                  <tr key={item.saved_search_id}>
                    <th scope="row">
                      <strong>{item.label}</strong>
                      <span>{item.completed_runs} completed run{item.completed_runs === 1 ? "" : "s"} · {item.canonical_posting_count} unique jobs</span>
                    </th>
                    <td>{item.captured_count}</td>
                    <td>{item.new_posting_count}</td>
                    <td>
                      <strong>{item.ai_actionable_count}</strong>
                      <span>
                        {item.ai_reviewed_count
                          ? `${Math.round((item.ai_actionable_count / item.ai_reviewed_count) * 100)}%`
                          : "—"}
                      </span>
                    </td>
                    <td>{item.human_pursue_count}</td>
                    <td>{item.applied_count}</td>
                    <td>{item.interview_count}</td>
                    <td>{item.offer_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="search-performance-note">
              AI+ = high priority + good match + check requirements. Applied counts only applications that reached submitted or a later stage; preparing alone is not counted. Overlapping searches share credit when both observed the same canonical job.
            </p>
          </div>
        )}
      </details>

      {batch && (
        <section className="discovery-batch-status" aria-labelledby="discovery-batch-status-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Latest discovery batch</p>
              <h3 id="discovery-batch-status-heading">{statusLabel(batch.status)}</h3>
              <p>
                {batch.completed_search_count}/{batch.selected_search_count} searches completed · {batch.captured_count} captured ·{" "}
                {batch.verified_count} verified · {batch.new_posting_count} new · {batch.duplicate_count} already known
              </p>
            </div>
            <button type="button" className="secondary" disabled={loading} onClick={() => void loadBatches()}>
              Refresh run
            </button>
          </div>

          {canExportReview && (
            <div className="batch-review-actions batch-review-actions-prominent">
              <a
                className="primary-link"
                href={`${apiBase}/api/linkedin-discovery-batches/${batch.id}/ai-review-exchange`}
                target="_blank"
                rel="noreferrer"
                title="Download only the new, deduplicated jobs from this search run for review in ChatGPT."
              >
                Export new jobs for review
              </a>
              <label className="batch-review-import">
                Import reviewed jobs
                <input
                  type="file"
                  accept="application/json,.json"
                  disabled={busy}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void importBatchReview(file);
                    event.currentTarget.value = "";
                  }}
                />
              </label>
            </div>
          )}

          <details className="batch-search-details" open={batchIsActive}>
            <summary>
              Search details ({batch.searches.length})
              <span>{batchIsActive ? "Running now" : "Expand to inspect each search"}</span>
            </summary>
            <div className="discovery-progress-list">
              {batch.searches.map((search) => (
                <article key={search.id}>
                  <div>
                    <strong>{search.position}. {search.label}</strong>
                    <span>{statusLabel(search.status)}</span>
                  </div>
                  <p>
                    {search.captured_count} captured · {search.verified_count} verified · {search.new_posting_count} new ·{" "}
                    {search.duplicate_count} known
                  </p>
                  {search.error && <p className="error">{search.error}</p>}
                </article>
              ))}
            </div>
          </details>
        </section>
      )}
    </section>
  );
}
