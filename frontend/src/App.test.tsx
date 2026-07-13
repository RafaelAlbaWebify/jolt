import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const opportunity = {
  posting_id: "posting-1",
  evaluation_id: "evaluation-1",
  source_url: "https://www.linkedin.com/jobs/view/123",
  title: "Application Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",
  recommendation: "pursue",
  proposed_decision: "pursue",
  confidence: "medium",
  ranking_score: 83,
  fit_summary: "Strong evidence-based alignment with Rafael's support and operations profile.",
  strengths: ["Application Support: application support, sql, api."],
  gaps: [],
  blockers: [],
  uncertainties: ["Salary or compensation is not evidenced."],
  dimensions: { role_alignment: 25, application_support: 20, support_ownership: 16 },
  reasons: ["Relevant signal(s): application support, sql, incident."],
  profile_version_id: "rafael-job-search:v2",
  engine_version: "profile-rules-v2",
  readiness: {
    report_id: "readiness-1",
    profile_version_id: "rafael-job-search:v2",
    engine_version: "application-readiness-v1",
    priority: "high",
    readiness_score: 91,
    evidence_matches: ["Production-critical IT support with incident ownership."],
    credibility_warnings: ["Do not claim DBA ownership."],
    cv_tailoring_points: ["Position SQL as a support troubleshooting tool."],
    talking_points: ["Incident ownership and controlled escalation."],
    interview_questions: ["How would you troubleshoot an API integration failure?"],
    revision_topics: ["SQL read-only diagnostics and escalation boundaries."],
    checklist: ["Confirm salary, contract, remote eligibility, shifts, and travel."],
  },
  review_decision: null,
};

const captureSummary = {
  capture_run_id: "capture-1",
  source: "linkedin",
  mode: "fixture",
  status: "completed_with_warnings",
  search_url: "https://www.linkedin.com/jobs/search/",
  warnings: ["1 detail panel failed identity verification."],
  started_at: "2026-07-12T20:00:00Z",
  completed_at: "2026-07-12T20:01:00Z",
  total_items: 2,
  verified_items: 1,
  rejected_items: 1,
};

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), { status: 200 });
}

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("submits a manual opportunity and records a human review", async () => {
    let reviewed = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/captures")) return jsonResponse([]);
      if (url.endsWith("/api/opportunities") && (!init || init.method !== "POST")) {
        return jsonResponse(reviewed ? [{ ...opportunity, review_decision: "pursue" }] : []);
      }
      if (url.endsWith("/api/intake/manual")) {
        return jsonResponse({
          posting_id: "posting-1",
          evaluation_id: "evaluation-1",
          identity_status: "new",
          title: opportunity.title,
          company: opportunity.company,
          location: opportunity.location,
          recommendation: "pursue",
          confidence: "medium",
          ranking_score: 83,
          reasons: ["Relevant signals found."],
        });
      }
      if (url.includes("/reviews")) {
        reviewed = true;
        return jsonResponse({
          review_id: "review-1",
          posting_id: "posting-1",
          evaluation_id: "evaluation-1",
          decision: "pursue",
          evaluation_overridden: false,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    const exportLink = screen.getByRole("link", { name: "Download analysis pack" });
    expect(exportLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/exports/analysis-pack",
    );
    expect(exportLink).toHaveAttribute("download", "JOLT_ANALYSIS_PACK.zip");

    fireEvent.change(screen.getByLabelText("Job text"), {
      target: { value: "Application Support Engineer\nExample Systems\nLocation: Remote Spain" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Evaluate opportunity" }));

    expect(await screen.findByRole("heading", { name: opportunity.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Rule score 83 · medium confidence")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "pursue" }));
    expect(await screen.findByText("pursue", { selector: ".queue-status strong" })).toBeInTheDocument();
  });

  it("shows automated decision evidence, readiness, and source provenance", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/captures")) return jsonResponse([]);
      if (url.endsWith("/api/opportunities")) return jsonResponse([opportunity]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByText("Automated proposed decision")).toBeInTheDocument();
    expect(screen.getByText(opportunity.fit_summary)).toBeInTheDocument();
    expect(screen.getByText(opportunity.strengths[0])).toBeInTheDocument();
    expect(screen.getByText(opportunity.uncertainties[0])).toBeInTheDocument();
    expect(screen.getByText("medium confidence · profile-rules-v2")).toBeInTheDocument();
    expect(screen.getByText("Profile rafael-job-search:v2")).toBeInTheDocument();
    expect(screen.getByText("Application readiness · high priority · 91/100")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Application readiness · high priority · 91/100"));
    expect(screen.getByText(opportunity.readiness.evidence_matches[0])).toBeInTheDocument();
    expect(screen.getByText(opportunity.readiness.credibility_warnings[0])).toBeInTheDocument();
    expect(screen.getByText(opportunity.readiness.interview_questions[0])).toBeInTheDocument();

    expect(screen.getByRole("link", { name: "Open source job" })).toHaveAttribute(
      "href",
      opportunity.source_url,
    );
    expect(screen.getByRole("button", { name: "pending (1)" })).toBeInTheDocument();
  });

  it("loads capture history and exposes rejected evidence", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/opportunities")) return jsonResponse([]);
      if (url.endsWith("/api/captures")) return jsonResponse([captureSummary]);
      if (url.endsWith("/api/captures/capture-1")) {
        return jsonResponse({
          ...captureSummary,
          pages: [{
            page_number: 1,
            visible_job_ids: ["4434979232", "4435000001"],
            next_control_present: true,
            next_control_enabled: true,
          }],
          items: [{
            capture_item_id: "item-1",
            source_job_id: "4435000001",
            source_url: "https://www.linkedin.com/jobs/view/4435000001",
            title: "Production Support Engineer",
            company: "Factory Cloud",
            location: "European Union",
            detail_status: "rejected_unverified",
            verification_reasons: ["Detail panel does not match expected job ID."],
            posting_id: null,
          }],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByText("1 verified · 1 rejected · 2 total")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Inspect capture" }));

    expect(await screen.findByRole("heading", { name: "Production Support Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Detail panel does not match expected job ID.")).toBeInTheDocument();
    expect(screen.getByText("rejected unverified")).toBeInTheDocument();
    expect(screen.getByText("not ingested")).toBeInTheDocument();
  });

  it("shows an actionable API error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The JOLT API is not available.");
  });
});
