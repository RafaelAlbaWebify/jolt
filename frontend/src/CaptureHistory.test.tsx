import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

    expect(await screen.findByText("Capture diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Capture bound:")).toBeInTheDocument();
    expect(screen.getByText("Stop reason:")).toBeInTheDocument();
    expect(screen.getAllByText("3 observed · 3 requested")).toHaveLength(2);
    expect(screen.getAllByText("requested limit reached")).toHaveLength(2);
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
});
