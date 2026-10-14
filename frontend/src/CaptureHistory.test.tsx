import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CaptureHistory } from "./CaptureHistory";

const capture = {
  capture_run_id: "capture-1",
  source: "linkedin",
  mode: "supervised_live",
  status: "completed",
  search_url: "https://www.linkedin.com/jobs/search/",
  warnings: [],
  requested_item_limit: 3,
  observed_item_count: 3,
  stop_reason: "requested_limit_reached",
  started_at: "2026-07-14T08:00:00Z",
  completed_at: "2026-07-14T08:01:00Z",
  total_items: 3,
  verified_items: 3,
  rejected_items: 0,
};

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), { status: 200 });
}

describe("CaptureHistory", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows configured bounds, observed counts, and stop reason in summary and diagnostics", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/captures")) return jsonResponse([capture]);
      if (url.endsWith("/api/captures/capture-1")) {
        return jsonResponse({ ...capture, pages: [], items: [] });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<CaptureHistory apiBase="http://127.0.0.1:8000" onError={vi.fn()} />);

    expect(await screen.findByText("3 observed · 3 requested")).toBeInTheDocument();
    expect(screen.getByText("requested limit reached")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Inspect capture" }));

    expect(await screen.findByText("Captured opportunities · 0")).toBeInTheDocument();
    expect(screen.getAllByText("3 observed · 3 requested")).toHaveLength(1);
    const inspector = screen.getByText("Captured opportunities · 0");
    expect(screen.getByRole("button", { name: "Inspect capture" }).closest("article")).toContainElement(inspector);
  });

  it("labels legacy runs without inventing a requested bound", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([{
      ...capture,
      requested_item_limit: null,
      observed_item_count: 0,
      stop_reason: "legacy_unknown",
    }]));

    render(<CaptureHistory apiBase="http://127.0.0.1:8000" onError={vi.fn()} />);

    expect(await screen.findByText("0 observed · not recorded requested")).toBeInTheDocument();
    expect(screen.getByText("legacy unknown")).toBeInTheDocument();
  });
  it("requires operator confirmation to import supervised observations for review", async () => {
    const source = {
      ...capture,
      source: "infojobs",
      mode: "supervised_browser_observation",
      verified_items: 0,
      total_items: 1,
    };
    const item = {
      capture_item_id: "observed-1",
      source_job_id: "9a3c6c996942d0b2d0f19cacaf8f2e",
      source_url: "https://www.infojobs.net/madrid/support/of-i9a3c6c996942d0b2d0f19cacaf8f2e",
      title: "IT Support Engineer",
      company: "Example Employer",
      location: "Madrid (Madrid)",
      detail_status: "observed_unverified",
      verification_reasons: ["Work-from-Spain eligibility not verified"],
      posting_id: null,
    };
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const requests: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      requests.push(url);
      if (url.endsWith("/api/captures")) return jsonResponse([source]);
      if (url.endsWith("/api/captures/capture-1")) {
        return jsonResponse({ ...source, pages: [], items: [item] });
      }
      throw new Error("Unexpected request: " + url);
    });
    render(<CaptureHistory apiBase="http://127.0.0.1:8000" onError={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Inspect capture" }));
    fireEvent.click(await screen.findByRole("button", { name: "Create opportunity for review" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(requests.some((url) => url.includes("/review-import"))).toBe(false);
  });

  it("imports confirmed supervised evidence via the existing captures endpoint", async () => {
    const run = { ...capture, source: "jobgether", mode: "supervised_browser_observation", verified_items: 0 };
    const item = {
      capture_item_id: "item-1", source_job_id: "a".repeat(24),
      source_url: "https://jobgether.com/offer/" + "a".repeat(24) + "-support",
      title: "Remote Support Engineer", company: "Example Employer", location: "",
      detail_status: "observed_unverified", verification_reasons: [], posting_id: null,
    };
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let imported = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/captures")) return jsonResponse([run]);
      if (url.endsWith("/api/captures/capture-1")) {
        return jsonResponse({ ...run, pages: [], items: [imported ? { ...item, posting_id: "posting-1", detail_status: "verified" } : item] });
      }
      if (url.endsWith("/api/captures/observations/item-1/review-import") && init?.method === "POST") {
        imported = true;
        return jsonResponse({ status: "imported_for_review", posting_id: "posting-1" });
      }
      throw new Error("Unexpected request: " + url);
    });
    render(<CaptureHistory apiBase="http://127.0.0.1:8000" onError={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Inspect capture" }));
    fireEvent.click(await screen.findByRole("button", { name: "Create opportunity for review" }));
    await waitFor(() => expect(imported).toBe(true));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Create opportunity for review" })).not.toBeInTheDocument());
  });

  it("defers capture history retrieval until Capture Jobs is active", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([capture]));
    const { rerender } = render(
      <CaptureHistory apiBase="http://127.0.0.1:8000" onError={vi.fn()} active={false} />,
    );
    expect(fetchMock).not.toHaveBeenCalled();
    rerender(<CaptureHistory apiBase="http://127.0.0.1:8000" onError={vi.fn()} active />);
    expect(await screen.findByText("3 observed · 3 requested")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

});
