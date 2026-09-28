import type { ApplicationStatus } from "./ApplicationWorkflow";

type Props = {
  applicationId?: string | null;
  applicationStatus?: ApplicationStatus | null;
  outcomeType?: string | null;
  reviewDecision: string | null;
};

function label(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "Not started";
}

export function OpportunityApplicationHandoff({ applicationId, applicationStatus, outcomeType, reviewDecision }: Props) {
  const state = outcomeType ?? applicationStatus;
  return (
    <section className="opportunity-application-handoff" aria-labelledby="opportunity-application-handoff-heading">
      <div>
        <p className="eyebrow">Application status</p>
        <h3 id="opportunity-application-handoff-heading">Continue in Applications</h3>
        <p>
          {applicationId
            ? `Current stage: ${label(state)}. Continue tracking this process in Applications.`
            : reviewDecision === "pursue"
              ? "This job is marked Apply and should already appear in Applications. Refresh Applications if you do not see it."
              : "Choose Apply in Review Inbox to start tracking this job in Applications."}
        </p>
      </div>
      <span className="opportunity-application-status">{label(state)}</span>
    </section>
  );
}
