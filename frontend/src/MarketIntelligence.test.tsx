import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarketIntelligence } from "./MarketIntelligence";

const DATA = {
  authority: "chatgpt",
  context_version: "global-context-test",
  market_summary: {
    executive_summary: "Application support and modern workplace roles remain strong targets.",
    high_confidence_signals: ["SQL and API troubleshooting recur", "M365 and identity remain common"],
    decision_counts: { reject: 98, strong_pursue: 1, pursue: 2, conditional: 1 },
  },
  skills_gap_summary: { highest_leverage: ["API troubleshooting", "SQL/log analysis"] },
  capture_strategy: { rule: "Resolve remote eligibility from vacancy body evidence" },
  application_strategy: { priority: "Verify eligibility before applying" },
  profile_strategy: { positioning: "IT Operations / Application Support" },
  evidence_provenance: {
    observation_count: 120,
    canonical_role_count: 90,
    duplicate_observation_count: 30,
    capture_run_count: 3,
    oldest_evidence_at: "2026-08-01T10:00:00+00:00",
    newest_evidence_at: "2026-09-01T17:00:00+00:00",
    latest_capture_at: "2026-09-01T17:00:00+00:00",
  },
  freshness: {
    status: "current",
    ai_updated_at: "2026-09-01T18:00:00+00:00",
    latest_capture_at: "2026-09-01T17:00:00+00:00",
    needs_analysis: false,
    reason: "Stored ChatGPT market intelligence covers the latest retained capture evidence.",
  },
  latest_feedback: [],
  recommendations: [{
    feedback_type: "recommendation",
    entity_type: "market",
    entity_id: "api-practice",
    payload: {
      title: "Strengthen API troubleshooting evidence",
      rationale: "Repeated demand across support roles.",
      proposed_action: "Build one REST troubleshooting portfolio exercise.",
    },
    confidence: 92,
    evidence_refs: ["posting:1"],
  }],
};

const APPLICATIONS = [
  { application_id: "app-1", application_status: "applied", outcome_type: null },
  { application_id: "app-2", application_status: "technical_interview", outcome_type: null },
];

function mockApi(market = DATA, applications = APPLICATIONS) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/api/ai-market/view")) {
      return new Response(JSON.stringify(market), { status: 200 });
    }
    if (url.includes("/api/application-index")) {
      return new Response(JSON.stringify(applications), { status: 200 });
    }
    return new Response("Not found", { status: 404 });
  });
}

describe("MarketIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders action-oriented market intelligence with real pipeline metrics", async () => {
    mockApi();
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("heading", { name: "Market Insights" })).toBeInTheDocument();
    expect(screen.getByText("What the market is telling you")).toBeInTheDocument();
    expect(screen.getByText("What to do next")).toBeInTheDocument();
    expect(screen.getByText("Application support and modern workplace roles remain strong targets.")).toBeInTheDocument();
    expect(screen.getByText("Strengthen API troubleshooting evidence")).toBeInTheDocument();

    expect(screen.getByText("Jobs analyzed")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("Good matches")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Applications")).toBeInTheDocument();
    expect(screen.getByText("Interviewing")).toBeInTheDocument();
  });

  it("switches between skills, search, application, and evidence views", async () => {
    mockApi();
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByRole("heading", { name: "Market Insights" });

    expect(screen.getByText("Skills & demand signals")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Search performance" }));
    expect(screen.getByText("Search strategy")).toBeInTheDocument();
    expect(screen.getByText("Search evidence")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Application performance" }));
    expect(screen.getByText("Application strategy")).toBeInTheDocument();
    expect(screen.getByText("Current pipeline")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));
    expect(screen.getByText("Evidence & provenance")).toBeInTheDocument();
    expect(screen.getByText("90")).toBeInTheDocument();
  });

  it("loads authoritative market intelligence plus the read-only application index", async () => {
    const fetchMock = mockApi();
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByRole("heading", { name: "Market Insights" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/ai-market/view",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/application-index",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/market-intelligence?"))).toBe(false);
  });

  it("shows stale-analysis guidance when new evidence arrives", async () => {
    const stale = {
      ...DATA,
      freshness: {
        status: "stale",
        ai_updated_at: "2026-09-01T16:00:00+00:00",
        latest_capture_at: "2026-09-02T09:00:00+00:00",
        needs_analysis: true,
        reason: "New captured market evidence is newer than the latest ChatGPT analysis.",
      },
    };
    mockApi(stale);
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByText("Market analysis needs an update")).toBeInTheDocument();
    expect(screen.getByText(/Update the analysis from Settings & Data/i)).toBeInTheDocument();
  });

  it("refreshes both persisted views without recomputing local intelligence", async () => {
    const fetchMock = mockApi();
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByRole("heading", { name: "Market Insights" });

    fireEvent.click(screen.getByRole("button", { name: "Refresh view" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  });

  it("falls back safely when decision counts or application metrics are unavailable", async () => {
    mockApi({
      ...DATA,
      market_summary: {
        executive_summary: "Support demand remains stable.",
      },
    }, []);

    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByText("Good matches")).toBeInTheDocument();
    expect(screen.getByText("Awaiting decision counts")).toBeInTheDocument();
    expect(screen.getByText("Support demand remains stable.")).toBeInTheDocument();
  });
});
