import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OpportunityApplicationHandoff } from "./OpportunityApplicationHandoff";

describe("OpportunityApplicationHandoff", () => {
  it("directs active application management to Applications without lifecycle controls", () => {
    render(<OpportunityApplicationHandoff applicationId="application-1" applicationStatus="technical_interview" outcomeType={null} reviewDecision="pursue" />);

    expect(screen.getByRole("heading", { name: "Continue in Applications" })).toBeInTheDocument();
    expect(screen.getByText(/Current stage: technical interview/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Stage")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save stage" })).not.toBeInTheDocument();
  });


  it("uses Apply language instead of internal pursue terminology", () => {
    render(
      <OpportunityApplicationHandoff
        applicationId={null}
        applicationStatus={null}
        outcomeType={null}
        reviewDecision={null}
      />,
    );

    expect(screen.getByText(/Choose Apply in Review Inbox/i)).toBeInTheDocument();
    expect(screen.queryByText(/Choose Pursue/i)).not.toBeInTheDocument();
  });

});
