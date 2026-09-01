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
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("defaults AI review export to JSON and can expose ZIP too", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    render(<DataTools apiBase="http://127.0.0.1:8000" />);

    const jsonChoice = screen.getByRole("radio", { name: /JSON — Recommended/i });
    const zipChoice = screen.getByRole("radio", { name: /ZIP — Full package/i });

    expect(jsonChoice).toBeChecked();
    expect(zipChoice).not.toBeChecked();

    const jsonLink = screen.getByRole("link", { name: "Download AI review JSON" });
    expect(jsonLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/exports/ai-review-json",
    );
    expect(jsonLink).toHaveAttribute("download", "JOLT_AI_REVIEW_INPUT.json");
    expect(screen.queryByRole("link", { name: "Download AI review ZIP" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /Also show the other format/i }));

    const zipLink = screen.getByRole("link", { name: "Download AI review ZIP" });
    expect(zipLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/exports/ai-review-pack",
    );
    expect(zipLink).toHaveAttribute("download", "JOLT_AI_REVIEW_INPUT.zip");

    fireEvent.click(zipChoice);
    expect(zipChoice).toBeChecked();
    expect(window.localStorage.getItem("jolt.aiReview.primaryExportFormat")).toBe("zip");

    expect(
      screen.getByText(
        /JOLT does not include its own recommendation, score, or eligibility decision/i,
      ),
    ).toBeInTheDocument();
  });

  it("imports an AI review JSON and refreshes the inbox", async () => {
    const onImported = vi.fn();

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          capture_run_id: "capture-1",
          received_count: 2,
          created_count: 2,
          updated_count: 0,
          protected_human_state_count: 0,
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
          contract_version: "1.0",
          capture_run_id: "capture-1",
          review_source: "chatgpt_source_first",
          review_version: "2026-08-27.1",
          reviewed_at: "2026-08-27T16:00:00+02:00",
          jobs: [],
        }),
      ],
      "JOLT_AI_REVIEW.json",
      {
        type: "application/json",
      },
    );

    fireEvent.change(screen.getByLabelText("Import AI review"), {
      target: {
        files: [file],
      },
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

    expect(await screen.findByRole("status")).toHaveTextContent(
      "2 AI-reviewed jobs imported",
    );

    expect(onImported).toHaveBeenCalledTimes(1);
  });
});
