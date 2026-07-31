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
  target: { ...EMPTY_SCOPE, total_roles: 1, top_skills: [{ label: "SQL", count: 1 }], study_priorities: [{ label: "API troubleshooting", count: 1 }] },
  all: { ...EMPTY_SCOPE, total_roles: 1 },
  outside_title_examples: [],
  fit_explanation: "Stable fit explanation.",
};
const LINKEDIN = { capture_count: 12, recommendation_count: 2, open_recommendation_count: 2, categories: { profile: 8, activity: 2 }, recommendation_statuses: { pending: 2 }, recommendations: [{ id: "rec-1", capture_id: null, recommendation_type: "profile_update", target_area: "headline", title: "Clarify headline for support roles", rationale: "The headline should mention SQL and Application Support.", proposed_action: "Rewrite headline.", proposed_text: "", priority: "high", status: "pending", created_at: "2026-07-31T00:00:00Z", updated_at: "2026-07-31T00:00:00Z" }] };
const PREFERENCES = { target_titles: ["Application Support Engineer"], preferred_work_modes: ["remote", "hybrid"], base_locality: "Vigo, Galicia, Spain", max_hybrid_distance_km: 60, countries: ["Spain"], languages: ["Spanish", "English"], expected_salary_eur_min: 35000, expected_salary_eur_target: 45000, preferred_shifts: ["business_hours"], excluded_shifts: ["night", "rotating"], preferred_workload: "normal", excluded_keywords: ["dispatch"], preferred_keywords: ["sql", "api"], notes: "Remote first." };
const EMPTY_IMPORTS = { import_count: 0, latest_import: null, imports: [] };
const IMPORTED = { import_count: 1, latest_import: { id: "import-1", source: "chatgpt_market_package", summary: "Focus search and preparation.", imported_at: "2026-07-31T00:00:00Z", action_count: 1, actions: [{ action_type: "study", title: "Practice SQL support triage", rationale: "SQL is important.", proposed_action: "Do three scenarios.", priority: "high", status: "pending", source: "chatgpt_market_package" }] }, imports: [] };

function stubMarketFetch(markets: object[] = [MARKET]) {
  let marketIndex = 0;
  let imported = false;
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/api/linkedin-command-center")) return Promise.resolve({ ok: true, json: async () => LINKEDIN });
    if (url.includes("/api/job-search-preferences")) return Promise.resolve({ ok: true, json: async () => PREFERENCES });
    if (url.includes("/api/market-intelligence/preparation-import")) {
      if (init?.method === "POST") { imported = true; return Promise.resolve({ ok: true, json: async () => ({ imported_count: 1, latest_import: IMPORTED.latest_import }) }); }
      return Promise.resolve({ ok: true, json: async () => (imported ? IMPORTED : EMPTY_IMPORTS) });
    }
    const payload = markets[Math.min(marketIndex, markets.length - 1)]; marketIndex += 1;
    return Promise.resolve({ ok: true, json: async () => payload });
  });
}

describe("MarketIntelligence", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("does not fetch while hidden and loads market plus LinkedIn signals and preferences on activation", async () => {
    const fetchMock = stubMarketFetch(); vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(<MarketIntelligence apiBase="http://api" active={false} />);
    expect(fetchMock).not.toHaveBeenCalled();
    rerender(<MarketIntelligence apiBase="http://api" active />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
    expect(screen.getByText("LinkedIn positioning vs market")).toBeInTheDocument();
    expect(screen.getByText("Preparation plan: study, practice, publish")).toBeInTheDocument();
    expect(screen.getByText("SQL troubleshooting")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Export Market + LinkedIn pack" })).toHaveAttribute("href", "http://api/api/market-intelligence/preparation-pack");
  });

  it("shows editable preferences and saves them", async () => {
    const fetchMock = stubMarketFetch(); vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);
    fireEvent.click(await screen.findByRole("button", { name: "Job preferences" }));
    expect(screen.getByText("Editable job search preferences")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Base locality"), { target: { value: "Tui, Galicia, Spain" } });
    fireEvent.click(screen.getByRole("button", { name: "Save job preferences" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("http://api/api/job-search-preferences", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("Job search preferences saved.")).toBeInTheDocument();
  });

  it("imports a market preparation return JSON", async () => {
    const fetchMock = stubMarketFetch(); vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);
    fireEvent.click(await screen.findByRole("button", { name: "Import analysis" }));
    fireEvent.change(screen.getByLabelText("Market preparation JSON fallback"), { target: { value: JSON.stringify({ source: "chatgpt_market_package", preparation_plan: [{ action_type: "study", title: "Practice SQL support triage", rationale: "SQL is important.", proposed_action: "Do three scenarios.", priority: "high" }] }) } });
    fireEvent.click(screen.getByRole("button", { name: "Import pasted JSON" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("http://api/api/market-intelligence/preparation-import", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("1 market preparation actions imported.")).toBeInTheDocument();
    expect(screen.getByText("Latest imported market analysis")).toBeInTheDocument();
    expect(screen.getByText("Practice SQL support triage")).toBeInTheDocument();
  });

  it("shows a stable failure and retries only when requested", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: false, json: async () => ({}) }).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/linkedin-command-center")) return Promise.resolve({ ok: true, json: async () => LINKEDIN });
      if (url.includes("/api/job-search-preferences")) return Promise.resolve({ ok: true, json: async () => PREFERENCES });
      if (url.includes("/api/market-intelligence/preparation-import")) return Promise.resolve({ ok: true, json: async () => EMPTY_IMPORTS });
      return Promise.resolve({ ok: true, json: async () => MARKET });
    });
    vi.stubGlobal("fetch", fetchMock); render(<MarketIntelligence apiBase="http://api" active />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load market insights.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Load insights" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
  });

  it("refreshes explicitly after initial data is loaded", async () => {
    const updated = { ...MARKET, fit_explanation: "Updated fit explanation." };
    const fetchMock = stubMarketFetch([MARKET, updated]); vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh insights" }));
    expect(await screen.findByText("Updated fit explanation.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(8);
  });
});
