import { useCallback, useEffect, useMemo, useState } from "react";

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

  const loadBatches = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/linkedin-discovery-batches`);
    if (!response.ok) throw await responseError(response, "Unable to load discovery batches.");
    const batches = (await response.json()) as DiscoveryBatch[];
    const activeBatch = batches.find((item) => !terminalBatch(item.status));
    setBatch(activeBatch ?? batches[0] ?? null);
  }, [apiBase]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([loadSearches(), loadBatches()]);
    } finally {
      setLoading(false);
    }
  }, [loadBatches, loadSearches]);

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
            await loadSearches();
          }
        })
        .catch((caught) => {
          setError(caught instanceof Error ? caught.message : "Unable to refresh discovery batch.");
        });
    }, 2_000);
    return () => window.clearInterval(interval);
  }, [active, apiBase, batch, loadSearches]);

  const selectedSearches = useMemo(
    () => searches.filter((item) => selectedIds.has(item.id) && item.enabled),
    [searches, selectedIds],
  );

  function toggleSelected(id: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function beginEdit(search?: SavedSearch) {
    if (!search) {
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
      setSelectedIds((current) => new Set(current).add(saved.id));
      setNotice(draft.id ? "Saved search updated." : "Saved search added and selected.");
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
        throw await responseError(createResponse, "The discovery batch could not be created.");
      }
      const created = (await createResponse.json()) as DiscoveryBatch;
      const startResponse = await fetch(
        `${apiBase}/api/linkedin-discovery-batches/${created.id}/start`,
        { method: "POST" },
      );
      if (!startResponse.ok) {
        throw await responseError(startResponse, "The discovery batch could not start.");
      }
      setBatch((await startResponse.json()) as DiscoveryBatch);
      setNotice("Discovery started. JOLT will reuse one visible Chromium session for the selected searches.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The discovery batch could not start.");
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
      if (!response.ok) throw await responseError(response, "The batch AI review could not be imported.");
      const result = (await response.json()) as {
        received_count: number;
        created_count: number;
        updated_count: number;
      };
      setNotice(
        `AI review imported: ${result.received_count} jobs · ${result.created_count} new · ${result.updated_count} updated.`,
      );
      onAIImported?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The batch AI review could not be imported.");
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
          <p className="eyebrow">Primary job discovery</p>
          <h2 id="linkedin-search-portfolio-heading">Saved LinkedIn searches</h2>
          <p>
            Select the searches you want to run. JOLT opens one visible Chromium session, captures each
            search sequentially, deduplicates canonical jobs, and prepares one AI review set.
          </p>
        </div>
        <button type="button" className="secondary" onClick={() => beginEdit()} disabled={busy}>
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
          <strong>{selectedSearches.length}</strong> of {searches.filter((item) => item.enabled).length} enabled searches selected
        </div>
        <div className="button-row">
          <button
            type="button"
            className="secondary"
            disabled={busy || searches.every((item) => !item.enabled)}
            onClick={() => setSelectedIds(new Set(searches.filter((item) => item.enabled).map((item) => item.id)))}
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
            {batchIsActive ? "Discovery running…" : `Start discovery (${selectedSearches.length})`}
          </button>
        </div>
      </div>

      {loading && searches.length === 0 ? (
        <p>Loading saved searches…</p>
      ) : searches.length === 0 ? (
        <div className="search-portfolio-empty">
          <strong>No saved searches yet.</strong>
          <p>Add your first LinkedIn job search URL, give it a useful name, then select it for discovery.</p>
        </div>
      ) : (
        <div className="search-portfolio-list">
          {searches.map((search) => (
            <article className={`search-portfolio-row${search.enabled ? "" : " search-portfolio-row-disabled"}`} key={search.id}>
              <label className="search-portfolio-check">
                <input
                  type="checkbox"
                  checked={selectedIds.has(search.id)}
                  disabled={!search.enabled || busy || batchIsActive}
                  onChange={(event) => toggleSelected(search.id, event.target.checked)}
                  aria-label={`Select ${search.label}`}
                />
              </label>
              <div className="search-portfolio-main">
                <strong>{search.label}</strong>
                <span>{search.enabled ? "Enabled" : "Disabled"} · {search.max_jobs} jobs · {search.max_pages} pages</span>
                <a href={search.search_url} target="_blank" rel="noreferrer">{search.search_url}</a>
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
      )}

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
              Refresh batch
            </button>
          </div>

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

          {canExportReview && (
            <div className="batch-review-actions">
              <a
                className="primary-link"
                href={`${apiBase}/api/linkedin-discovery-batches/${batch.id}/ai-review-exchange`}
                target="_blank"
                rel="noreferrer"
              >
                Download one AI review exchange
              </a>
              <label className="batch-review-import">
                Import returned AI review
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
        </section>
      )}
    </section>
  );
}
