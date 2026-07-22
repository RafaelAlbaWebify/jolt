import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  fit_summary: "Strong evidence-based alignment.",
  strengths: ["Application support and SQL troubleshooting."],
  gaps: ["Deep API diagnostics."],
  blockers: [],
  uncertainties: ["Salary is not evidenced."],
  dimensions: { role_alignment: 95, demonstrated_capability: 75 },
  reasons: ["Relevant support signals."],
  profile_version_id: "rafael-job-search:v4",
  engine_version: "profile-rules-v4",
  readiness: {
    report_id: "readiness-1",
    profile_version_id: "rafael-job-search:v4",
    engine_version: "application-readiness-v1",
    priority: "high",
    readiness_score: 91,
    evidence_matches: ["Incident ownership."],
    credibility_warnings: ["Do not overstate API ownership."],
    cv_tailoring_points: ["Position SQL as troubleshooting."],
    talking_points: ["Controlled escalation."],
    interview_questions: ["How would you troubleshoot an API failure?"],
    revision_topics: ["REST diagnostics."],
    checklist: ["Confirm salary and remote eligibility."],
  },
  review_decision: null,
};

const indexOpportunity = {
  posting_id: opportunity.posting_id,
  evaluation_id: opportunity.evaluation_id,
  source_url: opportunity.source_url,
  title: opportunity.title,
  company: opportunity.company,
  location: opportunity.location,
  recommendation: opportunity.recommendation,
  confidence: opportunity.confidence,
  ranking_score: opportunity.ranking_score,
  review_decision: null,
};

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), { status: 200 });
}

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.body.style.overflow = "";
  });

  it("loads a compact index and fetches full detail only when inspected", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/opportunity-index")) return jsonResponse([indexOpportunity]);
      if (url.endsWith("/api/opportunity-detail/posting-1")) return jsonResponse(opportunity);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.getByText("Showing 1–1 of 1")).toBeInTheDocument();
    expect(screen.queryByText(opportunity.fit_summary)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const inspectButton = screen.getByRole("button", { name: "Inspect" });
    fireEvent.click(inspectButton);

    expect(await screen.findByRole("dialog", { name: opportunity.title })).toBeInTheDocument();
    expect(await screen.findByText(opportunity.fit_summary)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open source job" })).toHaveAttribute("href", opportunity.source_url);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(inspectButton).toHaveFocus());
  });

  it("searches and sorts the compact queue without another request", async () => {
    const second = { ...indexOpportunity, posting_id: "posting-2", evaluation_id: "evaluation-2", title: "Cloud Operations Analyst", company: "Beta Cloud", ranking_score: 95 };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([indexOpportunity, second]));

    render(<App />);
    expect(await screen.findByText("Cloud Operations Analyst")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 })[0]).toHaveTextContent("Cloud Operations Analyst");

    fireEvent.change(screen.getByLabelText("Search opportunities"), { target: { value: "Example Systems" } });
    expect(screen.getByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Cloud Operations Analyst")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search opportunities"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "title_asc" } });
    expect(screen.getAllByRole("heading", { level: 3 })[0]).toHaveTextContent("Application Support Engineer");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("loads capture history only after operations tools open", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/opportunity-index")) return jsonResponse([]);
      if (url.endsWith("/api/captures")) return jsonResponse([]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);
    expect(await screen.findByText("No opportunities match this view.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("Intake, captures, and exports"));
    await screen.findByText("No capture runs recorded yet.");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows an actionable API error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The JOLT API is not available.");
  });
});
