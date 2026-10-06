import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { DiscoverySearchQueue } from "./DiscoverySearchQueue";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const sources = [
  { source: "linkedin", label: "LinkedIn", transport: "browser", saved_search_backend: "legacy_linkedin", execution_available: true },
  { source: "indeed", label: "Indeed", transport: "browser", saved_search_backend: "discovery", execution_available: true },
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
    execution_available: true,
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

  expect(screen.getByRole("button", { name: "Run discovery (2)" })).toBeEnabled();
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


it("creates an Indeed search from the unified editor", async () => {
  let listed = searches.filter((item) => item.source !== "indeed");
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/api/discovery-sources")) {
      return new Response(JSON.stringify(sources), { status: 200 });
    }
    if (url.endsWith("/api/discovery-searches") && (!init?.method || init.method === "GET")) {
      return new Response(JSON.stringify(listed), { status: 200 });
    }
    if (url.endsWith("/api/discovery-searches") && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      expect(body.source).toBe("indeed");
      expect(body.definition.search_url).toBe("https://es.indeed.com/jobs?q=application+support");
      expect(body.definition.max_pages).toBe(3);
      listed = [
        ...listed,
        {
          id: "indeed-new",
          source: "indeed",
          label: body.label,
          definition: body.definition,
          notes: body.notes,
          enabled: body.enabled,
          max_jobs: body.max_jobs,
          created_at: "2026-10-06T00:00:00Z",
          updated_at: "2026-10-06T00:00:00Z",
          execution_available: false,
        },
      ];
      return new Response(JSON.stringify(listed.at(-1)), { status: 200 });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<DiscoverySearchQueue apiBase="http://127.0.0.1:8000" active />);
  await screen.findByText("IT Operations Engineer - EU Remote");

  fireEvent.change(screen.getByLabelText("Portal"), { target: { value: "indeed" } });
  fireEvent.click(screen.getByRole("button", { name: "Add Indeed search" }));

  const dialog = screen.getByRole("dialog", { name: "Add discovery search" });
  fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Indeed Application Support Spain" } });
  fireEvent.change(within(dialog).getByLabelText("Indeed search URL"), { target: { value: "https://es.indeed.com/jobs?q=application+support" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Save search" }));

  await waitFor(() => {
    expect(screen.getByText("Indeed Application Support Spain")).toBeInTheDocument();
  });
  expect(fetchMock).toHaveBeenCalled();
});


it("runs LinkedIn then Indeed in the selected order", async () => {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/api/discovery-sources")) {
      return new Response(JSON.stringify(sources), { status: 200 });
    }
    if (url.endsWith("/api/discovery-searches") && (!init?.method || init.method === "GET")) {
      return new Response(JSON.stringify(searches), { status: 200 });
    }
    if (url.endsWith("/api/linkedin-discovery-batches") && init?.method === "POST") {
      calls.push("linkedin:create");
      return new Response(JSON.stringify({ id: "linkedin-batch", status: "queued" }), { status: 200 });
    }
    if (url.endsWith("/api/linkedin-discovery-batches/linkedin-batch/start")) {
      calls.push("linkedin:start");
      return new Response(JSON.stringify({ id: "linkedin-batch", status: "scheduled" }), { status: 200 });
    }
    if (url.endsWith("/api/linkedin-discovery-batches/linkedin-batch")) {
      calls.push("linkedin:complete");
      return new Response(JSON.stringify({ id: "linkedin-batch", status: "completed" }), { status: 200 });
    }
    if (url.endsWith("/api/discovery-executions") && init?.method === "POST") {
      calls.push("indeed:create");
      return new Response(JSON.stringify({
        id: "indeed-execution",
        status: "queued",
        error: "",
        capture_run_id: null,
      }), { status: 200 });
    }
    if (url.endsWith("/api/discovery-executions/indeed-execution")) {
      calls.push("indeed:complete");
      return new Response(JSON.stringify({
        id: "indeed-execution",
        status: "completed",
        error: "",
        capture_run_id: "capture-1",
      }), { status: 200 });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<DiscoverySearchQueue apiBase="http://127.0.0.1:8000" active />);
  await screen.findByText("IT Operations Engineer - EU Remote");

  fireEvent.click(screen.getByLabelText("Select LinkedIn · IT Operations Engineer - EU Remote"));
  fireEvent.click(screen.getByLabelText("Select Indeed · Application Support - Spain"));
  fireEvent.click(screen.getByRole("button", { name: "Run discovery (2)" }));

  await waitFor(() => {
    expect(screen.getByText("Discovery completed in the requested order: 2 searches.")).toBeInTheDocument();
  });

  expect(calls).toEqual([
    "linkedin:create",
    "linkedin:start",
    "linkedin:complete",
    "indeed:create",
    "indeed:complete",
  ]);
});


it("shows the live Indeed phase while a capture is running", async () => {
  let executionPolls = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/api/discovery-sources")) {
      return new Response(JSON.stringify(sources), { status: 200 });
    }
    if (url.endsWith("/api/discovery-searches") && (!init?.method || init.method === "GET")) {
      return new Response(JSON.stringify([searches[1]]), { status: 200 });
    }
    if (url.endsWith("/api/discovery-executions") && init?.method === "POST") {
      return new Response(JSON.stringify({
        id: "indeed-phase",
        status: "queued",
        error: "",
        capture_run_id: null,
      }), { status: 200 });
    }
    if (url.endsWith("/api/discovery-executions/indeed-phase")) {
      executionPolls += 1;
      if (executionPolls === 1) {
        return new Response(JSON.stringify({
          id: "indeed-phase",
          status: "waiting_results",
          error: "",
          capture_run_id: null,
        }), { status: 200 });
      }
      return new Response(JSON.stringify({
        id: "indeed-phase",
        status: "completed",
        error: "",
        capture_run_id: "capture-phase",
      }), { status: 200 });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<DiscoverySearchQueue apiBase="http://127.0.0.1:8000" active />);
  await screen.findByText("Application Support - Spain");

  fireEvent.click(screen.getByLabelText("Select Indeed · Application Support - Spain"));
  fireEvent.click(screen.getByRole("button", { name: "Run discovery (1)" }));

  expect(await screen.findByText(/Waiting for visible Indeed results/)).toBeInTheDocument();
  expect(await screen.findByText("Discovery completed in the requested order: 1 search.")).toBeInTheDocument();
});
