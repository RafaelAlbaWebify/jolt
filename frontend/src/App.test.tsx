import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const opportunity = {
  posting_id: "posting-1",
  title: "Application Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",
  recommendation: "pursue",
  ranking_score: 83,
  review_decision: null,
};

describe("App", () => {
  afterEach(() => vi.restoreAllMocks());

  it("submits a manual opportunity and records a human review", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        posting_id: "posting-1",
        evaluation_id: "evaluation-1",
        identity_status: "new",
        title: opportunity.title,
        company: opportunity.company,
        location: opportunity.location,
        recommendation: "pursue",
        confidence: "medium",
        ranking_score: 83,
        reasons: ["Relevant signals found."],
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([opportunity]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        review_id: "review-1",
        posting_id: "posting-1",
        evaluation_id: "evaluation-1",
        decision: "pursue",
        evaluation_overridden: false,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ ...opportunity, review_decision: "pursue" }]), { status: 200 }));

    render(<App />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText("Job text"), {
      target: { value: "Application Support Engineer\nExample Systems\nLocation: Remote Spain" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Evaluate opportunity" }));

    expect(await screen.findByRole("heading", { name: opportunity.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Rule score 83 · medium confidence")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "pursue" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    expect(await screen.findByText("pursue", { selector: ".queue-status strong" })).toBeInTheDocument();
  });

  it("shows an actionable API error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The JOLT API is not available.");
  });
});
