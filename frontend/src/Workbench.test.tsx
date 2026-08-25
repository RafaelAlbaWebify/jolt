import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./App", () => ({
  App: ({ evaluationRevision = 0 }: { evaluationRevision?: number }) => (
    <section>
      Opportunity review content revision {evaluationRevision}
    </section>
  ),
}));
vi.mock("./ApplicationDashboard", () => ({ ApplicationDashboard: () => <section>Application tracking content</section> }));
vi.mock("./DataTools", () => ({ DataTools: () => <section>Capture history, reviewed decisions, and exports</section> }));
vi.mock("./JobPreferences", () => ({
  JobPreferences: ({
    onEvaluationsRefreshed,
  }: {
    onEvaluationsRefreshed?: () => void;
  }) => (
    <section>
      <span>Job search preferences</span>
      <button
        type="button"
        onClick={() => onEvaluationsRefreshed?.()}
      >
        Apply preference refresh
      </button>
    </section>
  ),
}));
vi.mock("./LinkedInCommandCenter", () => ({ LinkedInCommandCenter: () => <section>LinkedIn profile content</section> }));
vi.mock("./MarketIntelligence", () => ({ MarketIntelligence: () => <section>Market intelligence content</section> }));
vi.mock("./ProfessionalIntelligence", () => ({ ProfessionalIntelligence: () => <section>Job capture content</section> }));
vi.mock("./RuntimeIdentity", () => ({ RuntimeIdentityPanel: () => <section>Developer diagnostics</section> }));

import { Workbench } from "./Workbench";

describe("Workbench", () => {
  afterEach(() => cleanup());

  it("keeps daily work in five primary views and moves utilities to Settings & Data", () => {
    render(<Workbench />);

    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    expect(sidebar).toContainElement(screen.getByRole("navigation", { name: "JOLT workspace views" }));
    expect(screen.getByRole("button", { name: "Capture Jobs" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review Inbox" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Applications" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "LinkedIn Profile" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Market Insights" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Settings & Data" })).toBeInTheDocument();
    expect(screen.queryByText("Capture history, reviewed decisions, and exports")).not.toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Settings & Data" }));
    expect(screen.getByRole("heading", { name: "Settings & Data" })).toBeInTheDocument();
    expect(screen.getByText("Capture history, reviewed decisions, and exports")).toBeVisible();
    expect(screen.getByText("Job search preferences")).toBeVisible();
    expect(screen.getByText("Developer diagnostics")).toBeVisible();
  });

  it("propagates preference re-evaluation to the mounted Review Inbox", () => {
    render(<Workbench />);

    fireEvent.click(
      screen.getByRole("button", { name: "Settings & Data" }),
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Apply preference refresh" }),
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Review Inbox" }),
    );

    expect(
      screen.getByText("Opportunity review content revision 1"),
    ).toBeVisible();
  });

  it("keeps workspaces mounted while showing one active view", () => {
    render(<Workbench />);

    const capture = screen.getByText("Job capture content").parentElement;
    const review = screen.getByText(/Opportunity review content revision/).parentElement;
    const applications = screen.getByText("Application tracking content").parentElement;
    const linkedin = screen.getByText("LinkedIn profile content").parentElement;
    const market = screen.getByText("Market intelligence content").parentElement;

    expect(capture).not.toHaveAttribute("hidden");
    expect(review).toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Review Inbox" }));
    expect(capture).toHaveAttribute("hidden");
    expect(review).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Applications" }));
    expect(applications).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn Profile" }));
    expect(linkedin).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "Market Insights" }));
    expect(market).not.toHaveAttribute("hidden");
  });

  it("shows the practical workflow and updates active descriptions", () => {
    render(<Workbench />);
    const sidebar = screen.getByRole("complementary", { name: "JOLT workspace navigation" });
    expect(sidebar).toHaveTextContent("Capture jobs");
    expect(sidebar).toHaveTextContent("Review opportunities");
    expect(sidebar).toHaveTextContent("Prepare and apply");

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn Profile" }));
    expect(sidebar).toHaveTextContent("Refresh profile evidence and manage concrete profile improvements.");
  });
});
