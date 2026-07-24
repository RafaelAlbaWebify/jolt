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
  authorized_at: null,
  authorization_expires_at: null,
  user_present_confirmed: false,
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

  it("records, explicitly authorizes, and cancels without execution", async () => {
    const authorized = {
      ...plannedRun,
      status: "authorized",
      authorized_at: "2026-07-24T18:01:00Z",
      authorization_expires_at: "2026-07-24T18:16:00Z",
      user_present_confirmed: true,
    };
    const cancelled = {
      ...authorized,
      status: "cancelled",
      completed_at: "2026-07-24T18:02:00Z",
      stop_reason: "cancelled_by_user",
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (!init?.method) return new Response(JSON.stringify([]), { status: 200 });
      if (url.endsWith("/capture-runs")) {
        return new Response(JSON.stringify(plannedRun), { status: 200 });
      }
      if (url.endsWith("/run-1/authorize")) {
        expect(JSON.parse(String(init.body))).toEqual({
          confirmation_phrase: "I UNDERSTAND THIS WILL OPEN LINKEDIN",
          user_present: true,
        });
        return new Response(JSON.stringify(authorized), { status: 200 });
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
    fireEvent.click(screen.getByRole("button", { name: "Authorize supervised run" }));
    fireEvent.change(screen.getByLabelText("Authorization phrase for run-1"), {
      target: { value: "I UNDERSTAND THIS WILL OPEN LINKEDIN" },
    });
    fireEvent.click(screen.getByLabelText("User present for run-1"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm authorization" }));

    expect(await screen.findByText("authorized")).toBeInTheDocument();
    expect(screen.getByText(/Authorization expires:/)).toBeInTheDocument();
    expect(screen.getByText(/Browser execution and evidence writing remain unavailable/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel preview" }));

    expect(await screen.findByText("cancelled")).toBeInTheDocument();
    expect(screen.getByText("cancelled by user")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  });
});
