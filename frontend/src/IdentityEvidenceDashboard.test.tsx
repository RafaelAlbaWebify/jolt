import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IdentityEvidenceDashboard } from "./IdentityEvidenceDashboard";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("IdentityEvidenceDashboard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows canonical and duplicate source evidence without raw payloads", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/opportunities")) {
        return jsonResponse([{
          posting_id: "posting-1",
          title: "Application Support Engineer",
          company: "Example Systems",
          location: "Remote Spain",
        }]);
      }
      if (url.endsWith("/api/opportunities/posting-1/identity-evidence")) {
        return jsonResponse({
          posting_id: "posting-1",
          canonical_url: "https://www.linkedin.com/jobs/view/123",
          identity_status: "new",
          evidence_count: 2,
          duplicate_evidence_count: 1,
          evidence: [
            {
              source_document_id: "source-1",
              source_type: "linkedin_live",
              source_url: "https://www.linkedin.com/jobs/view/123",
              identity_status: "original",
              match_basis: "canonical_url",
              captured_at: "2026-07-14T10:00:00+00:00",
            },
            {
              source_document_id: "source-2",
              source_type: "manual",
              source_url: "https://www.linkedin.com/jobs/view/123?trk=duplicate",
              identity_status: "confirmed_duplicate",
              match_basis: "canonical_url",
              captured_at: "2026-07-14T11:00:00+00:00",
            },
          ],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<IdentityEvidenceDashboard apiBase="http://127.0.0.1:8000" />);

    expect(await screen.findByRole("heading", { name: "Application Support Engineer" })).toBeInTheDocument();
    expect(screen.getByText("2 source documents · 1 confirmed duplicate")).toBeInTheDocument();
    expect(screen.getByText("duplicate evidence")).toBeInTheDocument();
    expect(screen.getByText("Inspect identity evidence")).toBeInTheDocument();
  });
});
