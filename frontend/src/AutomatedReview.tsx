export type AutomatedReviewEvidence = {
  proposed_decision: string;
  fit_summary: string;
  strengths: string[];
  gaps: string[];
  blockers: string[];
  uncertainties: string[];
  dimensions: Record<string, number>;
};

const DECISION_LABELS: Record<string, string> = {
  strong_pursue: "High priority",
  pursue: "Good match",
  conditional: "Check requirements",
  reject: "Not a match",
};

function readableLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/w/g, (character) => character.toUpperCase());
}

function EvidenceGroup({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="review-evidence-group">
      <strong>{title}</strong>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>
  );
}

export function AutomatedReview({ review }: { review: AutomatedReviewEvidence }) {
  return (
    <section className="automated-review" aria-label="Job match review">
      <div className="automated-review-heading">
        <div>
          <span className="review-label">Suggested decision</span>
          <strong>{DECISION_LABELS[review.proposed_decision] ?? readableLabel(review.proposed_decision)}</strong>
        </div>
        <span>Your decision is final</span>
      </div>
      <p>{review.fit_summary}</p>
      <div className="dimension-grid">
        {Object.entries(review.dimensions).map(([name, score]) => (
          <div key={name}>
            <span>{readableLabel(name)}</span>
            <strong>{score}</strong>
          </div>
        ))}
      </div>
      <div className="review-evidence-grid">
        <EvidenceGroup title="Supported strengths" items={review.strengths} />
        <EvidenceGroup title="Gaps" items={review.gaps} />
        <EvidenceGroup title="Requirements not met" items={review.blockers} />
        <EvidenceGroup title="Needs confirmation" items={review.uncertainties} />
      </div>
    </section>
  );
}
