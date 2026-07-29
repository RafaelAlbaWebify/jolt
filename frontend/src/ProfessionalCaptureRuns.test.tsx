import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const authorizedRun = {
  ...plannedRun,
  status: "authorized",
  authorized_at: "2026-07-24T18:01:00Z",
  authorization_expires_at: "2026-07-24T18:16:00Z",
  user_present_confirmed: true,
};

const preparedRun = {
  ...authorizedRun,
  mode: "supervised_read_only",
  stop_reason: "manual_browser_ready_prepare_linkedin_then_capture_current_page",
};

const preparedJobRun = {
  ...preparedRun,
  planned_sources: [
    {
      source_id: "linkedin-current-page",
      label: "Prepared LinkedIn job search",
      url: "https://www.linkedin.com/jobs/search/",
      initial_scope: true,
    },
  ],
  total_source_count: 1,
};

describe("ProfessionalCaptureRuns", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("opens Chromium into one above-the-fold current session workflow", async () => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
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
        return new Response(JSON.stringify(authorizedRun), { status: 200 });
      }
      if (url.endsWith("/run-1/prepare-browser")) {
        return new Response(JSON.stringify(preparedRun), { status: 200 });
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

    expect(await screen.findByRole("heading", { name: "Current capture session" })).toBeInTheDocument();
    expect(screen.getByText("Chromium ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Capture prepared page" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Capture prepared page" })).toHaveLength(1);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/capture-runs/run-1/prepare-browser",
      { method: "POST" },
    );
  });

  it("keeps one primary capture button when stale prepared runs exist", async () => {
    const olderPreparedRun = {
      ...preparedJobRun,
      id: "run-older",
      requested_at: "2026-07-24T17:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([preparedJobRun, olderPreparedRun]), { status: 200 }),
    );

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
        captureOptions={captureOptions}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Current capture session" })).toBeInTheDocument();
    const captureButton = screen.getByRole("button", { name: "Capture prepared page" });
    expect(captureButton).toBeEnabled();
    expect(screen.getAllByRole("button", { name: "Capture prepared page" })).toHaveLength(1);
  });

  it("captures the current prepared Chromium page from the top session card", async () => {
    const queued = {
      ...preparedJobRun,
      status: "running",
      started_at: "2026-07-24T18:02:00Z",
      stop_reason: "manual_current_page_capture_queued",
      source_progress: [
        {
          source_id: "linkedin-current-page",
          status: "pending",
          started_at: null,
          completed_at: null,
          completeness_status: "",
          detail: "Waiting to capture the user-prepared Chromium page.",
        },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (!init?.method) return new Response(JSON.stringify([preparedJobRun]), { status: 200 });
      if (url.endsWith("/run-1/capture-current-page")) return new Response(JSON.stringify(queued), { status: 200 });
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
        captureOptions={captureOptions}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Capture prepared page" }));

    expect((await screen.findAllByText("running")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/manual current page capture queued/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Request cancellation" })).toBeInTheDocument();
  });

  it("deletes through a second-confirm modal instead of expanding history rows", async () => {
    const preparedA = { ...preparedJobRun, id: "run-a" };
    const preparedB = { ...preparedJobRun, id: "run-b" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (!init?.method) return new Response(JSON.stringify([preparedA, preparedB]), { status: 200 });
      if (url.endsWith("/run-a/delete")) {
        expect(JSON.parse(String(init.body))).toEqual({ confirmation_phrase: "DELETE CAPTURE RUN" });
        return new Response(JSON.stringify({ run_id: "run-a", deleted_artifact_count: 0, deleted_evidence_directory: false }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active
        planRefreshKey={0}
        captureOptions={captureOptions}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Current capture session" })).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    const row = rows.find((candidate) => within(candidate).queryByText(/run-a/));
    expect(row).toBeDefined();
    fireEvent.click(within(row as HTMLTableRowElement).getByRole("button", { name: "Delete" }));

    expect(screen.getByRole("dialog", { name: "Delete capture run?" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/Deletion phrase/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete this run" }));

    await waitFor(() => expect(screen.queryByText(/run-a/)).not.toBeInTheDocument());
    expect(screen.getByText(/run-b/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/capture-runs/run-a/delete",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("surfaces running source, cancellation, and failed source details in the selected details panel", async () => {
    const runningRun = {
      ...plannedRun,
      id: "run-progress",
      status: "running",
      planned_sources: [
        {
          source_id: "linkedin-current-page",
          label: "Prepared LinkedIn job search",
          url: "https://www.linkedin.com/jobs/search/",
          initial_scope: true,
        },
      ],
      started_at: "2026-07-24T18:02:00Z",
      artifact_count: 1,
      source_progress: [
        {
          source_id: "linkedin-current-page",
          status: "failed",
          started_at: "2026-07-24T18:02:31Z",
          completed_at: null,
          completeness_status: "failed",
          detail: "The prepared LinkedIn browser page is still an authwall/sign-in page.",
        },
      ],
      completed_source_count: 0,
      total_source_count: 1,
      current_source_id: "linkedin-current-page",
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

    expect((await screen.findAllByText("running")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/0\/1 sources completed/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Prepared LinkedIn job search/).length).toBeGreaterThan(0);
    expect(screen.getByText(/authwall\/sign-in page/)).toBeInTheDocument();
  });
});
