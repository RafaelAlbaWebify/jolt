import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalIntelligence } from "./ProfessionalIntelligence";

const sources = [
  {
    source_id: "linkedin-profile",
    label: "Main profile",
    category: "profile",
    url: "https://www.linkedin.com/in/rafael-alba-tech/",
    initial_scope: true,
    enabled: true,
    capture_mode: "supervised_read_only",
  },
  {
    source_id: "linkedin-feed",
    label: "Feed",
    category: "network",
    url: "https://www.linkedin.com/feed/",
    initial_scope: false,
    enabled: true,
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

  it("saves a supervised source override and resets the verified default", async () => {
    const updated = {
      ...sources[0],
      label: "Profile positioning review",
      url: "https://www.linkedin.com/in/rafael-alba-tech/?source=jolt",
      initial_scope: false,
      enabled: false,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (!init?.method) return new Response(JSON.stringify(sources), { status: 200 });
      if (url.endsWith("/linkedin-profile/update")) {
        expect(JSON.parse(String(init.body))).toEqual({
          label: "Profile positioning review",
          url: "https://www.linkedin.com/in/rafael-alba-tech/?source=jolt",
          initial_scope: false,
          enabled: false,
        });
        return new Response(JSON.stringify(updated), { status: 200 });
      }
      if (url.endsWith("/linkedin-profile/reset")) {
        return new Response(JSON.stringify(sources[0]), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ProfessionalIntelligence apiBase="http://127.0.0.1:8000" active />);
    const profileHeading = await screen.findByText("Main profile");
    const profileCard = profileHeading.closest("article");
    expect(profileCard).not.toBeNull();
    fireEvent.click(within(profileCard as HTMLElement).getByText("Edit approved source"));
    fireEvent.change(screen.getByLabelText("Source label for linkedin-profile"), {
      target: { value: "Profile positioning review" },
    });
    fireEvent.change(screen.getByLabelText("LinkedIn URL for linkedin-profile"), {
      target: { value: "https://www.linkedin.com/in/rafael-alba-tech/?source=jolt" },
    });
    fireEvent.click(screen.getByLabelText("Initial scope for linkedin-profile"));
    fireEvent.click(screen.getByLabelText("Enabled for linkedin-profile"));
    fireEvent.click(within(profileCard as HTMLElement).getByRole("button", { name: "Save source" }));

    expect(await screen.findByText("Profile positioning review")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const updatedCard = screen.getByText("Profile positioning review").closest("article");
    expect(updatedCard).not.toBeNull();
    fireEvent.click(within(updatedCard as HTMLElement).getByText("Edit approved source"));
    fireEvent.click(
      within(updatedCard as HTMLElement).getByRole("button", { name: "Reset verified default" }),
    );

    expect(await screen.findByText("Main profile")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
