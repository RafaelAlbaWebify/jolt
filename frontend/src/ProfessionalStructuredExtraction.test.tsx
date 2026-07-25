import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalStructuredExtraction } from "./ProfessionalStructuredExtraction";

const extraction = {
  capture_run_id: "run-1",
  extraction_method: "deterministic_bounded_v1",
  integrity_verified: true,
  role_signals: [
    {
      value: "Application Support",
      source_id: "linkedin-profile",
      supporting_snippet: "Interested in remote Application Support opportunities.",
      confidence: "explicit_match",
      extraction_method: "deterministic_term_match",
    },
  ],
  location_signals: [],
  skills: [
    {
      value: "PowerShell",
      source_id: "linkedin-profile",
      supporting_snippet: "Experience with PowerShell and Azure.",
      confidence: "explicit_match",
      extraction_method: "deterministic_term_match",
    },
  ],
  certifications: [],
  employers: [],
  job_interest_keywords: [],
};

describe("ProfessionalStructuredExtraction", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows explicit signals with source and supporting snippet", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(extraction), { status: 200 }),
    );

    render(<ProfessionalStructuredExtraction apiBase="http://127.0.0.1:8000" runId="run-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Build structured extraction" }));

    expect(await screen.findByText("Integrity-verified deterministic extraction")).toBeInTheDocument();
    expect(screen.getByText("Application Support")).toBeInTheDocument();
    expect(screen.getByText("PowerShell")).toBeInTheDocument();
    expect(screen.getAllByText(/linkedin-profile · explicit match/)).toHaveLength(2);
    expect(screen.getByText("Interested in remote Application Support opportunities.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/capture-runs/run-1/structured-extraction",
    );
  });
});
