import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalIntelligence } from "./ProfessionalIntelligence";

const sources = [
  {
    source_id: "linkedin-profile",
    label: "Main profile",
    category: "profile",
    url: "https://www.linkedin.com/in/rafael-alba-tech/",
    initial_scope: true,
    enabled: true,
    capture_mode: "supervised_read_only",
  },
  {
    source_id: "linkedin-feed",
    label: "Feed",
    category: "network",
    url: "https://www.linkedin.com/feed/",
    initial_scope: false,
    enabled: true,
    capture_mode: "supervised_read_only",
  },
];

function capturePlan(plannedSources = [sources[0]], excludedSources = [{ source: sources[1], reason: "deferred_scope" }]) {
  return {
    mode: "preview_only",
    execution_available: false,
    planned_sources: plannedSources,
    excluded_sources: excludedSources,
    safety_constraints: [
      "supervised_read_only",
      "no_credentials_or_session_storage",
      "no_account_actions",
      "browser_execution_not_available",
    ],
  };
}

describe("ProfessionalIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads only when active and shows the deterministic capture preview", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/sources")) return new Response(JSON.stringify(sources), { status: 200 });
      if (url.endsWith("/capture-plan")) {
        return new Response(JSON.stringify(capturePlan()), { status: 200 });
      }
      if (url.endsWith("/capture-runs")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const { rerender } = render(
      <ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active={false} />,
    );
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByRole("heading", { name: "Main profile" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Feed" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Initial supervised scope" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Deferred sources" })).toBeInTheDocument();
    expect(screen.getByText(/No login handling/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open approved source" })).toHaveLength(2);
    expect(await screen.findByRole("heading", { name: "Supervised capture plan" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Preview run history" })).toBeInTheDocument();
    expect(screen.getByText("No preview runs recorded.")).toBeInTheDocument();
    expect(screen.getByText("Browser not launched")).toBeInTheDocument();
    expect(screen.getByText("Feed · deferred scope")).toBeInTheDocument();
    expect(screen.getByText("browser execution not available")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/sources",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/capture-plan",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/capture-runs",
    );
  });

  it("refreshes the preview after saving and resetting a source override", async () => {
    const updated = {
      ...sources[0],
      label: "Profile positioning review",
      url: "https://www.linkedin.com/in/rafael-alba-tech/?source=jolt",
      initial_scope: false,
      enabled: false,
    };
    let planCalls = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/sources") && !init?.method) {
        return new Response(JSON.stringify(sources), { status: 200 });
      }
      if (url.endsWith("/capture-runs") && !init?.method) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/capture-plan")) {
        planCalls += 1;
        const payload = planCalls === 1
          ? capturePlan()
          : planCalls === 2
            ? capturePlan([], [
                { source: updated, reason: "disabled_by_user" },
                { source: sources[1], reason: "deferred_scope" },
              ])
            : capturePlan();
        return new Response(JSON.stringify(payload), { status: 200 });
      }
      if (url.endsWith("/linkedin-profile/update")) {
        expect(JSON.parse(String(init?.body))).toEqual({
          label: "Profile positioning review",
          url: "https://www.linkedin.com/in/rafael-alba-tech/?source=jolt",
          initial_scope: false,
          enabled: false,
        });
        return new Response(JSON.stringify(updated), { status: 200 });
      }
      if (url.endsWith("/linkedin-profile/reset")) {
        return new Response(JSON.stringify(sources[0]), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active />);
    const profileHeading = await screen.findByRole("heading", { name: "Main profile" });
    const profileCard = profileHeading.closest("article");
    expect(profileCard).not.toBeNull();
    fireEvent.click(within(profileCard as HTMLElement).getByText("Edit approved source"));
    fireEvent.change(screen.getByLabelText("Source label for linkedin-profile"), {
      target: { value: "Profile positioning review" },
    });
    fireEvent.change(screen.getByLabelText("LinkedIn URL for linkedin-profile"), {
      target: { value: "https://www.linkedin.com/in/rafael-alba-tech/?source=jolt" },
    });
    fireEvent.click(screen.getByLabelText("Initial scope for linkedin-profile"));
    fireEvent.click(screen.getByLabelText("Enabled for linkedin-profile"));
    fireEvent.click(within(profileCard as HTMLElement).getByRole("button", { name: "Save source" }));

    const updatedHeading = await screen.findByRole("heading", { name: "Profile positioning review" });
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    expect(await screen.findByText("Profile positioning review · disabled by user")).toBeInTheDocument();

    const updatedCard = updatedHeading.closest("article");
    expect(updatedCard).not.toBeNull();
    fireEvent.click(within(updatedCard as HTMLElement).getByText("Edit approved source"));
    fireEvent.click(
      within(updatedCard as HTMLElement).getByRole("button", { name: "Reset verified default" }),
    );

    expect(await screen.findByRole("heading", { name: "Main profile" })).toBeInTheDocument();
    await waitFor(() => expect(planCalls).toBe(3));
    expect(fetchMock).toHaveBeenCalledTimes(7);
  });
});
