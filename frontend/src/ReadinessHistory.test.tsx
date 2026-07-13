import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReadinessHistory } from "./ReadinessHistory";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), { status: 200 });
}

describe("ReadinessHistory", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads immutable readiness history and refreshes the current report", async () => {
    let refreshed = false;
    const onRefreshed = vi.fn(async () => undefined);
    const onError = vi.fn();

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/readiness/refresh") && init?.method === "POST") {
        refreshed = true;
        return jsonResponse({ report_id: "report-2" });
      }
      if (url.endsWith("/readiness/history")) {
        return jsonResponse(refreshed ? [
          {
            report_id: "report-2",
            profile_version_id: "rafael-job-search:v2",
            engine_version: "application-readiness-v1",
            priority: "high",
            readiness_score: 91,
            evidence_matches: [],
            credibility_warnings: [],
            cv_tailoring_points: [],
            talking_points: [],
            interview_questions: [],
            revision_topics: [],
            checklist: [],
            created_at: "2026-07-14T00:00:00Z",
            is_current: true,
            refresh_reason: "manual_recalculation",
            supersedes_report_id: "report-1",
          },
          {
            report_id: "report-1",
            profile_version_id: "rafael-job-search:v2",
            engine_version: "application-readiness-v1",
            priority: "medium",
            readiness_score: 75,
            evidence_matches: [],
            credibility_warnings: [],
            cv_tailoring_points: [],
            talking_points: [],
            interview_questions: [],
            revision_topics: [],
            checklist: [],
            created_at: "2026-07-13T00:00:00Z",
            is_current: false,
          },
        ] : []);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ReadinessHistory
        apiBase="http://127.0.0.1:8000"
        postingId="posting-1"
        title="Application Support Engineer"
        disabled={false}
        onRefreshed={onRefreshed}
        onError={onError}
      />,
    );

    fireEvent.click(screen.getByText("Readiness report history"));
    fireEvent.click(screen.getByRole("button", { name: "Recalculate readiness" }));

    expect(await screen.findByText("Current report")).toBeInTheDocument();
    expect(screen.getByText("Historical report")).toBeInTheDocument();
    expect(screen.getByText("high priority · 91/100")).toBeInTheDocument();
    expect(screen.getByText("medium priority · 75/100")).toBeInTheDocument();
    expect(onRefreshed).toHaveBeenCalledOnce();
    expect(onError).toHaveBeenCalledWith("");
  });
});
