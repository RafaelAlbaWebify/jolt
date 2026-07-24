import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalCapturePlan } from "./ProfessionalCapturePlan";

const plan = {
  mode: "preview_only",
  execution_available: false,
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
  safety_constraints: ["no_credentials_or_session_storage", "no_account_actions"],
};

describe("ProfessionalCapturePlan", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not fetch while inactive and renders a preview-only plan when activated", async () => {
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
    expect(screen.getByText("Browser not launched")).toBeInTheDocument();
    expect(screen.getByText("no credentials or session storage")).toBeInTheDocument();
  });
});
