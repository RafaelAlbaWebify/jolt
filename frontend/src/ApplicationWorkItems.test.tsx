import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDashboard } from "./ApplicationDashboard";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const opportunity = {
  posting_id: "posting-1",
  source_url: "https://example.test/job/1",
  title: "Application Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",
  review_decision: "pursue",
  application_id: "application-1",
  application_status: "submitted",
  outcome_type: null,
};

const application = {
  application_id: "application-1",
  posting_id: "posting-1",
  status: "submitted",
  application_url: "https://example.test/application/1",
  resume_used: "support-resume.pdf",
  notes: "Submitted externally.",
  outcome_type: null,
  events: [
    {
      event_id: "event-1",
      event_type: "application_created",
      from_status: "",
      to_status: "preparing",
      notes: "Preparation record created.",
      occurred_at: "2026-07-24T08:00:00Z",
    },
  ],
};

describe("Application workspace work items", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.body.style.overflow = "";
  });

  it("loads persisted Tasks, Interviews, and Timeline panels", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse([opportunity]);
      if (url.endsWith("/api/applications/application-1")) return jsonResponse(application);
      if (url.endsWith("/api/applications/application-1/tasks")) return jsonResponse([]);
      if (url.endsWith("/api/applications/application-1/interviews")) return jsonResponse([]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.click(await screen.findByRole("button", { name: "Open Application Support Engineer" }));
    expect(await screen.findByRole("dialog", { name: "Application Support Engineer" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Tasks" }));
    expect(await screen.findByRole("heading", { name: "Tasks" })).toBeInTheDocument();
    expect(screen.getByLabelText("Task title")).toBeInTheDocument();
    expect(screen.getByText("No tasks recorded yet.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Interviews" }));
    expect(await screen.findByRole("heading", { name: "Interviews" })).toBeInTheDocument();
    expect(screen.getByLabelText("Interview type")).toBeInTheDocument();
    expect(screen.getByText("No interviews recorded yet.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Timeline" }));
    expect(await screen.findByRole("heading", { name: "Timeline" })).toBeInTheDocument();
    expect(screen.getByText("application created")).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/tasks",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/interviews",
    );
  });
});
