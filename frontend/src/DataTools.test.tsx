import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTools } from "./DataTools";

describe("DataTools", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("offers the unified JOLT Review Pack for ChatGPT auditing", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    render(<DataTools apiBase="http://127.0.0.1:8000" />);

    const link = screen.getByRole("link", {
      name: "Download review pack",
    });

    expect(link).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/exports/review-pack",
    );
    expect(link).toHaveAttribute(
      "download",
      "JOLT_REVIEW_PACK.zip",
    );
  });
});
