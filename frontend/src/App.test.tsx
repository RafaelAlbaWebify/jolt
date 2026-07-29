import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
}

const baseOpportunity = {
  posting_id: "posting-1",
  evaluation_id: "evaluation-1",
  source_url: "https://example.com/job-1",
  title: "Application Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",
  recommendation: "pursue",
  confidence: "high",
  ranking_score: 91,
  review_decision: null,
  application_id: null,
  application_status: null,
  outcome_type: null,
};

const detail = {
  ...baseOpportunity,
  proposed_decision: "pursue",
  fit_summary: "Strong application support fit.",
  strengths: ["SQL troubleshooting"],
  gaps: ["More API examples"],
  blockers: [],
  uncertainties: [],
  dimensions: { application_support: 5 },
  reasons: ["Matches target profile"],
  profile_version_id: "profile:v1",
  engine_version: "rules-v1",
  readiness: {
    report_id: "readiness-1",
    profile_version_id: "profile:v1",
    engine_version: "readiness-rules:v1",
    priority: "high",
    readiness_score: 82,
    evidence_matches: ["SQL troubleshooting"],
    credibility_warnings: [],
    cv_tailoring_points: ["Tailor CV"],
    talking_points: ["Application support incidents"],
    interview_questions: [],
    revision_topics: [],
    checklist: ["Review the source job"],
  },
};

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads a compact index and fetches full detail only when inspected", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/opportunity-index")) return jsonResponse([baseOpportunity]);
      if (url.endsWith("/api/opportunity-detail/posting-1")) return jsonResponse(detail);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByText("Application Support Engineer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    expect(await screen.findByText("Strong application support fit.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("hands pursued opportunities to Applications without creating records in the inspector", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/opportunity-index")) return jsonResponse([baseOpportunity]);
      if (url.endsWith("/api/opportunity-detail/posting-1")) return jsonResponse(detail);
      if (url.endsWith("/api/opportunities/posting-1/reviews") && init?.method === "POST") return jsonResponse({});
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);

    expect(await screen.findByText("Application Support Engineer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    const decision = await screen.findByDisplayValue("Pending review");
    fireEvent.change(decision, { target: { value: "pursue" } });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/opportunities/posting-1/reviews",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByRole("status")).toHaveTextContent("Application Pipeline");
  });

  it("searches and sorts the compact queue without another request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([
      baseOpportunity,
      { ...baseOpportunity, posting_id: "posting-2", title: "Cloud Operations Analyst", company: "Other Co", ranking_score: 70 },
    ]));

    render(<App />);

    expect(await screen.findByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 })[0]).toHaveTextContent("Application Support Engineer");
    fireEvent.change(screen.getByLabelText("Search inbox"), { target: { value: "Example Systems" } });
    expect(screen.getByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Cloud Operations Analyst")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search inbox"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "title_asc" } });
    expect(screen.getAllByRole("heading", { level: 3 })[0]).toHaveTextContent("Application Support Engineer");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("loads capture history only after data tools open", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/opportunity-index")) return jsonResponse([]);
      if (url.endsWith("/api/captures")) return jsonResponse([]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<App />);
    expect(await screen.findByText("No pending review items match this view.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("Data tools: capture batches and exports"));
    await screen.findByText("No active capture batches recorded.");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows the network error without an unhandled rejection", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("offline");
  });
});
