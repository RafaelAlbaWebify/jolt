import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./App", () => ({
  App: () => <section>Opportunity review content</section>,
}));

vi.mock("./ApplicationDashboard", () => ({
  ApplicationDashboard: () => <section>Application tracking content</section>,
}));

vi.mock("./DataTools", () => ({
  DataTools: () => <details><summary>Data tools: capture batches, decisions, and exports</summary></details>,
}));

vi.mock("./LinkedInCommandCenter", () => ({
  LinkedInCommandCenter: () => <section>LinkedIn profile content</section>,
}));

vi.mock("./MarketIntelligence", () => ({
  MarketIntelligence: () => <section>Market intelligence content</section>,
}));

vi.mock("./ProfessionalIntelligence", () => ({
  ProfessionalIntelligence: () => <section>Job capture content</section>,
}));

import { Workbench } from "./Workbench";

describe("Workbench", () => {
  afterEach(() => cleanup());

  it("renders persistent navigation and global data tools beside the active job-capture workspace", () => {
    render(<Workbench />);

    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    const workspace = screen.getByRole("main");

    expect(sidebar).toContainElement(screen.getByRole("heading", { name: "JOLT" }));
    expect(sidebar).toContainElement(screen.getByRole("navigation", { name: "JOLT workspace views" }));
    expect(sidebar).toHaveTextContent("Capture LinkedIn job searches and send verified opportunities into JOLT.");
    expect(screen.getByText("Data tools: capture batches, decisions, and exports")).toBeInTheDocument();
    expect(workspace).toContainElement(screen.getByText("Job capture content"));
  });

  it("keeps workspaces mounted while showing one primary view", () => {
    render(<Workbench />);

    const professional = screen.getByText("Job capture content").parentElement;
    const opportunities = screen.getByText("Opportunity review content").parentElement;
    const applications = screen.getByText("Application tracking content").parentElement;
    const linkedin = screen.getByText("LinkedIn profile content").parentElement;
    const market = screen.getByText("Market intelligence content").parentElement;

    expect(professional).not.toHaveAttribute("hidden");
    expect(opportunities).toHaveAttribute("hidden");
    expect(applications).toHaveAttribute("hidden");
    expect(linkedin).toHaveAttribute("hidden");
    expect(market).toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Review Inbox" }));
    expect(professional).toHaveAttribute("hidden");
    expect(opportunities).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Applications" }));
    expect(opportunities).toHaveAttribute("hidden");
    expect(applications).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn Profile" }));
    expect(applications).toHaveAttribute("hidden");
    expect(linkedin).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Market Insights" }));
    expect(linkedin).toHaveAttribute("hidden");
    expect(market).not.toHaveAttribute("hidden");
  });

  it("shows the practical workflow and updates the active description", () => {
    render(<Workbench />);

    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    expect(sidebar).toHaveTextContent("Capture jobs");
    expect(sidebar).toHaveTextContent("Review opportunities");
    expect(sidebar).toHaveTextContent("Prepare and apply");
    expect(screen.getByRole("button", { name: "Capture Jobs" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn Profile" }));
    expect(screen.getByRole("button", { name: "LinkedIn Profile" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Capture Jobs" })).toHaveAttribute("aria-pressed", "false");
    expect(sidebar).toHaveTextContent("Capture and improve profile positioning, skills, activity, and professional presence.");
  });
});
