import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalIntelligence } from "./ProfessionalIntelligence";

const sources = [
  {
    source_id: "linkedin-profile",
    label: "Main profile",
    category: "profile",
    url: "https://www.linkedin.com/in/rafael-alba-tech/",
    initial_scope: true,
    capture_mode: "supervised_read_only",
  },
  {
    source_id: "linkedin-feed",
    label: "Feed",
    category: "network",
    url: "https://www.linkedin.com/feed/",
    initial_scope: false,
    capture_mode: "supervised_read_only",
  },
];

describe("ProfessionalIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads only when active and separates initial from deferred sources", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(sources), { status: 200 }),
    );

    const { rerender } = render(
      <ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active={false} />,
    );
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByText("Main profile")).toBeInTheDocument();
    expect(screen.getByText("Feed")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Initial supervised scope" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Deferred sources" })).toBeInTheDocument();
    expect(screen.getByText(/No login handling/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open approved source" })).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/professional-intelligence/sources",
    );
  });
});
