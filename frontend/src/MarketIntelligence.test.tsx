import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarketIntelligence } from "./MarketIntelligence";

const SCOPE = {
  total_roles: 8,
  strong_roles: 3,
  viable_roles: 4,
  role_families: [{ label: "application_support", count: 5 }],
  work_modes: [{ label: "remote", count: 6 }],
  seniority: [],
  top_companies: [],
  top_locations: [{ label: "Spain", count: 7 }],
  top_skills: [{ label: "SQL", count: 6 }, { label: "API troubleshooting", count: 5 }],
  fit_distribution: [{ label: "strong", count: 3 }, { label: "viable", count: 4 }],
  top_gaps: [{ label: "Linux", count: 4 }],
  study_priorities: [{ label: "Linux", count: 4 }, { label: "KQL", count: 2 }],
  salary_mentions: [{ title: "Application Support Engineer", company: "Example", mention: "€45,000" }],
  salary_coverage: 0.5,
};

const DATA = {
  filters: { timeframe: "all", source_scope: "all" },
  total_unique_roles: 10,
  target_role_count: 8,
  outside_target_count: 2,
  target: SCOPE,
  all: { ...SCOPE, total_roles: 10 },
  outside_title_examples: [],
  fit_explanation: "Target support roles show repeatable fit and a small number of preparation gaps.",
};

describe("MarketIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders actionable market evidence without preparation import or preference editors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("heading", { name: "Market Insights" })).toBeInTheDocument();
    expect(await screen.findByText("Double down on")).toBeInTheDocument();
    expect(screen.getByText("Prepare next")).toBeInTheDocument();
    expect(screen.getByText("SQL (6)")).toBeInTheDocument();
    expect(screen.getByText("Linux (4)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Job-search preferences/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/preparation pack/i)).not.toBeInTheDocument();
  });

  it("applies timeframe and source filters directly to the market endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByText("Double down on");

    fireEvent.change(screen.getByLabelText("Timeframe"), { target: { value: "last_30_days" } });
    fireEvent.change(screen.getByLabelText("Source"), { target: { value: "capture_batches" } });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/market-intelligence?timeframe=last_30_days&source_scope=capture_batches",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));
  });

  it("switches between target and all retained role scopes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);
    expect(await screen.findByText("8")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Scope"), { target: { value: "all" } });
    expect(screen.getByText("10")).toBeInTheDocument();
  });
});
