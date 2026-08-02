import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./LinkedInJobCaptureLauncher", () => ({
  LinkedInJobCaptureLauncher: () => (
    <section>
      <h3>Capture a LinkedIn job search</h3>
      <button type="button">Start LinkedIn job capture</button>
    </section>
  ),
}));

import { ProfessionalIntelligence } from "./ProfessionalIntelligence";

describe("ProfessionalIntelligence", () => {
  afterEach(() => cleanup());

  it("keeps Capture Jobs focused on the proven job-search workflow", () => {
    render(<ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active />);

    expect(screen.getByRole("heading", { name: "Capture Jobs" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Capture a LinkedIn job search" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start LinkedIn job capture" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Profile capture has moved" })).toBeInTheDocument();
    expect(screen.getByText(/belong in LinkedIn Profile/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start configured-source capture" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Evidence directory" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Primary sources" })).not.toBeInTheDocument();
  });
});
