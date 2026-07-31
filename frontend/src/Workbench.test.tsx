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
  LinkedInCommandCenter: () => <section>LinkedIn command content</section>,
}));

vi.mock("./MarketIntelligence", () => ({
  MarketIntelligence: () => <section>Market intelligence content</section>,
}));

vi.mock("./ProfessionalIntelligence", () => ({
  ProfessionalIntelligence: () => <section>Capture and evidence content</section>,
}));

import { Workbench } from "./Workbench";

describe("Workbench", () => {
  afterEach(() => cleanup());

  it("renders persistent navigation and global data tools beside the active capture workspace", () => {
    render(<Workbench />);

    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    const workspace = screen.getByRole("main");

    expect(sidebar).toContainElement(screen.getByRole("heading", { name: "JOLT" }));
    expect(sidebar).toContainElement(screen.getByRole("navigation", { name: "JOLT workspace views" }));
    expect(sidebar).toHaveTextContent("Start supervised capture, store local evidence, and confirm how captured material routes through JOLT.");
    expect(screen.getByText("Data tools: capture batches, decisions, and exports")).toBeInTheDocument();
    expect(workspace).toContainElement(screen.getByText("Capture and evidence content"));
  });

  it("keeps workspaces mounted while showing one primary view", () => {
    render(<Workbench />);

    const professional = screen.getByText("Capture and evidence content").parentElement;
    const opportunities = screen.getByText("Opportunity review content").parentElement;
    const applications = screen.getByText("Application tracking content").parentElement;
    const linkedin = screen.getByText("LinkedIn command content").parentElement;
    const market = screen.getByText("Market intelligence content").parentElement;

    expect(professional).not.toHaveAttribute("hidden");
    expect(opportunities).toHaveAttribute("hidden");
    expect(applications).toHaveAttribute("hidden");
    expect(linkedin).toHaveAttribute("hidden");
    expect(market).toHaveAttribute("hidden");
    expect(screen.getByText("Data tools: capture batches, decisions, and exports")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Review Inbox" }));
    expect(professional).toHaveAttribute("hidden");
    expect(opportunities).not.toHaveAttribute("hidden");
    expect(screen.getByText("Data tools: capture batches, decisions, and exports")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Application Pipeline" }));
    expect(opportunities).toHaveAttribute("hidden");
    expect(applications).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn Command Center" }));
    expect(applications).toHaveAttribute("hidden");
    expect(linkedin).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Market Insights" }));
    expect(linkedin).toHaveAttribute("hidden");
    expect(market).not.toHaveAttribute("hidden");
  });

  it("shows persistent navigation and updates its active description", () => {
    render(<Workbench />);

    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    expect(sidebar).toHaveTextContent("Job Opportunity Learning & Tracking");
    expect(sidebar).toHaveTextContent("Start supervised capture, store local evidence, and confirm how captured material routes through JOLT.");
    expect(screen.getByRole("button", { name: "Capture & Evidence" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn Command Center" }));
    expect(screen.getByRole("button", { name: "LinkedIn Command Center" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Capture & Evidence" })).toHaveAttribute("aria-pressed", "false");
    expect(sidebar).toHaveTextContent("Improve profile positioning, network quality, activity, and outreach from user-approved LinkedIn evidence.");
  });
});
