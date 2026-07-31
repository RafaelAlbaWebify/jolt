import { cleanup, render, screen } from "@testing-library/react";
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
  source_progress: [],
  completed_source_count: 2,
  total_source_count: 2,
  current_source_id: "",
  cancel_requested: false,
  progress_updated_at: "2026-07-31T12:01:15.000Z",
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

describe("ProfessionalCaptureRuns", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders the routing summary and source-level routing reasons for capture runs", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/professional-intelligence/capture-runs")) {
        return Promise.resolve(new Response(JSON.stringify([CAPTURE_RUN]), { status: 200 }));
      }
      if (url.endsWith("/api/professional-intelligence/capture-runs/run-1/routing-summary")) {
        return Promise.resolve(new Response(JSON.stringify(ROUTING_SUMMARY), { status: 200 }));
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

    expect(await screen.findByText("Routing summary / evidence inbox")).toBeInTheDocument();
    expect(screen.getByText(/Review Inbox jobs/)).toBeInTheDocument();
    expect(screen.getByText(/LinkedIn presence/)).toBeInTheDocument();
    expect(screen.getByText(/Market signals/)).toBeInTheDocument();
    expect(screen.getByText(/Needs review/)).toBeInTheDocument();
    expect(screen.getByText(/Rejected\/noise/)).toBeInTheDocument();

    expect(screen.getByText(/Main profile/)).toBeInTheDocument();
    expect(screen.getByText(/Profile and activity evidence is routed to LinkedIn positioning review/)).toBeInTheDocument();
    expect(screen.getByText(/Jobs based on preferences/)).toBeInTheDocument();
    expect(screen.getByText(/Career\/job-search evidence must become verified job items/)).toBeInTheDocument();
    expect(screen.getByText(/job opportunity → Review Inbox/)).toBeInTheDocument();
    expect(screen.getByText(/linkedin presence → LinkedIn Command Center/)).toBeInTheDocument();
  });
});
