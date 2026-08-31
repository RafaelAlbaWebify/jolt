import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { DataTools } from "./DataTools";

describe("DataTools", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("exports one package for AI review and Market Insights", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    render(<DataTools apiBase="http://127.0.0.1:8000" />);

    const link = screen.getByRole("link", {
      name: "Download for ChatGPT",
    });

    expect(link).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/exports/ai-review-pack",
    );
    expect(link).toHaveAttribute(
      "download",
      "JOLT_AI_REVIEW_INPUT.zip",
    );
    expect(
      screen.getByText(/one JSON file with both Review Inbox decisions and Market Insights/i),
    ).toBeInTheDocument();
  });

  it("imports jobs and Market Insights with one JSON", async () => {
    const onImported = vi.fn();

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            capture_run_id: "capture-1",
            received_count: 2,
            created_count: 2,
            updated_count: 0,
            protected_human_state_count: 0,
            market_insight_action_count: 7,
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      );

    render(
      <DataTools
        apiBase="http://127.0.0.1:8000"
        onImported={onImported}
      />,
    );

    const file = new File(
      [
        JSON.stringify({
          contract_type: "jolt_ai_review",
          contract_version: "2.0",
          capture_run_id: "capture-1",
          review_source: "chatgpt_source_first",
          review_version: "2026-08-31.1",
          reviewed_at: "2026-08-31T12:00:00+02:00",
          jobs: [],
          market_insights: {},
        }),
      ],
      "JOLT_AI_REVIEW.json",
      { type: "application/json" },
    );

    fireEvent.change(screen.getByLabelText("Import AI review"), {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/ai-review/import",
        expect.objectContaining({
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }),
      ),
    );

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("2 AI-reviewed jobs imported");
    expect(status).toHaveTextContent("7 Market Insight actions updated from the same review");
    expect(onImported).toHaveBeenCalledTimes(1);
  });
});
