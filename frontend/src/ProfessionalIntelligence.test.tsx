import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./LinkedInSearchPortfolio", () => ({
  LinkedInSearchPortfolio: () => (
    <section>
      <h3>Run LinkedIn searches</h3>
      <button type="button">Run searches (2)</button>
    </section>
  ),
}));

vi.mock("./LinkedInJobCaptureLauncher", () => ({
  LinkedInJobCaptureLauncher: () => (
    <section>
      <h3>Run one LinkedIn search</h3>
      <button type="button">Run this search</button>
    </section>
  ),
}));

import { ProfessionalIntelligence } from "./ProfessionalIntelligence";

describe("ProfessionalIntelligence", () => {
  afterEach(() => cleanup());

  it("keeps Capture Jobs focused on the proven job-search workflow", () => {
    render(<ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active />);

    expect(screen.getByRole("heading", { name: "Capture Jobs" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Run LinkedIn searches" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run searches (2)" })).toBeInTheDocument();
    expect(screen.getByText("Run one LinkedIn search manually")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Run one LinkedIn search" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Profile capture has moved" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start configured-source capture" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Evidence directory" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Primary sources" })).not.toBeInTheDocument();
  });
});
