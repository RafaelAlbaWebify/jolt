import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalEvidenceReview } from "./ProfessionalEvidenceReview";

const review = {
  capture_run_id: "run-1",
  run_status: "completed",
  integrity_valid: true,
  review_available: true,
  ready_for_analysis: true,
  sources: [
    {
      source_id: "linkedin-profile",
      completeness_status: "complete",
      artifacts: [
        {
          id: "artifact-text",
          source_id: "linkedin-profile",
          artifact_type: "rendered_text_json",
          relative_path: "professional-intelligence/run-1/linkedin-profile/rendered-text.json",
          completeness_status: "complete",
          retention_days: 30,
          exists: true,
          integrity_valid: true,
          reviewable: true,
          content: { text: "Visible professional evidence" },
        },
        {
          id: "artifact-png",
          source_id: "linkedin-profile",
          artifact_type: "screenshot_png",
          relative_path: "professional-intelligence/run-1/linkedin-profile/page.png",
          completeness_status: "complete",
          retention_days: 30,
          exists: true,
          integrity_valid: true,
          reviewable: false,
          content: null,
        },
      ],
    },
  ],
};

describe("ProfessionalEvidenceReview", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads verified evidence and exposes JSON content without screenshot bytes", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(review), { status: 200 }),
    );

    render(<ProfessionalEvidenceReview apiBase="http://127.0.0.1:8000" runId="run-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Review captured evidence" }));

    expect(await screen.findByText("Integrity verified")).toBeInTheDocument();
    expect(screen.getByText("Ready for analysis")).toBeInTheDocument();
    fireEvent.click(screen.getByText("linkedin-profile · complete · 2 artifacts"));
    expect(screen.getAllByText("Hash verified", { selector: "span" })).toHaveLength(2);
    expect(screen.getByText(/Visible professional evidence/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/capture-runs/run-1/evidence-review",
    );
  });
});
