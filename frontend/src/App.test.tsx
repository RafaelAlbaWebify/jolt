import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
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

  hardline_status: "PASS",
  hardline_reasons: [],
  location_eligibility: "eligible",
  location_evidence: ["Remote Spain"],
  mandatory_requirements: [],
  mandatory_requirement_results: [],
  employment_constraints: [],
  fit_analysis_allowed: true,
  decision_reason: "Eligible and strongly aligned.",

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

  hardline_status: null,
  hardline_reasons: [],
  location_eligibility: null,
  location_evidence: [],
  mandatory_requirements: [],
  mandatory_requirement_results: [],
  employment_constraints: [],
  fit_analysis_allowed: null,
  decision_reason: "",

  geography_status: null,
  clearance_status: null,
  language_status: null,
  technical_fit: null,

  summary: "",
  reasons: [],
};

const hardlineRejectedOpportunity = {
  ...reviewedOpportunity,
  posting_id: "posting-us-only",
  source_url: "https://example.com/job-us-only",
  title: "Technical Support Engineer L2",
  company: "LucidLink",
  location: "United States · Remote",
  ai_review_id: "ai-review-us-only",
  decision: "reject",
  priority_score: 0,
  hardline_status: "REJECT",
  hardline_reasons: ["US-only remote: applicants must be anywhere in the US."],
  location_eligibility: "ineligible",
  location_evidence: ["United States · Remote", "anywhere in the US"],
  fit_analysis_allowed: false,
  decision_reason: "US-only remote hardline.",
  geography_status: "ineligible",
  technical_fit: null,
  summary: "Rejected at Stage 1 before technical fit analysis.",
  reasons: ["US-only remote requisition."],
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
      screen.getAllByText("High priority").length,
    ).toBeGreaterThanOrEqual(1);

    expect(
      screen.getAllByText("Needs AI review").length,
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

  it("exports the current AI review package from Review Inbox", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse([reviewedOpportunity, awaitingOpportunity]),
    );

    render(<App />);

    await screen.findByText("Cloud Operations Analyst");

    const exportLink = screen.getByRole("link", { name: "Export AI review (1)" });
    expect(exportLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/ai-work-package/export",
    );
    expect(exportLink).toHaveAttribute("download", "JOLT_AI_WORK_PACKAGE.json");
  });

  it("imports a reviewed AI work package from Review Inbox", async () => {
    let index: Array<typeof reviewedOpportunity | typeof awaitingOpportunity> = [
      awaitingOpportunity,
    ];

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input, init) => {
        const url = String(input);

        if (url.endsWith("/api/ai-review/opportunity-index")) {
          return jsonResponse(index);
        }

        if (
          url.endsWith("/api/ai-work-package/import") &&
          init?.method === "POST"
        ) {
          expect(JSON.parse(String(init.body))).toEqual({
            contract_type: "jolt_ai_work_package_update",
            package_id: "package-1",
          });

          index = [reviewedOpportunity];

          return jsonResponse({
            package_id: "package-1",
            imported_sections: [],
            review_inbox_imported: true,
            section_results: {
              review_inbox: {
                received_count: 1,
              },
            },
          });
        }

        throw new Error(`Unexpected request: ${url}`);
      },
    );

    render(<App />);

    await screen.findByText("Cloud Operations Analyst");

    const input = screen.getByLabelText("AI review result file");
    const file = new File(
      [
        JSON.stringify({
          contract_type: "jolt_ai_work_package_update",
          package_id: "package-1",
        }),
      ],
      "JOLT_AI_WORK_PACKAGE_REVIEWED.json",
      { type: "application/json" },
    );

    fireEvent.change(input, {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/ai-work-package/import",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    expect(
      await screen.findByText("AI review imported successfully for 1 job."),
    ).toBeInTheDocument();
  });

  it("switches the selected-job preview between overview, fit analysis, and job details", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse([reviewedOpportunity]),
    );

    render(<App />);

    await screen.findByText("Application Support Engineer");

    expect(await screen.findByText("Why it looks promising")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Fit analysis" }));
    expect(screen.getByText("Fit assessment")).toBeInTheDocument();
    expect(screen.getByText("Evidence supporting the match")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Job details" }));
    expect(screen.getByText("Mandatory requirements")).toBeInTheDocument();
    expect(screen.getAllByText("Location evidence").length).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole("tab", { name: "Overview" }));
    expect(screen.getByText("Why it looks promising")).toBeInTheDocument();
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

    const dialog = screen.getByRole("dialog", {
      name: "Application Support Engineer",
    });

    expect(
      within(dialog).getByText(
        "Strong application support fit.",
      ),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText(
        "Spain-compatible employment.",
      ),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByText("eligible"),
    ).toBeInTheDocument();

    expect(
      fetchMock,
    ).toHaveBeenCalledTimes(1);
  });

  it("shows a hardline rejection before fit and suppresses misleading fit scores", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse([hardlineRejectedOpportunity]),
    );

    render(<App />);

    expect(
      await screen.findByText("Technical Support Engineer L2"),
    ).toBeInTheDocument();

    expect(
      screen.getAllByText("Required condition not met").length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      await screen.findByText("US-only remote: applicants must be anywhere in the US."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Fit score not shown because a required condition was not met."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Technical fit 95/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Technical fit 91/i)).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Inspect" }),
    );

    expect(
      screen.getAllByText("Required condition not met").length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("Fit score not shown because a required condition was not met.").length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Technical fit")).not.toBeInTheDocument();
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

    fireEvent.click(
      within(
        screen.getByLabelText(
          "Actions for Application Support Engineer",
        ),
      ).getByRole("button", { name: "Apply" }),
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
      "ready in Applications",
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

    const actions = screen.getByLabelText(
      "Actions for Cloud Operations Analyst",
    );

    expect(
      within(actions).getByRole("button", { name: "Apply" }),
    ).toBeDisabled();
    expect(
      within(actions).getByRole("button", { name: "Reject" }),
    ).toBeDisabled();
  });

  it("keeps Review Inbox decisions to Apply or Reject and labels AI filters clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse([reviewedOpportunity]),
    );

    render(<App />);

    await screen.findByText("Application Support Engineer");

    const actions = screen.getByLabelText(
      "Actions for Application Support Engineer",
    );
    expect(within(actions).getByRole("button", { name: "Apply" })).toBeInTheDocument();
    expect(within(actions).getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(screen.queryByText("Maybe")).not.toBeInTheDocument();
    expect(screen.queryByText("Save for later")).not.toBeInTheDocument();
    expect(screen.queryByText("Need information")).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: /High priority/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Good match/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Check/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Not a match/ })).toBeInTheDocument();
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

    fireEvent.click(await screen.findByText("Maintenance"));
    fireEvent.click(
      screen.getByRole(
        "button",
        {
          name: "Clear unresolved inbox (1)",
        },
      ),
    );

    expect(
      await screen.findByText(
        /1 pending card cleared from 1 search run/,
      ),
    ).toBeInTheDocument();
  });

  it("moves focus into the inspector and restores it when Escape closes the dialog", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse([reviewedOpportunity]),
    );

    render(<App />);

    await screen.findByText("Application Support Engineer");
    const inspect = screen.getByRole("button", { name: "Inspect" });
    inspect.focus();
    fireEvent.click(inspect);

    const dialog = await screen.findByRole("dialog", {
      name: "Application Support Engineer",
    });
    const close = screen.getByRole("button", { name: "Close" });

    await waitFor(() => expect(close).toHaveFocus());
    expect(dialog).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Application Support Engineer" }),
      ).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(inspect).toHaveFocus());
  });

});
