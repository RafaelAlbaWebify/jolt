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
  target: { ...EMPTY_SCOPE, total_roles: 1 },
  all: { ...EMPTY_SCOPE, total_roles: 1 },
  outside_title_examples: [],
  fit_explanation: "Stable fit explanation.",
};

describe("MarketIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not fetch while hidden and loads on first activation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => MARKET });
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(<MarketIntelligence apiBase="http://api" active={false} />);
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<MarketIntelligence apiBase="http://api" active />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
  });

  it("shows a stable failure and retries only when requested", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, json: async () => MARKET });
    vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load market insights.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry insights load" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
  });

  it("refreshes explicitly after initial data is loaded", async () => {
    const updated = { ...MARKET, fit_explanation: "Updated fit explanation." };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => MARKET })
      .mockResolvedValueOnce({ ok: true, json: async () => updated });
    vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh insights" }));
    expect(await screen.findByText("Updated fit explanation.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});