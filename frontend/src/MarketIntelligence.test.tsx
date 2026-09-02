import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarketIntelligence } from "./MarketIntelligence";

const DATA = {
  authority: "chatgpt",
  context_version: "global-context-test",
  market_summary: {
    executive_summary: "Application support and modern workplace roles remain strong targets.",
    high_confidence_signals: ["SQL and API troubleshooting recur", "M365 and identity remain common"],
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

describe("MarketIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders ChatGPT-derived intelligence and deterministic provenance", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("heading", { name: "Market Insights" })).toBeInTheDocument();
    expect(screen.getByText("ChatGPT")).toBeInTheDocument();
    expect(screen.getByText("120 observations · 90 canonical roles · 30 repeated observations · 3 capture runs")).toBeInTheDocument();
    expect(screen.getByText("Application support and modern workplace roles remain strong targets.")).toBeInTheDocument();
    expect(screen.getByText("Strengthen API troubleshooting evidence")).toBeInTheDocument();
    expect(screen.queryByText(/Fit shortfall/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Evidence indicator/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Adaptive market baseline/i)).not.toBeInTheDocument();
  });

  it("loads only the authoritative AI market view endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByRole("heading", { name: "Market summary" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/ai-market/view",
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
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(stale), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("heading", { name: "Market analysis needs refresh" })).toBeInTheDocument();
    expect(screen.getByText(/export a new AI work package from Data tools/i)).toBeInTheDocument();
  });

  it("refreshes the persisted view without recomputing local intelligence", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByRole("heading", { name: "Market summary" });

    fireEvent.click(screen.getByRole("button", { name: "Refresh view" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
