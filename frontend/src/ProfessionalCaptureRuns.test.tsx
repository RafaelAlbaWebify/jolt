import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalCaptureRuns } from "./ProfessionalCaptureRuns";

vi.mock("./ProfessionalEvidenceReview", () => ({
  ProfessionalEvidenceReview: () => <section>Evidence review placeholder</section>,
}));

const CAPTURE_OPTIONS = {
  max_sources: 3,
  max_scroll_batches: 2,
  max_items_per_source: 25,
  timeout_seconds: 30,
  stop_on_failure: true,
};

const CAPTURE_RUN = {
  id: "run-1",
  mode: "supervised_read_only",
  status: "completed",
  planned_sources: [
    {
      source_id: "linkedin-profile",
      label: "Main profile",
      category: "profile",
      url: "https://www.linkedin.com/in/example/",
      initial_scope: true,
      enabled: true,
      capture_mode: "supervised_read_only",
    },
    {
      source_id: "linkedin-jobs-preferences",
      label: "Jobs based on preferences",
      category: "career",
      url: "https://www.linkedin.com/jobs/search-results/",
      initial_scope: true,
      enabled: true,
      capture_mode: "supervised_read_only",
    },
  ],
  safety_constraints: [],
  capture_options: CAPTURE_OPTIONS,
  requested_at: "2026-07-31T12:00:00.000Z",
  authorized_at: "2026-07-31T12:00:10.000Z",
  authorization_expires_at: "2026-07-31T12:15:10.000Z",
  user_present_confirmed: true,
  started_at: "2026-07-31T12:00:15.000Z",
  completed_at: "2026-07-31T12:01:15.000Z",
  stop_reason: "submitted_batch_completed",
  artifact_count: 4,
  source_progress: [
    {
      source_id: "linkedin-profile",
      status: "completed",
      started_at: "2026-07-31T12:00:15.000Z",
      completed_at: "2026-07-31T12:00:30.000Z",
      completeness_status: "complete",
      detail: "Source capture finished with complete completeness.",
    },
    {
      source_id: "linkedin-jobs-preferences",
      status: "completed",
      started_at: "2026-07-31T12:00:30.000Z",
      completed_at: "2026-07-31T12:01:15.000Z",
      completeness_status: "complete",
      detail: "Source capture finished with complete completeness.",
    },
  ],
  completed_source_count: 2,
  total_source_count: 2,
  current_source_id: "",
  cancel_requested: false,
  progress_updated_at: "2026-07-31T12:01:15.000Z",
};

const PROFILE_ONLY_RUN = {
  ...CAPTURE_RUN,
  id: "run-profile-only",
  planned_sources: [CAPTURE_RUN.planned_sources[0]],
  source_progress: [CAPTURE_RUN.source_progress[0]],
  completed_source_count: 1,
  total_source_count: 1,
};

const ROUTING_SUMMARY = {
  capture_run_id: "run-1",
  run_status: "completed",
  artifact_count: 4,
  total_sources: 2,
  completed_sources: 2,
  counts: {
    job_opportunities: 1,
    linkedin_presence: 1,
    market_signals: 0,
    unclassified_evidence: 0,
    rejected_noise: 0,
  },
  decisions: [
    {
      source_id: "linkedin-profile",
      label: "Main profile",
      source_category: "profile",
      target_bucket: "linkedin_presence",
      target_workspace: "LinkedIn Command Center",
      routing_status: "routed",
      reason: "Profile and activity evidence is routed to LinkedIn positioning review.",
    },
    {
      source_id: "linkedin-jobs-preferences",
      label: "Jobs based on preferences",
      source_category: "career",
      target_bucket: "job_opportunity",
      target_workspace: "Review Inbox",
      routing_status: "needs_canonical_ingestion",
      reason: "Career/job-search evidence must become verified job items before it can create Review Inbox postings.",
    },
  ],
  explanation: "This summary shows where captured evidence is allowed to route through JOLT.",
};

const PROFILE_ONLY_ROUTING_SUMMARY = {
  ...ROUTING_SUMMARY,
  capture_run_id: "run-profile-only",
  total_sources: 1,
  completed_sources: 1,
  counts: {
    job_opportunities: 0,
    linkedin_presence: 1,
    market_signals: 0,
    unclassified_evidence: 0,
    rejected_noise: 0,
  },
  decisions: [ROUTING_SUMMARY.decisions[0]],
};

const IMPORT_RESULT = {
  capture_run_id: "run-1",
  imported_count: 1,
  skipped_count: 0,
  candidates: [
    {
      title: "Application Support Engineer",
      company: "Acme SaaS Operations",
      location: "Remote Spain",
      posting_id: "posting-1",
      identity_status: "new",
      recommendation: "pursue",
      ranking_score: 87,
    },
  ],
  warnings: [],
};

const LOGIN_REQUIRED_RUN = {
  ...CAPTURE_RUN,
  id: "run-login",
  status: "failed",
  completed_at: "2026-07-31T12:01:15.000Z",
  stop_reason: "linkedin_login_required",
  artifact_count: 1,
  source_progress: [
    {
      source_id: "linkedin-jobs-preferences",
      status: "failed",
      started_at: "2026-07-31T12:00:15.000Z",
      completed_at: "2026-07-31T12:01:15.000Z",
      completeness_status: "failed",
      detail: "LinkedIn login is required.",
    },
  ],
  completed_source_count: 0,
  total_source_count: 2,
  cancel_requested: true,
};

