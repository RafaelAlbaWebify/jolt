import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createPortal } from "react-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./App", () => ({
  App: ({ sidebarToolsTarget }: { sidebarToolsTarget?: HTMLDivElement | null }) => (
    <>
      <section>Opportunity review content</section>
      {sidebarToolsTarget
        ? createPortal(
            <details>
              <summary>Intake, captures, and exports</summary>
            </details>,
            sidebarToolsTarget,
          )
        : null}
    </>
  ),
}));

vi.mock("./ApplicationDashboard", () => ({
  ApplicationDashboard: () => <section>Application tracking content</section>,
}));

vi.mock("./MarketIntelligence", () => ({
  MarketIntelligence: () => <section>Market intelligence content</section>,
}));

vi.mock("./ProfessionalIntelligence", () => ({
  ProfessionalIntelligence: () => <section>Professional intelligence content</section>,
}));

import { Workbench } from "./Workbench";

describe("Workbench", () => {
  afterEach(() => cleanup());

  it("renders persistent navigation beside the active workspace", () => {
    render(<Workbench />);

    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    const workspace = screen.getByRole("main");

    expect(sidebar).toContainElement(screen.getByRole("heading", { name: "JOLT" }));
    expect(sidebar).toContainElement(screen.getByRole("navigation", { name: "JOLT workspace views" }));
    expect(sidebar).toHaveTextContent("Review, prioritise, and prepare opportunities.");
    expect(sidebar).toContainElement(screen.getByText("Intake, captures, and exports"));
    expect(workspace).toContainElement(screen.getByText("Opportunity review content"));
  });

  it("keeps workspaces mounted while showing one primary view", () => {
    render(<Workbench />);

    const opportunities = screen.getByText("Opportunity review content").parentElement;
    const applications = screen.getByText("Application tracking content").parentElement;
    const market = screen.getByText("Market intelligence content").parentElement;
    const professional = screen.getByText("Professional intelligence content").parentElement;

    expect(opportunities).not.toHaveAttribute("hidden");
    expect(applications).toHaveAttribute("hidden");
    expect(market).toHaveAttribute("hidden");
    expect(professional).toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Applications" }));
    expect(opportunities).toHaveAttribute("hidden");
    expect(applications).not.toHaveAttribute("hidden");
    expect(screen.queryByText("Intake, captures, and exports")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Market" }));
    expect(applications).toHaveAttribute("hidden");
    expect(market).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Professional" }));
    expect(market).toHaveAttribute("hidden");
    expect(professional).not.toHaveAttribute("hidden");
  });

  it("shows persistent navigation and updates its active description", () => {
    render(<Workbench />);

    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    expect(sidebar).toHaveTextContent("Job Opportunity Learning & Tracking");
    expect(sidebar).toHaveTextContent("Review, prioritise, and prepare opportunities.");
    expect(screen.getByRole("button", { name: "Opportunities" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Professional" }));
    expect(screen.getByRole("button", { name: "Professional" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Opportunities" })).toHaveAttribute("aria-pressed", "false");
    expect(sidebar).toHaveTextContent("Review approved professional sources and supervised evidence boundaries.");
  });
});
