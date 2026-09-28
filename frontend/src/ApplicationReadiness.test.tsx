import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApplicationReadiness } from "./ApplicationReadiness";

describe("ApplicationReadiness", () => {
  it("keeps engine metadata behind technical details", () => {
    render(
      <ApplicationReadiness
        readiness={{
          report_id: "report-1",
          profile_version_id: "profile-v3",
          engine_version: "engine-v7",
          evidence_matches: ["Incident troubleshooting"],
          credibility_warnings: ["Do not overstate cloud depth"],
          cv_tailoring_points: [],
          talking_points: [],
          interview_questions: [],
          revision_topics: [],
          checklist: [],
        }}
      />,
    );

    expect(screen.getByText("Application preparation guidance")).toBeInTheDocument();
    expect(screen.getByText("Evidence to mention")).toBeInTheDocument();
    expect(screen.getByText("Claims to verify")).toBeInTheDocument();
    expect(screen.getByText("Technical details")).toBeInTheDocument();
    expect(screen.getByText(/engine-v7/)).toBeInTheDocument();
  });
});
