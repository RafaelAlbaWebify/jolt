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

const emptyEvidenceRoot = {
  configured: false,
  root_path: null,
  exists: false,
  writable: false,
  verified_at: null,
};

function capturePlan(
  plannedSources = [sources[0]],
  excludedSources = [{ source: sources[1], reason: "deferred_scope" }],
) {
  return {
    mode: "supervised_read_only",
    execution_available: true,
    planned_sources: plannedSources,
    excluded_sources: excludedSources,
    safety_constraints: [
      "explicit_user_start_required",
      "visible_fresh_browser_context_per_source",
      "no_credentials_cookies_or_tokens_in_evidence",
      "no_unattended_capture",
    ],
  };
}

function executionReadiness() {
  return {
    ready: false,
    execution_available: true,
    blockers: ["local_evidence_root_not_verified"],
    required_user_actions: [
      "choose_local_evidence_root",
      "record_and_authorize_each_run_explicitly",
      "remain_present_during_capture",
      "review_artifacts_before_analysis",
    ],
    evidence_policy: {
      allowed_artifact_types: [
        "capture_metadata_json",
        "page_diagnostics_json",
        "rendered_text_json",
        "screenshot_png",
      ],
      page_completeness_statuses: ["complete", "partial", "failed"],
      default_retention_days: 30,
      maximum_retention_days: 365,
      text_extraction_policy: ["visible_rendered_dom_text_is_primary"],
      prohibited_evidence: ["credentials", "cookies", "tokens", "browser_storage_state"],
    },
  };
}

describe("ProfessionalIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads only when active and shows the supervised execution contract", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/sources")) return new Response(JSON.stringify(sources), { status: 200 });
      if (url.endsWith("/evidence-root")) {
        return new Response(JSON.stringify(emptyEvidenceRoot), { status: 200 });
      }
      if (url.endsWith("/capture-plan")) {
        return new Response(JSON.stringify(capturePlan()), { status: 200 });
      }
      if (url.endsWith("/capture-runs")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/execution-readiness")) {
        return new Response(JSON.stringify(executionReadiness()), { status: 200 });
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
    expect(screen.getByRole("heading", { name: "Evidence directory" })).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Supervised capture readiness" })).toBeInTheDocument();
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(screen.getByText("local evidence root not verified")).toBeInTheDocument();
    expect(screen.getByText("Default retention: 30 days.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Supervised capture plan" })).toBeInTheDocument();
    expect(screen.getByText("Explicit start available")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Supervised run history" })).toBeInTheDocument();
    expect(screen.getByText("No preview runs recorded.")).toBeInTheDocument();
    expect(screen.getByText("Feed · deferred scope")).toBeInTheDocument();
    expect(screen.getByText("visible fresh browser context per source")).toBeInTheDocument();
  });

  it("refreshes the supervised plan after saving and resetting a source override", async () => {
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
      if (url.endsWith("/evidence-root") && !init?.method) {
        return new Response(JSON.stringify(emptyEvidenceRoot), { status: 200 });
      }
      if (url.endsWith("/capture-runs") && !init?.method) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/execution-readiness")) {
        return new Response(JSON.stringify(executionReadiness()), { status: 200 });
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
    expect(fetchMock).toHaveBeenCalledTimes(9);
  });
});
