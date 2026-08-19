export type ApplicationReadinessData = {
  report_id: string;
  profile_version_id: string;
  engine_version: string;
  evidence_matches: string[];
  credibility_warnings: string[];
  cv_tailoring_points: string[];
  talking_points: string[];
  interview_questions: string[];
  revision_topics: string[];
  checklist: string[];
};

function ReadinessList({ title, items }: { title: string; items?: string[] | null }) {
  const safeItems = items ?? [];
  if (safeItems.length === 0) return null;
  return (
    <div className="readiness-section">
      <h5>{title}</h5>
      <ul>{safeItems.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>
  );
}

export function ApplicationReadiness({ readiness }: { readiness: ApplicationReadinessData }) {
  return (
    <details className="application-readiness">
      <summary>Application evidence preparation</summary>
      <p className="confidence">
        {readiness.engine_version} · profile {readiness.profile_version_id}
      </p>
      <ReadinessList title="Evidence to use" items={readiness.evidence_matches} />
      <ReadinessList title="Credibility warnings" items={readiness.credibility_warnings} />
      <ReadinessList title="CV tailoring points" items={readiness.cv_tailoring_points} />
      <ReadinessList title="Application talking points" items={readiness.talking_points} />
      <ReadinessList title="Likely interview questions" items={readiness.interview_questions} />
      <ReadinessList title="Technical revision topics" items={readiness.revision_topics} />
      <ReadinessList title="Application checklist" items={readiness.checklist} />
    </details>
  );
}
