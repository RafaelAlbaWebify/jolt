import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkedInCommandCenter } from "./LinkedInCommandCenter";

const EMPTY_DASHBOARD = {
  capture_count: 0,
  recommendation_count: 0,
  open_recommendation_count: 0,
  categories: {},
  recommendation_statuses: {},
  captures: [],
  recommendations: [],
};

const POPULATED_DASHBOARD = {
  capture_count: 1,
  recommendation_count: 1,
  open_recommendation_count: 1,
  categories: { profile: 1 },
  recommendation_statuses: { pending: 1 },
  captures: [{
    id: "capture-1",
    category: "profile",
    title: "Profile baseline",
    source_url: "https://www.linkedin.com/in/example/",
    visible_text: "Application Support headline",
    notes: "",
    content_hash: "hash",
    previous_capture_id: null,
    changed_since_previous: false,
    captured_at: "2026-07-30T10:00:00Z",
  }],
  recommendations: [{
    id: "recommendation-1",
    capture_id: "capture-1",
    recommendation_type: "profile_update",
    target_area: "Headline",
    title: "Rewrite headline",
    rationale: "Clarify target role.",
    proposed_action: "Update headline manually.",
    proposed_text: "Application Support Engineer | SaaS Support",
    priority: "high",
    status: "pending",
    created_at: "2026-07-30T10:00:00Z",
    updated_at: "2026-07-30T10:00:00Z",
  }],
};

describe("LinkedInCommandCenter", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads only when active, saves captures, and displays recommendations", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => EMPTY_DASHBOARD })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "capture-1" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => POPULATED_DASHBOARD });
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(<LinkedInCommandCenter apiBase="http://api" active={false} />);
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<LinkedInCommandCenter apiBase="http://api" active />);
    expect(await screen.findByText("No LinkedIn recommendations yet.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Capture LinkedIn" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Profile baseline" } });
    fireEvent.change(screen.getByLabelText("Visible text"), { target: { value: "Application Support headline" } });
    fireEvent.click(screen.getByRole("button", { name: "Save LinkedIn capture" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/linkedin-command-center/captures",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("Rewrite headline")).toBeInTheDocument();
    expect(screen.getByText("Profile baseline")).toBeInTheDocument();
  });

  it("updates recommendation status manually", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => POPULATED_DASHBOARD })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...POPULATED_DASHBOARD.recommendations[0], status: "implemented" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...POPULATED_DASHBOARD, recommendations: [{ ...POPULATED_DASHBOARD.recommendations[0], status: "implemented" }] }) });
    vi.stubGlobal("fetch", fetchMock);

    render(<LinkedInCommandCenter apiBase="http://api" active />);
    const status = await screen.findByDisplayValue("pending");
    fireEvent.change(status, { target: { value: "implemented" } });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/linkedin-command-center/recommendations/recommendation-1/status",
      expect.objectContaining({ method: "POST" }),
    ));
  });
});
