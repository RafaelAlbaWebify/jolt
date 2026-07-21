import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IdentityEvidenceDashboard } from "./IdentityEvidenceDashboard";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function evidence(postingId: string, duplicateCount: number) {
  return {
    posting_id: postingId,
    canonical_url: `https://www.linkedin.com/jobs/view/${postingId}`,
    identity_status: duplicateCount ? "confirmed_duplicate" : "new",
    evidence_count: duplicateCount + 1,
    duplicate_evidence_count: duplicateCount,
    evidence: [
      {
        source_document_id: `${postingId}-source-1`,
        source_type: "linkedin_live",
        source_url: `https://www.linkedin.com/jobs/view/${postingId}`,
        identity_status: "original",
        match_basis: "canonical_url",
        captured_at: "2026-07-14T10:00:00+00:00",
      },
    ],
  };
}

describe("IdentityEvidenceDashboard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads once, then summarises, filters, searches, and inspects identity evidence", async () => {
    const rows = [
      {
        opportunity: {
          posting_id: "posting-1",
          title: "Application Support Engineer",
          company: "Example Systems",
          location: "Remote Spain",
        },
        evidence: evidence("posting-1", 1),
      },
      {
        opportunity: {
          posting_id: "posting-2",
          title: "Cloud Support Engineer",
          company: "Beta Cloud",
          location: "Madrid",
        },
        evidence: evidence("posting-2", 0),
      },
    ];

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/identity-evidence")) return jsonResponse(rows);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<IdentityEvidenceDashboard apiBase="http://127.0.0.1:8000" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading identity evidence");
    expect(await screen.findByRole("heading", { name: "Application Support Engineer" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent("Identity evidence loaded for 2 opportunities.");
    expect(screen.getByRole("button", { name: "duplicates (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "single (1)" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "duplicates (1)" }));
    expect(screen.getByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Cloud Support Engineer")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "all (2)" }));
    fireEvent.change(screen.getByLabelText("Search evidence"), { target: { value: "Beta Cloud" } });
    expect(screen.getByText("Cloud Support Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Application Support Engineer")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search evidence"), { target: { value: "" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Inspect" })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Canonical source")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open source evidence" })).toBeInTheDocument();
  });
});
