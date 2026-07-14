import { useEffect, useState } from "react";

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

type Props = { apiBase: string };

export function IdentityEvidenceDashboard({ apiBase }: Props) {
  const [rows, setRows] = useState<Array<{ opportunity: Opportunity; evidence: IdentityEvidence }>>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
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
      setRows(loaded);
    }
    load().catch((caught) => setError(caught instanceof Error ? caught.message : "Identity evidence failed."));
  }, [apiBase]);

  return (
    <section className="panel shell" aria-labelledby="identity-evidence-heading">
      <h2 id="identity-evidence-heading">Duplicate and source identity evidence</h2>
      <p>JOLT keeps every captured source document while using one canonical opportunity record. No records are merged or deleted here.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {rows.length === 0 && !error ? <p>No opportunity identity evidence is available.</p> : (
        <div className="queue opportunity-grid">
          {rows.map(({ opportunity, evidence }) => (
            <article className="opportunity-card" key={opportunity.posting_id}>
              <div className="opportunity-main">
                <h3>{opportunity.title || "Untitled opportunity"}</h3>
                <p>{[opportunity.company, opportunity.location].filter(Boolean).join(" · ")}</p>
                <p>
                  {evidence.evidence_count} source document{evidence.evidence_count === 1 ? "" : "s"}
                  {" · "}{evidence.duplicate_evidence_count} confirmed duplicate{evidence.duplicate_evidence_count === 1 ? "" : "s"}
                </p>
                <details>
                  <summary>Inspect identity evidence</summary>
                  <ul>
                    {evidence.evidence.map((item) => (
                      <li key={item.source_document_id}>
                        <strong>{item.identity_status.replaceAll("_", " ")}</strong>
                        {" · "}{item.match_basis.replaceAll("_", " ")}
                        {" · "}{item.source_type}
                        {item.source_url && (
                          <> · <a href={item.source_url} target="_blank" rel="noreferrer">Open source evidence</a></>
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
              </div>
              <div className="queue-status">
                <strong>{evidence.duplicate_evidence_count ? "duplicate evidence" : "single source"}</strong>
                <span>identity resolution</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
