import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDashboard } from "./ApplicationDashboard";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("application card operational signals", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows activity, next due item, document state, and overdue warning", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([{
      posting_id: "posting-1",
      evaluation_id: "evaluation-1",
      source_url: "https://example.test/job",
      title: "Application Support Engineer",
      company: "Example Systems",
      location: "Remote Spain",
      recommendation: "pursue",
      confidence: "high",
      ranking_score: 90,
      review_decision: "pursue",
      application_id: "application-1",
      application_status: "submitted",
      outcome_type: null,
      last_activity_at: "2026-07-24T06:00:00Z",
      next_due_at: "2026-07-23T09:00:00Z",
      next_due_kind: "task",
      document_state: "resume attached",
      overdue: true,
    }]));

    const { container } = render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getByText("Last activity")).toBeInTheDocument();
    expect(screen.getByText("Next task")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("resume attached")).toBeInTheDocument();
    expect(container.querySelector(".application-card-overdue")).not.toBeNull();
  });
});
