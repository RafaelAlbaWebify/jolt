import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the project foundation status", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "JOLT" })).toBeInTheDocument();
    expect(screen.getByTestId("foundation-status")).toHaveTextContent(
      "Foundation scaffold ready.",
    );
  });
});
