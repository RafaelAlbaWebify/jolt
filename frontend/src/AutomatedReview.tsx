export type AutomatedReviewEvidence = {
  proposed_decision: string;
  fit_summary: string;
  strengths: string[];
  gaps: string[];
  blockers: string[];
  uncertainties: string[];
  dimensions: Record<string, number>;
};

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
    <section className="automated-review" aria-label="Automated job review">
      <div className="automated-review-heading">
        <div>
          <span className="review-label">Automated proposed decision</span>
          <strong>{review.proposed_decision.replaceAll("_", " ")}</strong>
        </div>
        <span>Human confirmation required</span>
      </div>
      <p>{review.fit_summary}</p>
      <div className="dimension-grid">
        {Object.entries(review.dimensions).map(([name, score]) => (
          <div key={name}>
            <span>{name.replaceAll("_", " ")}</span>
            <strong>{score}</strong>
          </div>
        ))}
      </div>
      <div className="review-evidence-grid">
        <EvidenceGroup title="Supported strengths" items={review.strengths} />
        <EvidenceGroup title="Gaps" items={review.gaps} />
        <EvidenceGroup title="Verified blockers" items={review.blockers} />
        <EvidenceGroup title="Needs confirmation" items={review.uncertainties} />
      </div>
    </section>
  );
}