const LOGIN_REQUIRED_ROUTING_SUMMARY = {
  ...ROUTING_SUMMARY,
  capture_run_id: "run-login",
  run_status: "failed",
  artifact_count: 1,
  completed_sources: 0,
};

describe("ProfessionalCaptureRuns", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders selected sources, routing summary, and imports opportunity candidates to Review Inbox", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/professional-intelligence/capture-runs") && !init?.method) {
        return Promise.resolve(new Response(JSON.stringify([CAPTURE_RUN]), { status: 200 }));
      }
      if (url.endsWith("/api/professional-intelligence/capture-runs/run-1/routing-summary")) {
        return Promise.resolve(new Response(JSON.stringify(ROUTING_SUMMARY), { status: 200 }));
      }
      if (
        url.endsWith("/api/professional-intelligence/capture-runs/run-1/opportunity-candidates/import")
        && init?.method === "POST"
      ) {
        return Promise.resolve(new Response(JSON.stringify(IMPORT_RESULT), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active={true}
        planRefreshKey={1}
        captureOptions={CAPTURE_OPTIONS}
      />,
    );

    const selectedSourcesHeading = await screen.findByText("Selected capture sources");
    const selectedSources = selectedSourcesHeading.closest("details");
    expect(selectedSources).not.toBeNull();
    expect(within(selectedSources as HTMLElement).getByText(/Jobs based on preferences/)).toBeInTheDocument();
    expect(within(selectedSources as HTMLElement).getByText(/can feed Review Inbox after import/)).toBeInTheDocument();

    const summaryHeading = await screen.findByText("Routing summary / evidence inbox");
    expect(summaryHeading).toBeInTheDocument();
    const routingSummary = summaryHeading.closest("details");
    expect(routingSummary).not.toBeNull();
    const routing = within(routingSummary as HTMLElement);

    expect(routing.getByText(/Review Inbox jobs/)).toBeInTheDocument();
    expect(routing.getByText(/LinkedIn presence/)).toBeInTheDocument();
    expect(routing.getByText(/Market signals/)).toBeInTheDocument();
    expect(routing.getByText(/Needs review/)).toBeInTheDocument();
    expect(routing.getByText(/Rejected\/noise/)).toBeInTheDocument();

    expect(routing.getByText(/Main profile/)).toBeInTheDocument();
    expect(routing.getByText(/Profile and activity evidence is routed to LinkedIn positioning review/)).toBeInTheDocument();
    expect(routing.getByText(/Jobs based on preferences/)).toBeInTheDocument();
    expect(routing.getByText(/Career\/job-search evidence must become verified job items/)).toBeInTheDocument();
    expect(routing.getByText(/job opportunity → Review Inbox/)).toBeInTheDocument();
    expect(routing.getByText(/linkedin presence → LinkedIn Command Center/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Import opportunity candidates to Review Inbox" }));

    expect(await screen.findByText("1 opportunity candidates imported to Review Inbox.")).toBeInTheDocument();
    expect(screen.getByText(/Open Review Inbox and refresh the list/)).toBeInTheDocument();
    expect(screen.getByText(/Application Support Engineer/)).toBeInTheDocument();
    expect(screen.getByText(/Acme SaaS Operations/)).toBeInTheDocument();
  });

  it("does not offer opportunity import for profile-only captures", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/professional-intelligence/capture-runs")) {
        return Promise.resolve(new Response(JSON.stringify([PROFILE_ONLY_RUN]), { status: 200 }));
      }
      if (url.endsWith("/api/professional-intelligence/capture-runs/run-profile-only/routing-summary")) {
        return Promise.resolve(new Response(JSON.stringify(PROFILE_ONLY_ROUTING_SUMMARY), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active={true}
        planRefreshKey={1}
        captureOptions={CAPTURE_OPTIONS}
      />,
    );

    expect(await screen.findByText(/This run has no career\/job source/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import opportunity candidates to Review Inbox" })).not.toBeInTheDocument();
  });

  it("lets the user start the same capture run again after LinkedIn login is required", async () => {
    const authorizedRun = {
      ...LOGIN_REQUIRED_RUN,
      status: "authorized",
      stop_reason: "",
      cancel_requested: false,
      completed_at: null,
    };
    const queuedRun = {
      ...authorizedRun,
      status: "running",
      stop_reason: "capture_queued",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/professional-intelligence/capture-runs") && !init?.method) {
        return Promise.resolve(new Response(JSON.stringify([LOGIN_REQUIRED_RUN]), { status: 200 }));
      }
      if (url.endsWith("/api/professional-intelligence/capture-runs/run-login/routing-summary")) {
        return Promise.resolve(new Response(JSON.stringify(LOGIN_REQUIRED_ROUTING_SUMMARY), { status: 200 }));
      }
      if (url.endsWith("/api/professional-intelligence/capture-runs/run-login/authorize") && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify(authorizedRun), { status: 200 }));
      }
      if (url.endsWith("/api/professional-intelligence/capture-runs/run-login/start") && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify(queuedRun), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ProfessionalCaptureRuns
        apiBase="http://127.0.0.1:8000"
        active={true}
        planRefreshKey={1}
        captureOptions={CAPTURE_OPTIONS}
      />,
    );

    expect(await screen.findByText(/LinkedIn asked for login or checkpoint/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start capture again" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/professional-intelligence/capture-runs/run-login/authorize",
        expect.objectContaining({ method: "POST" }),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/professional-intelligence/capture-runs/run-login/start",
        { method: "POST" },
      );
    });
  });
});
