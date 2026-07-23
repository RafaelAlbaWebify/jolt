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
        <p className="eyebrow">Application handoff</p>
        <h3 id="opportunity-application-handoff-heading">Manage this process in Applications</h3>
        <p>
          {applicationId
            ? `Current recorded state: ${label(state)}. Stage changes, outcomes, and timeline history belong in the Applications workspace.`
            : reviewDecision === "pursue"
              ? "This role is ready in the Preparing lane. Create and manage the application record from Applications."
              : "Choose Pursue to place this role in the Applications preparation lane."}
        </p>
      </div>
      <span className="opportunity-application-status">{label(state)}</span>
    </section>
  );
}
