import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OpportunityApplicationHandoff } from "./OpportunityApplicationHandoff";

describe("OpportunityApplicationHandoff", () => {
  it("directs active application management to Applications without lifecycle controls", () => {
    render(<OpportunityApplicationHandoff applicationId="application-1" applicationStatus="technical_interview" outcomeType={null} reviewDecision="pursue" />);

    expect(screen.getByRole("heading", { name: "Manage this process in Applications" })).toBeInTheDocument();
    expect(screen.getByText(/Current recorded state: technical interview/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Stage")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save stage" })).not.toBeInTheDocument();
  });
});
