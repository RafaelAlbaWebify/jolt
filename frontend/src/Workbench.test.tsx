import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./App", () => ({
  App: () => <section>Opportunity review content</section>,
}));

vi.mock("./ApplicationDashboard", () => ({
  ApplicationDashboard: () => <section>Application tracking content</section>,
}));

vi.mock("./IdentityEvidenceDashboard", () => ({
  IdentityEvidenceDashboard: () => <section>Identity evidence content</section>,
}));

import { Workbench } from "./Workbench";

describe("Workbench", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows one primary workspace view at a time", () => {
    render(<Workbench />);

    expect(screen.getByText("Opportunity review content")).toBeInTheDocument();
    expect(screen.queryByText("Application tracking content")).not.toBeInTheDocument();
    expect(screen.queryByText("Identity evidence content")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Applications" }));
    expect(screen.getByText("Application tracking content")).toBeInTheDocument();
    expect(screen.queryByText("Opportunity review content")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));
    expect(screen.getByText("Identity evidence content")).toBeInTheDocument();
    expect(screen.queryByText("Application tracking content")).not.toBeInTheDocument();
  });

  it("exposes the active view through accessible pressed state", () => {
    render(<Workbench />);

    expect(screen.getByRole("button", { name: "Opportunities" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: "Applications" }));

    expect(screen.getByRole("button", { name: "Applications" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Opportunities" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
