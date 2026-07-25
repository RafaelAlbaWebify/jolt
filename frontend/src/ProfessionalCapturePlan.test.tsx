import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalCapturePlan } from "./ProfessionalCapturePlan";

const plan = {
  mode: "supervised_read_only",
  execution_available: true,
  planned_sources: [
    {
      source_id: "linkedin-profile",
      label: "Main profile",
      category: "profile",
      url: "https://www.linkedin.com/in/rafael-alba-tech/",
      initial_scope: true,
      enabled: true,
      capture_mode: "supervised_read_only",
    },
  ],
  excluded_sources: [
    {
      source: {
        source_id: "linkedin-feed",
        label: "Feed",
        category: "network",
        url: "https://www.linkedin.com/feed/",
        initial_scope: false,
        enabled: true,
        capture_mode: "supervised_read_only",
      },
      reason: "deferred_scope",
    },
  ],
  safety_constraints: [
    "visible_fresh_browser_context_per_source",
    "no_credentials_cookies_or_tokens_in_evidence",
    "no_unattended_capture",
  ],
};

describe("ProfessionalCapturePlan", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not fetch while inactive and renders the supervised plan when activated", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(plan), { status: 200 }),
    );
    const { rerender } = render(
      <ProfessionalCapturePlan apiBase="http://127.0.0.1:8000" active={false} refreshKey={0} />,
    );
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(
      <ProfessionalCapturePlan apiBase="http://127.0.0.1:8000" active refreshKey={0} />,
    );

    expect(await screen.findByRole("heading", { name: "Supervised capture plan" })).toBeInTheDocument();
    expect(screen.getByText("Main profile")).toBeInTheDocument();
    expect(screen.getByText("Feed · deferred scope")).toBeInTheDocument();
    expect(screen.getByText("Explicit start available")).toBeInTheDocument();
    expect(screen.getByText("visible fresh browser context per source")).toBeInTheDocument();
  });
});
