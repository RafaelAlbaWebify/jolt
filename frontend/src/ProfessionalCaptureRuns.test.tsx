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

  it("starts a guided capture from the overview trigger and deletes the completed batch", async () => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
    const authorized = {
      ...plannedRun,
      status: "authorized",
      authorized_at: "2026-07-24T18:01:00Z",
      authorization_expires_at: "2026-07-24T18:16:00Z",
      user_present_confirmed: true,
    };
    const completed = {
      ...authorized,
      mode: "supervised_read_only",
      status: "completed",
      started_at: "2026-07-24T18:02:00Z",
      completed_at: "2026-07-24T18:03:00Z",
      artifact_count: 32,
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
      if (url.endsWith("/run-1/start")) {
        return new Response(JSON.stringify(completed), { status: 200 });
      }
      if (url.endsWith("/run-1/delete")) {
        expect(JSON.parse(String(init.body))).toEqual({ confirmation_phrase: "DELETE CAPTURE RUN" });
        return new Response(JSON.stringify({ run_id: "run-1" }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const { rerender } = render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
        startRequestKey={0}
      />,
    );

    expect(await screen.findByText(/No capture runs recorded yet/)).toBeInTheDocument();
    rerender(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
        startRequestKey={1}
      />,
    );

    expect(await screen.findByText("planned")).toBeInTheDocument();
    expect(screen.getByLabelText("Authorization phrase for run-1")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Authorization phrase for run-1"), {
      target: { value: "I UNDERSTAND THIS WILL OPEN LINKEDIN" },
    });
    fireEvent.click(screen.getByLabelText("User present for run-1"));
    fireEvent.click(screen.getByRole("button", { name: "Authorize capture" }));

    expect(await screen.findByText("authorized")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start capture now" }));

    expect(await screen.findByText("completed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete this capture batch" }));
    const deleteButton = screen.getByRole("button", { name: "Permanently delete batch" });
    expect(deleteButton).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Deletion phrase for run-1"), {
      target: { value: "DELETE CAPTURE RUN" },
    });
    fireEvent.click(deleteButton);

    await waitFor(() => expect(screen.queryByText("completed")).not.toBeInTheDocument());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
  });
});
