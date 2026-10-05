import { fireEvent, render, screen, within } from "@testing-library/react";
import { vi } from "vitest";

import { DiscoverySearchQueue } from "./DiscoverySearchQueue";

const sources = [
  { source: "linkedin", label: "LinkedIn", transport: "browser", saved_search_backend: "legacy_linkedin", execution_available: true },
  { source: "indeed", label: "Indeed", transport: "browser", saved_search_backend: "discovery", execution_available: false },
  { source: "jobgether", label: "Jobgether", transport: "api", saved_search_backend: "discovery", execution_available: false },
];

const searches = [
  {
    id: "li-1",
    source: "linkedin",
    label: "IT Operations Engineer - EU Remote",
    definition: { search_url: "https://www.linkedin.com/jobs/search/?keywords=IT+Operations", max_pages: 5 },
    notes: "",
    enabled: true,
    max_jobs: 50,
    created_at: "2026-10-05T00:00:00Z",
    updated_at: "2026-10-05T00:00:00Z",
    execution_available: true,
  },
  {
    id: "in-1",
    source: "indeed",
    label: "Application Support - Spain",
    definition: { search_url: "https://es.indeed.com/jobs?q=application+support" },
    notes: "",
    enabled: true,
    max_jobs: 50,
    created_at: "2026-10-05T00:00:00Z",
    updated_at: "2026-10-05T00:00:00Z",
    execution_available: false,
  },
];

it("shows portal-specific searches and lets the user build an execution order", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/discovery-sources")) {
      return new Response(JSON.stringify(sources), { status: 200 });
    }
    if (url.endsWith("/api/discovery-searches")) {
      return new Response(JSON.stringify(searches), { status: 200 });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<DiscoverySearchQueue apiBase="http://127.0.0.1:8000" active />);

  expect(await screen.findByText("IT Operations Engineer - EU Remote")).toBeInTheDocument();
  expect(screen.getByText("Application Support - Spain")).toBeInTheDocument();
  expect(screen.getByText("3 sources registered")).toBeInTheDocument();

  fireEvent.click(screen.getByLabelText("Select LinkedIn · IT Operations Engineer - EU Remote"));
  fireEvent.click(screen.getByLabelText("Select Indeed · Application Support - Spain"));

  const preview = screen.getByText("Execution order (2)").parentElement;
  expect(preview).not.toBeNull();
  const items = within(preview as HTMLElement).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("LinkedIn · IT Operations Engineer - EU Remote");
  expect(items[1]).toHaveTextContent("Indeed · Application Support - Spain");

  fireEvent.click(screen.getByLabelText("Move Application Support - Spain up"));
  const reordered = within(preview as HTMLElement).getAllByRole("listitem");
  expect(reordered[0]).toHaveTextContent("Indeed · Application Support - Spain");
  expect(reordered[1]).toHaveTextContent("LinkedIn · IT Operations Engineer - EU Remote");

  expect(screen.getByRole("button", { name: "Run discovery (2)" })).toBeDisabled();
});

it("filters saved searches by portal", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/discovery-sources")) {
      return new Response(JSON.stringify(sources), { status: 200 });
    }
    if (url.endsWith("/api/discovery-searches")) {
      return new Response(JSON.stringify(searches), { status: 200 });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<DiscoverySearchQueue apiBase="http://127.0.0.1:8000" active />);
  await screen.findByText("Application Support - Spain");

  fireEvent.change(screen.getByLabelText("Portal"), { target: { value: "indeed" } });

  expect(screen.queryByText("IT Operations Engineer - EU Remote")).not.toBeInTheDocument();
  expect(screen.getByText("Application Support - Spain")).toBeInTheDocument();
});
