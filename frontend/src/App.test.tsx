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

import { App } from "./App";

function jsonResponse(
  payload: unknown,
  status = 200,
) {
  return new Response(
    JSON.stringify(payload),
    {
      status,
      headers: {
        "Content-Type": "application/json",
      },
    },
  );
}

const reviewedOpportunity = {
  posting_id: "posting-1",
  source_url: "https://example.com/job-1",
  title: "Application Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",

  ai_review_id: "ai-review-1",
  ai_review_status: "reviewed",

  decision: "strong_pursue",
  priority_score: 94,

  geography_status: "eligible",
  clearance_status: "clear",
  language_status: "conditional",
  technical_fit: 91,

  duplicate_of_posting_id: null,

  summary: "Strong application support fit.",
  reasons: [
    "Spain-compatible employment.",
    "Strong production support alignment.",
  ],

  review_decision: null,
  application_id: null,
  application_status: null,

  reviewed_at: "2026-08-27T14:00:00Z",
  imported_at: "2026-08-27T14:05:00Z",
};

const awaitingOpportunity = {
  ...reviewedOpportunity,
  posting_id: "posting-2",
  title: "Cloud Operations Analyst",
  company: "Other Co",

  ai_review_id: null,
  ai_review_status: "awaiting_ai_review",

  decision: null,
  priority_score: null,

  geography_status: null,
  clearance_status: null,
  language_status: null,
  technical_fit: null,

  summary: "",
  reasons: [],
};

describe("App AI review workflow", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads the AI-authoritative Review Inbox", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);

        if (
          url.endsWith(
            "/api/ai-review/opportunity-index",
          )
        ) {
          return jsonResponse([
            reviewedOpportunity,
            awaitingOpportunity,
          ]);
        }

        throw new Error(
          `Unexpected request: ${url}`,
        );
      });

    render(<App />);

    expect(
      await screen.findByText(
        "Application Support Engineer",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText("strong pursue"),
    ).toBeInTheDocument();

    expect(
      screen.getAllByText("Awaiting AI review").length,
    ).toBeGreaterThanOrEqual(1);

    expect(
      fetchMock,
    ).toHaveBeenCalledTimes(1);

    expect(
      String(fetchMock.mock.calls[0][0]),
    ).toContain(
      "/api/ai-review/opportunity-index",
    );

    expect(
      String(fetchMock.mock.calls[0][0]),
    ).not.toContain(
      "/api/opportunity-index",
    );
  });

  it("shows imported AI reasoning in the inspector without fetching Python analysis", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse([reviewedOpportunity]),
      );

    render(<App />);

    expect(
      await screen.findByText(
        "Application Support Engineer",
      ),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Inspect",
      }),
    );

    expect(
      screen.getByText(
        "Strong application support fit.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Spain-compatible employment.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText("eligible"),
    ).toBeInTheDocument();

    expect(
      fetchMock,
    ).toHaveBeenCalledTimes(1);
  });

  it("sends ai_review_id when the human chooses pursue", async () => {
    let index = [reviewedOpportunity];

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(
        async (input, init) => {
          const url = String(input);

          if (
            url.endsWith(
              "/api/ai-review/opportunity-index",
            )
          ) {
            return jsonResponse(index);
          }

          if (
            url.endsWith(
              "/api/opportunities/posting-1/reviews",
            ) &&
            init?.method === "POST"
          ) {
            const body = JSON.parse(
              String(init.body),
            ) as Record<string, unknown>;

            expect(body).toEqual({
              ai_review_id: "ai-review-1",
              decision: "pursue",
            });

            expect(
              "evaluation_id" in body,
            ).toBe(false);

            index = [];

            return jsonResponse({
              review_id: "review-1",
              posting_id: "posting-1",
              evaluation_id: null,
              ai_review_id: "ai-review-1",
              decision: "pursue",
              evaluation_overridden: false,
            });
          }

          throw new Error(
            `Unexpected request: ${url}`,
          );
        },
      );

    render(<App />);

    expect(
      await screen.findByText(
        "Application Support Engineer",
      ),
    ).toBeInTheDocument();

    fireEvent.change(
      screen.getByLabelText(
        "Decision for Application Support Engineer",
      ),
      {
        target: {
          value: "pursue",
        },
      },
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/opportunities/posting-1/reviews",
        expect.objectContaining({
          method: "POST",
        }),
      ),
    );

    expect(
      await screen.findByRole("status"),
    ).toHaveTextContent(
      "Application Pipeline",
    );
  });

  it("prevents a human decision before AI review exists", async () => {
    vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      jsonResponse([awaitingOpportunity]),
    );

    render(<App />);

    expect(
      await screen.findByText(
        "Cloud Operations Analyst",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText(
        "Decision for Cloud Operations Analyst",
      ),
    ).toBeDisabled();
  });

  it("sorts strong pursue before awaiting and reject", async () => {
    const rejected = {
      ...reviewedOpportunity,
      posting_id: "posting-3",
      title: "Foreign Restricted Support",
      ai_review_id: "ai-review-3",
      decision: "reject",
      priority_score: 0,
      geography_status: "ineligible",
    };

    vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      jsonResponse([
        rejected,
        awaitingOpportunity,
        reviewedOpportunity,
      ]),
    );

    render(<App />);

    await screen.findByText(
      "Application Support Engineer",
    );

    const headings =
      screen.getAllByRole(
        "heading",
        { level: 3 },
      );

    expect(headings[0]).toHaveTextContent(
      "Application Support Engineer",
    );

    expect(headings[1]).toHaveTextContent(
      "Cloud Operations Analyst",
    );

    expect(headings[2]).toHaveTextContent(
      "Foreign Restricted Support",
    );
  });

  it("clears the pending AI Review Inbox after confirmation", async () => {
    let index = [awaitingOpportunity];

    vi.spyOn(
      window,
      "confirm",
    ).mockReturnValue(true);

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(
        async (input, init) => {
          const url = String(input);

          if (
            url.endsWith(
              "/api/ai-review/opportunity-index",
            )
          ) {
            return jsonResponse(index);
          }

          if (
            url.endsWith(
              "/api/review-inbox/clear-pending",
            ) &&
            init?.method === "POST"
          ) {
            index = [];

            return jsonResponse({
              pending_before: 1,
              pending_after: 0,
              cleared_pending_count: 1,
              archived_capture_run_count: 1,
              protected_pending_count: 0,
              archived_runs: [],
            });
          }

          throw new Error(
            `Unexpected request: ${url}`,
          );
        },
      );

    render(<App />);

    fireEvent.click(
      await screen.findByRole(
        "button",
        {
          name: "Clear pending inbox (1)",
        },
      ),
    );

    expect(
      await screen.findByText(
        /1 pending card cleared from 1 capture batch/,
      ),
    ).toBeInTheDocument();
  });
});
