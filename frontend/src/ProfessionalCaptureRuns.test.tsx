import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalCaptureRuns } from "./ProfessionalCaptureRuns";

const plannedRun = {
  id: "run-1",
  mode: "preview_only",
  status: "planned",
  planned_sources: [],
  safety_constraints: ["no_unattended_capture"],
  requested_at: "2026-07-24T18:00:00Z",
  started_at: null,
  completed_at: null,
  stop_reason: "",
  artifact_count: 0,
};

describe("ProfessionalCaptureRuns", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("records and cancels a preview-only run without execution", async () => {
    const cancelled = {
      ...plannedRun,
      status: "cancelled",
      completed_at: "2026-07-24T18:01:00Z",
      stop_reason: "cancelled_by_user",
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (!init?.method) return new Response(JSON.stringify([]), { status: 200 });
      if (url.endsWith("/capture-runs")) {
        return new Response(JSON.stringify(plannedRun), { status: 200 });
      }
      if (url.endsWith("/run-1/cancel")) {
        return new Response(JSON.stringify(cancelled), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
      />,
    );

    expect(await screen.findByText("No preview runs recorded.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record preview run" }));

    expect(await screen.findByText("planned")).toBeInTheDocument();
    expect(screen.getByText("0 planned sources · 0 artifacts")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel preview" }));

    expect(await screen.findByText("cancelled")).toBeInTheDocument();
    expect(screen.getByText("cancelled by user")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
