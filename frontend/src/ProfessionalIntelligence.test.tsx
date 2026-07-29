import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalCapturePlan } from "./ProfessionalCapturePlan";
import { ProfessionalEvidenceRoot } from "./ProfessionalEvidenceRoot";
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

const verifiedEvidenceRoot = {
  configured: true,
  root_path: "C:\\Evidence",
  exists: true,
  writable: true,
  verified_at: "2026-07-27T00:00:00Z",
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

describe("ProfessionalIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads only when active and shows source and evidence configuration", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/sources")) return new Response(JSON.stringify(sources), { status: 200 });
      if (url.endsWith("/evidence-root")) {
        return new Response(JSON.stringify(emptyEvidenceRoot), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const { rerender } = render(
      <ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active={false} />,
    );
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByRole("heading", { name: "Sources & Evidence" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Main profile" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Feed" })).toBeInTheDocument();
    expect(screen.getAllByText("Trusted source")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Start capture" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence directory" })).toBeInTheDocument();
    expect(screen.getByText(/Supervised captures write their evidence files and manifests/)).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Primary sources" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Secondary sources" })).toBeInTheDocument();
  });

  it("updates the source registry after saving and resetting a source override", async () => {
    const updated = {
      ...sources[0],
      label: "Profile positioning review",
      url: "https://www.linkedin.com/in/rafael-alba-tech/?source=jolt",
      initial_scope: false,
      enabled: false,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/sources") && !init?.method) {
        return new Response(JSON.stringify(sources), { status: 200 });
      }
      if (url.endsWith("/evidence-root") && !init?.method) {
        return new Response(JSON.stringify(emptyEvidenceRoot), { status: 200 });
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

    const updatedCard = updatedHeading.closest("article");
    expect(updatedCard).not.toBeNull();
    fireEvent.click(within(updatedCard as HTMLElement).getByText("Edit approved source"));
    fireEvent.click(
      within(updatedCard as HTMLElement).getByRole("button", { name: "Reset verified default" }),
    );

    expect(await screen.findByRole("heading", { name: "Main profile" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  });

  it("retries an evidence-root failure and clears the stale error", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(verifiedEvidenceRoot), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<ProfessionalEvidenceRoot apiBase="http://api" active onChanged={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load the local evidence directory.");
    fireEvent.click(screen.getByRole("button", { name: "Retry evidence directory" }));

    expect(await screen.findByDisplayValue("C:\\Evidence")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("keeps the newest capture plan when an older request resolves last", async () => {
    let resolveFirst: ((response: Response) => void) | undefined;
    let resolveSecond: ((response: Response) => void) | undefined;
    const first = new Promise<Response>((resolve) => { resolveFirst = resolve; });
    const second = new Promise<Response>((resolve) => { resolveSecond = resolve; });
    const fetchMock = vi.fn()
      .mockReturnValueOnce(first)
      .mockReturnValueOnce(second);
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = render(
      <ProfessionalCapturePlan apiBase="http://api" active refreshKey={0} />,
    );
    rerender(<ProfessionalCapturePlan apiBase="http://api" active refreshKey={1} />);

    resolveSecond?.(new Response(JSON.stringify(capturePlan([sources[1]], [])), { status: 200 }));
    expect(await screen.findByText("Feed")).toBeInTheDocument();

    resolveFirst?.(new Response(JSON.stringify(capturePlan([sources[0]], [])), { status: 200 }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Feed")).toBeInTheDocument();
  });
});