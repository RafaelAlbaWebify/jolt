import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalCaptureRuns, type ProfessionalCaptureOptions } from "./ProfessionalCaptureRuns";

const captureOptions: ProfessionalCaptureOptions = {
  max_sources: 2,
  max_scroll_batches: 1,
  max_items_per_source: 10,
  timeout_seconds: 20,
  stop_on_failure: true,
};

const plannedRun = {
  id: "run-1",
  mode: "preview_only",
  status: "planned",
  planned_sources: [],
  safety_constraints: ["no_unattended_capture"],
  capture_options: captureOptions,
  requested_at: "2026-07-24T18:00:00Z",
  authorized_at: null,
  authorization_expires_at: null,
  user_present_confirmed: false,
  started_at: null,
  completed_at: null,
  stop_reason: "",
  artifact_count: 0,
  source_progress: [],
  completed_source_count: 0,
  total_source_count: 0,
  current_source_id: "",
  cancel_requested: false,
  progress_updated_at: null,
};

describe("ProfessionalCaptureRuns", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("starts a bounded capture from one overview click and deletes the batch", async () => {
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
      artifact_count: 8,
      completed_source_count: 2,
      total_source_count: 2,
      source_progress: [
        {
          source_id: "linkedin-profile",
          status: "completed",
          started_at: "2026-07-24T18:02:00Z",
          completed_at: "2026-07-24T18:02:30Z",
          completeness_status: "complete",
          detail: "Captured profile evidence.",
        },
        {
          source_id: "linkedin-posts",
          status: "completed",
          started_at: "2026-07-24T18:02:31Z",
          completed_at: "2026-07-24T18:03:00Z",
          completeness_status: "partial",
          detail: "Captured bounded post evidence.",
        },
      ],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (!init?.method) return new Response(JSON.stringify([]), { status: 200 });
      if (url.endsWith("/capture-runs")) {
        expect(JSON.parse(String(init.body))).toEqual({ options: captureOptions });
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
        captureOptions={captureOptions}
        startRequestKey={0}
      />,
    );

    expect(await screen.findByText(/No captures yet/)).toBeInTheDocument();
    rerender(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
        captureOptions={captureOptions}
        startRequestKey={1}
      />,
    );

    expect(await screen.findByText("completed")).toBeInTheDocument();
    expect(screen.getByText(/Limits: 2 sources/)).toBeInTheDocument();
    expect(screen.getByText(/Progress: 2\/2 sources completed/)).toBeInTheDocument();
    expect(screen.getByText("Source progress and failure details")).toBeInTheDocument();
    expect(screen.getByText(/linkedin-profile/)).toBeInTheDocument();
    expect(screen.getByText(/Captured bounded post evidence/)).toBeInTheDocument();
    expect(screen.queryByText(/Type the exact phrase/)).not.toBeInTheDocument();

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

  it("surfaces running source, cancellation, and failed source details", async () => {
    const runningRun = {
      ...plannedRun,
      id: "run-progress",
      status: "running",
      planned_sources: [
        {
          source_id: "linkedin-profile",
          label: "LinkedIn profile",
          url: "https://www.linkedin.com/in/example/",
          initial_scope: true,
        },
        {
          source_id: "linkedin-posts",
          label: "LinkedIn posts",
          url: "https://www.linkedin.com/in/example/recent-activity/all/",
          initial_scope: true,
        },
      ],
      started_at: "2026-07-24T18:02:00Z",
      artifact_count: 1,
      source_progress: [
        {
          source_id: "linkedin-profile",
          status: "completed",
          started_at: "2026-07-24T18:02:00Z",
          completed_at: "2026-07-24T18:02:30Z",
          completeness_status: "complete",
          detail: "Profile captured successfully.",
        },
        {
          source_id: "linkedin-posts",
          status: "failed",
          started_at: "2026-07-24T18:02:31Z",
          completed_at: null,
          completeness_status: "failed",
          detail: "LinkedIn posts timed out before bounded capture completed.",
        },
      ],
      completed_source_count: 1,
      total_source_count: 2,
      current_source_id: "linkedin-posts",
      cancel_requested: true,
      progress_updated_at: "2026-07-24T18:03:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([runningRun]), { status: 200 }),
    );

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
        captureOptions={captureOptions}
      />,
    );

    expect(await screen.findByText("running")).toBeInTheDocument();
    expect(screen.getByText(/Progress: 1\/2 sources completed/)).toBeInTheDocument();
    expect(screen.getByText(/Current: LinkedIn posts/)).toBeInTheDocument();
    expect(screen.getByText(/cancellation requested/)).toBeInTheDocument();
    expect(screen.getByText(/LinkedIn posts timed out/)).toBeInTheDocument();
  });
});
