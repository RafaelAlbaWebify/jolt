import { useEffect, useMemo, useState } from "react";

type Opportunity = {
  posting_id: string;
  title: string;
  company: string;
  location: string;
};

type EvidenceItem = {
  source_document_id: string;
  source_type: string;
  source_url: string;
  identity_status: string;
  match_basis: string;
  captured_at: string;
};

type IdentityEvidence = {
  posting_id: string;
  canonical_url: string;
  identity_status: string;
  evidence_count: number;
  duplicate_evidence_count: number;
  evidence: EvidenceItem[];
};

type EvidenceRow = { opportunity: Opportunity; evidence: IdentityEvidence };
type EvidenceFilter = "all" | "duplicates" | "single";
type Props = { apiBase: string };

const PAGE_SIZE = 25;

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function IdentityEvidenceDashboard({ apiBase }: Props) {
  const [rows, setRows] = useState<EvidenceRow[]>([]);
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selectedPostingId, setSelectedPostingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      const opportunitiesResponse = await fetch(`${apiBase}/api/opportunities`);
      if (!opportunitiesResponse.ok) throw new Error("Unable to load identity evidence.");
      const opportunities = (await opportunitiesResponse.json()) as Opportunity[];
      const loaded = await Promise.all(opportunities.map(async (opportunity) => {
        const response = await fetch(
          `${apiBase}/api/opportunities/${opportunity.posting_id}/identity-evidence`,
        );
        if (!response.ok) throw new Error(`Unable to load identity evidence for ${opportunity.title}.`);
        return { opportunity, evidence: (await response.json()) as IdentityEvidence };
      }));
      if (!cancelled) setRows(loaded);
    }

    load()
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Identity evidence failed.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const counts = useMemo(() => ({
    all: rows.length,
    duplicates: rows.filter(({ evidence }) => evidence.duplicate_evidence_count > 0).length,
    single: rows.filter(({ evidence }) => evidence.duplicate_evidence_count === 0).length,
  }), [rows]);

  const visibleRows = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return rows.filter(({ opportunity, evidence }) => {
      if (filter === "duplicates" && evidence.duplicate_evidence_count === 0) return false;
      if (filter === "single" && evidence.duplicate_evidence_count > 0) return false;
      if (!normalizedQuery) return true;
      return [opportunity.title, opportunity.company, opportunity.location, evidence.canonical_url]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery);
    });
  }, [filter, query, rows]);

  const pageCount = Math.max(1, Math.ceil(visibleRows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pagedRows = visibleRows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const selected = rows.find(({ opportunity }) => opportunity.posting_id === selectedPostingId) ?? null;

  return (
    <section className="panel evidence-workspace" aria-labelledby="identity-evidence-heading">
      <div className="section-heading evidence-heading">
        <div>
          <p className="eyebrow">Source integrity</p>
          <h2 id="identity-evidence-heading">Identity evidence</h2>
          <p>Review canonical sources and confirmed duplicates without expanding every opportunity.</p>
        </div>
      </div>

      {loading && <p role="status">Loading identity evidence…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {!loading && !error && (
        <p className="evidence-loaded" role="status">Identity evidence loaded for {rows.length} opportunities.</p>
      )}

      {!loading && !error && (
        <>
          <div className="evidence-metrics" aria-label="Identity evidence summary">
            <div><strong>{counts.all}</strong><span>Opportunities</span></div>
            <div><strong>{counts.duplicates}</strong><span>With duplicates</span></div>
            <div><strong>{counts.single}</strong><span>Single source</span></div>
          </div>

          <div className="evidence-controls">
            <div className="queue-filters" aria-label="Filter identity evidence">
              {(["all", "duplicates", "single"] as EvidenceFilter[]).map((item) => (
                <button
                  type="button"
                  className={filter === item ? "filter-active" : "secondary"}
                  onClick={() => {
                    setFilter(item);
                    setPage(1);
                  }}
                  key={item}
                >
                  {item} ({counts[item]})
                </button>
              ))}
            </div>
            <label className="evidence-search">
              <span>Search evidence</span>
              <input
                type="search"
                value={query}
                placeholder="Role, company, location, or canonical URL"
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPage(1);
                }}
              />
            </label>
          </div>

          <div className="queue-summary">
            <span>
              Showing {pagedRows.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1}
              {"–"}{Math.min(currentPage * PAGE_SIZE, visibleRows.length)} of {visibleRows.length}
            </span>
            <span>Page {currentPage} of {pageCount}</span>
          </div>

          {pagedRows.length === 0 ? (
            <div className="evidence-empty">
              <h3>No evidence matches this view</h3>
              <p>Change the filter or search to review another source record.</p>
            </div>
          ) : (
            <div className="evidence-list">
              {pagedRows.map(({ opportunity, evidence }) => (
                <article className="evidence-row" key={opportunity.posting_id}>
                  <div className="evidence-row-title">
                    <h3>{opportunity.title || "Untitled opportunity"}</h3>
                    <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                  </div>
                  <div className="evidence-counts">
                    <strong>{evidence.evidence_count}</strong>
                    <span>source{evidence.evidence_count === 1 ? "" : "s"}</span>
                  </div>
                  <div className={`evidence-status ${evidence.duplicate_evidence_count ? "evidence-status-duplicate" : ""}`}>
                    <strong>{evidence.duplicate_evidence_count ? `${evidence.duplicate_evidence_count} duplicate${evidence.duplicate_evidence_count === 1 ? "" : "s"}` : "single source"}</strong>
                    <span>{label(evidence.identity_status)}</span>
                  </div>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setSelectedPostingId(opportunity.posting_id)}
                  >
                    Inspect
                  </button>
                </article>
              ))}
            </div>
          )}

          <div className="pagination" aria-label="Evidence pages">
            <button
              type="button"
              className="secondary"
              disabled={currentPage <= 1}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
            >
              Previous
            </button>
            <span>Page {currentPage} of {pageCount}</span>
            <button
              type="button"
              className="secondary"
              disabled={currentPage >= pageCount}
              onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
            >
              Next
            </button>
          </div>
        </>
      )}

      {selected && (
        <div className="evidence-inspector-backdrop" role="presentation" onMouseDown={() => setSelectedPostingId(null)}>
          <aside
            className="evidence-inspector"
            role="dialog"
            aria-modal="true"
            aria-labelledby="evidence-inspector-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="evidence-inspector-header">
              <div>
                <p className="eyebrow">Identity evidence</p>
                <h2 id="evidence-inspector-title">{selected.opportunity.title || "Untitled opportunity"}</h2>
                <p>{[selected.opportunity.company, selected.opportunity.location].filter(Boolean).join(" · ")}</p>
              </div>
              <button type="button" className="secondary" onClick={() => setSelectedPostingId(null)}>Close</button>
            </header>

            <div className="evidence-inspector-summary">
              <div><strong>{selected.evidence.evidence_count}</strong><span>Total sources</span></div>
              <div><strong>{selected.evidence.duplicate_evidence_count}</strong><span>Confirmed duplicates</span></div>
            </div>

            {selected.evidence.canonical_url && (
              <p className="canonical-source">
                <strong>Canonical source</strong>
                <a href={selected.evidence.canonical_url} target="_blank" rel="noreferrer">{selected.evidence.canonical_url}</a>
              </p>
            )}

            <ol className="evidence-source-list">
              {selected.evidence.evidence.map((item) => (
                <li key={item.source_document_id}>
                  <div>
                    <strong>{label(item.identity_status)}</strong>
                    <span>{label(item.match_basis)} · {item.source_type}</span>
                  </div>
                  <time dateTime={item.captured_at}>{new Date(item.captured_at).toLocaleString()}</time>
                  {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Open source evidence</a>}
                </li>
              ))}
            </ol>
          </aside>
        </div>
      )}
    </section>
  );
}
