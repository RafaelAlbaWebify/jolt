import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarketIntelligence } from "./MarketIntelligence";

const EMPTY_SCOPE = {
  total_roles: 0,
  strong_roles: 0,
  viable_roles: 0,
  role_families: [],
  work_modes: [],
  seniority: [],
  top_companies: [],
  top_locations: [],
  top_skills: [],
  fit_distribution: [],
  top_gaps: [],
  study_priorities: [],
  salary_mentions: [],
  salary_coverage: 0,
};

const MARKET = {
  total_unique_roles: 1,
  target_role_count: 1,
  outside_target_count: 0,
  target: {
    ...EMPTY_SCOPE,
    total_roles: 1,
    top_skills: [{ label: "SQL", count: 1 }],
    study_priorities: [{ label: "API troubleshooting", count: 1 }],
  },
  all: { ...EMPTY_SCOPE, total_roles: 1 },
  outside_title_examples: [],
  fit_explanation: "Stable fit explanation.",
};

const LINKEDIN = {
  capture_count: 12,
  recommendation_count: 2,
  open_recommendation_count: 2,
  categories: { profile: 8, activity: 2 },
  recommendation_statuses: { pending: 2 },
  recommendations: [
    {
      id: "rec-1",
      capture_id: null,
      recommendation_type: "profile_update",
      target_area: "headline",
      title: "Clarify headline for support roles",
      rationale: "The headline should mention SQL and Application Support.",
      proposed_action: "Rewrite headline.",
      proposed_text: "",
      priority: "high",
      status: "pending",
      created_at: "2026-07-31T00:00:00Z",
      updated_at: "2026-07-31T00:00:00Z",
    },
  ],
};

function stubMarketFetch(markets: object[] = [MARKET]) {
  let marketIndex = 0;
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/linkedin-command-center")) {
      return Promise.resolve({ ok: true, json: async () => LINKEDIN });
    }
    const payload = markets[Math.min(marketIndex, markets.length - 1)];
    marketIndex += 1;
    return Promise.resolve({ ok: true, json: async () => payload });
  });
}

describe("MarketIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not fetch while hidden and loads market plus LinkedIn signals on activation", async () => {
    const fetchMock = stubMarketFetch();
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(<MarketIntelligence apiBase="http://api" active={false} />);
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<MarketIntelligence apiBase="http://api" active />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
    expect(screen.getByText("LinkedIn positioning vs market")).toBeInTheDocument();
    expect(screen.getByText("Preparation plan: study, practice, publish")).toBeInTheDocument();
    expect(screen.getByText("SQL troubleshooting")).toBeInTheDocument();
  });

  it("shows a stable failure and retries only when requested", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) })
      .mockImplementation((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/linkedin-command-center")) {
          return Promise.resolve({ ok: true, json: async () => LINKEDIN });
        }
        return Promise.resolve({ ok: true, json: async () => MARKET });
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load market insights.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry insights load" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
  });

  it("refreshes explicitly after initial data is loaded", async () => {
    const updated = { ...MARKET, fit_explanation: "Updated fit explanation." };
    const fetchMock = stubMarketFetch([MARKET, updated]);
    vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh insights" }));
    expect(await screen.findByText("Updated fit explanation.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});
