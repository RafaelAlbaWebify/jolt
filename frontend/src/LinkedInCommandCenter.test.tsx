import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkedInCommandCenter } from "./LinkedInCommandCenter";

const EMPTY = {
  capture_count: 0,
  recommendation_count: 0,
  open_recommendation_count: 0,
  categories: {},
  captures: [],
  recommendations: [],
};

const POPULATED = {
  capture_count: 1,
  recommendation_count: 1,
  open_recommendation_count: 1,
  categories: { profile: 1 },
  captures: [{
    id: "capture-1",
    category: "profile",
    title: "Profile",
    source_url: "https://www.linkedin.com/in/example/",
    visible_text: "Application Support Engineer",
    notes: "",
    changed_since_previous: true,
    captured_at: "2026-08-02T09:00:00Z",
  }],
  recommendations: [{
    id: "recommendation-1",
    recommendation_type: "profile_update",
    target_area: "Headline",
    title: "Clarify the headline",
    rationale: "Make the target role explicit.",
    proposed_action: "Edit the LinkedIn headline manually.",
    proposed_text: "Application Support Engineer | SaaS Support",
    priority: "high",
    status: "pending",
  }],
};

describe("LinkedInCommandCenter", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("uses one profile-only target registry and excludes job-search targets", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(EMPTY), { status: 200 }));
    render(<LinkedInCommandCenter apiBase="http://api" active />);

    expect(await screen.findByRole("heading", { name: "LinkedIn Profile" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Capture targets" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Capture targets" }));

    const registry = screen.getByRole("region", { name: "Capture targets" });
    expect(within(registry).getByText("Experience")).toBeInTheDocument();
    expect(within(registry).getByText("Skills")).toBeInTheDocument();
    expect(within(registry).getByText("Licenses & certifications")).toBeInTheDocument();
    expect(within(registry).getByText("All activity")).toBeInTheDocument();
    expect(within(registry).queryByText("Job Tracker")).not.toBeInTheDocument();
    expect(within(registry).queryByText("Jobs Based on my Preferences")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import analysis" })).not.toBeInTheDocument();
  });

  it("captures one target and refreshes retained evidence", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(EMPTY), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(POPULATED.captures[0]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(POPULATED), { status: 200 }));

    render(<LinkedInCommandCenter apiBase="http://api" active />);
    await screen.findByText("No LinkedIn profile evidence yet.");
    fireEvent.click(screen.getByRole("button", { name: "Capture targets" }));

    const profileCard = screen.getByText("Profile").closest("article");
    expect(profileCard).not.toBeNull();
    fireEvent.click(within(profileCard as HTMLElement).getByRole("button", { name: "Capture" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/linkedin-command-center/captures/playwright",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("Profile captured and stored as LinkedIn profile evidence.")).toBeInTheDocument();
    expect(screen.getByText("Application Support Engineer")).toBeInTheDocument();
  });

  it("keeps manual evidence as a fallback and updates recommendation status", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(POPULATED), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...POPULATED.recommendations[0], status: "implemented" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...POPULATED, open_recommendation_count: 0, recommendations: [{ ...POPULATED.recommendations[0], status: "implemented" }] }), { status: 200 }));

    render(<LinkedInCommandCenter apiBase="http://api" active />);
    expect(await screen.findByText("Clarify the headline")).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("pending"), { target: { value: "implemented" } });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/linkedin-command-center/recommendations/recommendation-1/status",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByDisplayValue("implemented")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Manual evidence" })).toBeInTheDocument();
  });
});
