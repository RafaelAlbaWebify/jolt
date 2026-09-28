import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AutomatedReview } from "./AutomatedReview";

describe("AutomatedReview", () => {
  it("shows human-readable decision and dimension labels", () => {
    render(
      <AutomatedReview
        review={{
          proposed_decision: "strong_pursue",
          fit_summary: "Strong support alignment.",
          strengths: ["Windows support"],
          gaps: [],
          blockers: [],
          uncertainties: [],
          dimensions: { technical_fit: 91 },
        }}
      />,
    );

    expect(screen.getByText("High priority")).toBeInTheDocument();
    expect(screen.getByText("Technical Fit")).toBeInTheDocument();
    expect(screen.getByText("Your decision is final")).toBeInTheDocument();
    expect(screen.queryByText("strong_pursue")).not.toBeInTheDocument();
  });
});
