import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarketIntelligence } from "./MarketIntelligence";

const SCOPE = {
  total_roles: 8,
  role_families: [{ label: "application_support", count: 5 }],
  work_modes: [{ label: "remote", count: 6 }],
  seniority: [{ label: "mid_level", count: 4 }],
  top_companies: [{ label: "Example", count: 3 }],
  top_locations: [{ label: "Spain", count: 7 }],
  top_skills: [{ label: "SQL", count: 6 }, { label: "API troubleshooting", count: 5 }],
  required_skills: [{ label: "SQL", count: 4 }],
  preferred_skills: [{ label: "Azure", count: 3 }],
  mentioned_skills: [{ label: "Windows", count: 5 }],
  salary_mentions: [{ title: "Application Support Engineer", company: "Example", mention: "€45,000" }],
  salary_role_count: 4,
  salary_coverage: 0.5,
  salary_coverage_percent: 50,
};

const DATA = {
  filters: { timeframe: "all", source_scope: "all" },
  evidence_provenance: {
    source_posting_count: 10,
    canonical_role_count: 8,
    duplicate_member_count: 2,
    oldest_evidence_at: "2026-07-01T10:00:00+00:00",
    newest_evidence_at: "2026-08-15T10:00:00+00:00",
  },
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

  it("renders evidence without legacy career-authority guidance", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("heading", { name: "Market Insights" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Role families" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence provenance" })).toBeInTheDocument();
    expect(screen.getByText("10 retained observations · 8 canonical roles · 2 duplicate observations")).toBeInTheDocument();
    expect(screen.getByText("4 / 8 · 50%")).toBeInTheDocument();
    expect(screen.queryByText("Strong fit")).not.toBeInTheDocument();
    expect(screen.queryByText("Viable fit")).not.toBeInTheDocument();
    expect(screen.queryByText("Fit distribution")).not.toBeInTheDocument();
    expect(screen.queryByText("Prepare next")).not.toBeInTheDocument();
    expect(screen.queryByText("Double down on")).not.toBeInTheDocument();
    expect(screen.queryByText("What to do next")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Job-search preferences/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/preparation pack/i)).not.toBeInTheDocument();
  });

  it("keeps demand and salary evidence available in focused non-stacked views", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByRole("heading", { name: "Role families" });
    expect(screen.getByText("4 / 8 · 50%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Demand signals" }));
    expect(screen.getByRole("tabpanel", { name: "Demand signals" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "All skill mentions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Explicitly required skills" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Explicitly preferred skills" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Other skill mentions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Companies" })).toBeInTheDocument();
    expect(screen.queryByText("Repeated blockers and gaps")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Salary evidence" }));
    expect(screen.getByRole("tabpanel", { name: "Salary evidence" })).toBeInTheDocument();
    expect(screen.getByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.getByText("€45,000")).toBeInTheDocument();
    expect(screen.getByText("4 of 8 roles (50%) contain salary evidence.")).toBeInTheDocument();
  });

  it("applies timeframe and source filters directly to the market endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(DATA), { status: 200 }));
    render(<MarketIntelligence apiBase="http://api" active />);
    await screen.findByRole("heading", { name: "Role families" });

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
