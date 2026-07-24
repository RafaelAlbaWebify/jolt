import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./App", () => ({
  App: () => <section>Opportunity review content</section>,
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

    fireEvent.click(screen.getByRole("button", { name: "Market" }));
    expect(applications).toHaveAttribute("hidden");
    expect(market).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Professional" }));
    expect(market).toHaveAttribute("hidden");
    expect(professional).not.toHaveAttribute("hidden");
  });

  it("exposes the active view through accessible pressed state", () => {
    render(<Workbench />);
    expect(screen.getByRole("button", { name: "Opportunities" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Professional" }));
    expect(screen.getByRole("button", { name: "Professional" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Opportunities" })).toHaveAttribute("aria-pressed", "false");
  });
});
