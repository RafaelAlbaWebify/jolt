import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkedInAIAnalysisStatus } from "./LinkedInAIAnalysisStatus";

describe("LinkedInAIAnalysisStatus", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("marks profile analysis stale when capture evidence is newer than the latest ChatGPT review", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/linkedin-command-center")) {
        return new Response(
          JSON.stringify({
            capture_count: 2,
            captures: [
              { captured_at: "2026-09-04T08:30:00Z" },
              { captured_at: "2026-09-03T08:30:00Z" },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/api/ai-linkedin/feedback")) {
        return new Response(
          JSON.stringify({
            total_import_count: 1,
            records: [
              {
                reviewed_at: "2026-09-03T17:00:00Z",
                imported_at: "2026-09-03T17:10:00Z",
                review_version: "review-v1",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <LinkedInAIAnalysisStatus
        apiBase="http://127.0.0.1:8000"
        active
      />,
    );

    expect(await screen.findByText("Analysis outdated")).toBeInTheDocument();
    expect(
      screen.getByText(/evidence is newer than the latest ChatGPT review/i),
    ).toBeInTheDocument();
  });

  it("marks profile analysis current after a newer ChatGPT review is imported", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/linkedin-command-center")) {
        return new Response(
          JSON.stringify({
            capture_count: 1,
            captures: [{ captured_at: "2026-09-04T08:30:00Z" }],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/api/ai-linkedin/feedback")) {
        return new Response(
          JSON.stringify({
            total_import_count: 2,
            records: [
              {
                reviewed_at: "2026-09-04T09:00:00Z",
                imported_at: "2026-09-04T09:05:00Z",
                review_version: "review-v2",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <LinkedInAIAnalysisStatus
        apiBase="http://127.0.0.1:8000"
        active
      />,
    );

    await waitFor(() => expect(screen.getByText("Current")).toBeInTheDocument());
    expect(
      screen.getByText(/latest captured profile evidence has a ChatGPT review/i),
    ).toBeInTheDocument();
  });
});
