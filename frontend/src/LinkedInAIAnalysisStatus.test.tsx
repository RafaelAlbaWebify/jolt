import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkedInAIAnalysisStatus } from "./LinkedInAIAnalysisStatus";

function statusResponse(state: "no_evidence" | "not_analyzed" | "stale" | "current") {
  return new Response(
    JSON.stringify({
      overall_status: state === "current" ? "current" : "update_available",
      last_intelligence_update_at: "2026-09-04T09:05:00Z",
      context_updated_at: "2026-09-04T09:00:00Z",
      current_sections: state === "current" ? 1 : 0,
      attention_sections: state === "current" ? 0 : 1,
      sections: {
        linkedin_profile: {
          state,
          evidence_at: "2026-09-04T08:30:00Z",
          analyzed_at: state === "current" ? "2026-09-04T09:00:00Z" : "2026-09-03T17:00:00Z",
          reason: state === "current"
            ? "LinkedIn analysis covers the latest profile evidence."
            : "LinkedIn evidence is newer than the latest profile analysis.",
          operator_relevant: true,
        },
      },
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("LinkedInAIAnalysisStatus", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("uses backend AI status for stale LinkedIn analysis", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(statusResponse("stale"));

    render(<LinkedInAIAnalysisStatus apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByText("Update available")).toBeInTheDocument();
    expect(
      screen.getByText(/LinkedIn evidence is newer than the latest profile analysis/i),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/ai-status");
  });

  it("shows current status from the same backend authority", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(statusResponse("current"));

    render(<LinkedInAIAnalysisStatus apiBase="http://127.0.0.1:8000" active />);

    await waitFor(() => expect(screen.getByText("Up to date")).toBeInTheDocument());
    expect(
      screen.getByText(/LinkedIn analysis covers the latest profile evidence/i),
    ).toBeInTheDocument();
  });
});
