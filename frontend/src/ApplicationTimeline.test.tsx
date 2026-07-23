import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDashboard } from "./ApplicationDashboard";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("Application workspace timeline", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.body.style.overflow = "";
  });

  it("shows immutable application events in newest-first order", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse([{
        posting_id: "posting-1",
        source_url: "https://example.test/job",
        title: "Application Support Engineer",
        company: "Example Systems",
        location: "Remote Spain",
        review_decision: "pursue",
        application_id: "application-1",
        application_status: "submitted",
        outcome_type: null,
      }]);
      if (url.endsWith("/api/applications/application-1")) return jsonResponse({
        application_id: "application-1",
        posting_id: "posting-1",
        status: "submitted",
        application_url: "https://example.test/apply",
        resume_used: "Support_CV.pdf",
        notes: "Prepared locally.",
        outcome_type: null,
        events: [
          { event_id: "event-1", event_type: "application_created", from_status: "", to_status: "preparing", notes: "Prepared locally.", occurred_at: "2026-07-14T10:00:00+00:00" },
          { event_id: "event-2", event_type: "status_changed", from_status: "preparing", to_status: "submitted", notes: "Submitted manually.", occurred_at: "2026-07-14T11:00:00+00:00" },
        ],
      });
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);
    fireEvent.click(await screen.findByRole("button", { name: "Open Application Support Engineer" }));
    fireEvent.click(screen.getByRole("tab", { name: "Timeline" }));

    expect(await screen.findByRole("heading", { name: "Timeline" })).toBeInTheDocument();
    expect(screen.getByText("2 events")).toBeInTheDocument();
    const notes = screen.getAllByText(/Submitted manually|Prepared locally/);
    expect(notes[0]).toHaveTextContent("Submitted manually");
  });
});
