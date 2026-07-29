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

describe("ProfessionalCaptureRuns", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("opens Chromium for manual preparation before current-page capture", async () => {
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

    expect(await screen.findByText("authorized")).toBeInTheDocument();
    expect(screen.getByText(/Chromium is open/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Capture current Chromium page" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/capture-runs/run-1/prepare-browser",
      { method: "POST" },
    );
  });

  it("captures the current prepared Chromium page with a separate button", async () => {
    const queued = {
      ...preparedRun,
      status: "running",
      started_at: "2026-07-24T18:02:00Z",
      stop_reason: "manual_current_page_capture_queued",
      planned_sources: [
        {
          source_id: "linkedin-current-page",
          label: "Prepared LinkedIn job search",
          url: "https://www.linkedin.com/jobs/search/",
          initial_scope: true,
        },
      ],
      total_source_count: 1,
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
      if (!init?.method) return new Response(JSON.stringify([preparedRun]), { status: 200 });
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

    fireEvent.click(await screen.findByRole("button", { name: "Capture current Chromium page" }));

    expect(await screen.findByText("running")).toBeInTheDocument();
    expect(screen.getByText(/manual current page capture queued/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request cancellation" })).toBeInTheDocument();
  });

  it("surfaces running source, cancellation, and failed source details", async () => {
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

    expect(await screen.findByText("running")).toBeInTheDocument();
    expect(screen.getByText(/Progress: 0\/1 sources completed/)).toBeInTheDocument();
    expect(screen.getByText(/Current: Prepared LinkedIn job search/)).toBeInTheDocument();
    expect(screen.getByText(/cancellation requested/)).toBeInTheDocument();
    expect(screen.getByText(/authwall\/sign-in page/)).toBeInTheDocument();
  });
});
