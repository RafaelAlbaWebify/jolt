import { useState } from "react";

type Signal = {
  value: string;
  source_id: string;
  supporting_snippet: string;
  confidence: string;
  extraction_method: string;
};

type Extraction = {
  capture_run_id: string;
  extraction_method: string;
  integrity_verified: boolean;
  role_signals: Signal[];
  location_signals: Signal[];
  skills: Signal[];
  certifications: Signal[];
  employers: Signal[];
  job_interest_keywords: Signal[];
};

type Props = {
  apiBase: string;
  runId: string;
};

const sections: Array<[keyof Extraction, string]> = [
  ["role_signals", "Role signals"],
  ["location_signals", "Location signals"],
  ["skills", "Skills"],
  ["certifications", "Certifications and training"],
  ["employers", "Employer signals"],
  ["job_interest_keywords", "Job-interest keywords"],
];

export function ProfessionalStructuredExtraction({ apiBase, runId }: Props) {
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadExtraction() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/professional-intelligence/capture-runs/${runId}/structured-extraction`,
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "Structured extraction could not be built.");
      }
      setExtraction((await response.json()) as Extraction);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Structured extraction failed.");
    } finally {
      setLoading(false);
    }
  }

  if (!extraction) {
    return (
      <div className="professional-extraction-launch">
        <button type="button" disabled={loading} onClick={() => void loadExtraction()}>
          {loading ? "Extracting explicit signals…" : "Build structured extraction"}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    );
  }

  return (
    <section className="professional-structured-extraction" aria-label={`Structured extraction for ${runId}`}>
      <div>
        <strong>Integrity-verified deterministic extraction</strong>
        <span>{extraction.extraction_method.replaceAll("_", " ")}</span>
      </div>
      <div className="professional-extraction-sections">
        {sections.map(([key, title]) => {
          const signals = extraction[key] as Signal[];
          return (
            <section key={String(key)}>
              <h4>{title}</h4>
              {signals.length === 0 ? <p>No explicit matches.</p> : (
                <ul>
                  {signals.map((signal) => (
                    <li key={`${signal.source_id}-${signal.value}`}>
                      <strong>{signal.value}</strong>
                      <span>{signal.source_id} · {signal.confidence.replaceAll("_", " ")}</span>
                      <blockquote>{signal.supporting_snippet}</blockquote>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}
