import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkedInSearchPortfolio } from "./LinkedInSearchPortfolio";

const savedSearches = [
  {
    id: "s1",
    label: "LinkedIn IT Support",
    search_url: "https://www.linkedin.com/jobs/search/?keywords=IT+Support",
    notes: "",
    enabled: true,
    max_jobs: 100,
    max_pages: 10,
    created_at: "2026-09-23T00:00:00Z",
    updated_at: "2026-09-23T00:00:00Z",
  },
  {
    id: "s2",
    label: "LinkedIn Application Support",
    search_url: "https://www.linkedin.com/jobs/search/?keywords=Application+Support",
    notes: "",
    enabled: true,
    max_jobs: 100,
    max_pages: 10,
    created_at: "2026-09-23T00:00:00Z",
    updated_at: "2026-09-23T00:00:00Z",
  },
];

describe("LinkedInSearchPortfolio", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("starts one discovery batch for the selected saved searches", async () => {
    const calls: Array<{ url: string; method: string; body?: unknown }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      calls.push({
        url,
        method,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });

      if (url.endsWith("/api/linkedin-searches")) {
        return new Response(JSON.stringify(savedSearches), { status: 200 });
      }
      if (url.endsWith("/api/linkedin-discovery-batches") && method === "GET") {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/api/linkedin-discovery-batches") && method === "POST") {
        return new Response(JSON.stringify({
          id: "b1",
          status: "queued",
          selected_search_count: 2,
          completed_search_count: 0,
          failed_search_count: 0,
          captured_count: 0,
          verified_count: 0,
          new_posting_count: 0,
          duplicate_count: 0,
          started_at: null,
          completed_at: null,
          created_at: "2026-09-23T00:00:00Z",
          searches: [],
        }), { status: 200 });
      }
      if (url.endsWith("/api/linkedin-discovery-batches/b1/start")) {
        return new Response(JSON.stringify({
          id: "b1",
          status: "scheduled",
          selected_search_count: 2,
          completed_search_count: 0,
          failed_search_count: 0,
          captured_count: 0,
          verified_count: 0,
          new_posting_count: 0,
          duplicate_count: 0,
          started_at: null,
          completed_at: null,
          created_at: "2026-09-23T00:00:00Z",
          searches: [],
        }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    });

    render(<LinkedInSearchPortfolio apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByText("LinkedIn IT Support")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Select enabled" }));
    fireEvent.click(screen.getByRole("button", { name: "Start discovery (2)" }));

    await waitFor(() => {
      expect(calls).toContainEqual({
        url: "http://127.0.0.1:8000/api/linkedin-discovery-batches",
        method: "POST",
        body: { saved_search_ids: ["s1", "s2"] },
      });
      expect(calls.some((call) => call.url.endsWith("/b1/start") && call.method === "POST")).toBe(true);
    });
  });

  it("edits a saved search from its actions menu", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/linkedin-searches") && method === "GET") {
        return new Response(JSON.stringify(savedSearches), { status: 200 });
      }
      if (url.endsWith("/api/linkedin-discovery-batches")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/api/linkedin-searches/s1") && method === "POST") {
        return new Response(JSON.stringify({
          ...savedSearches[0],
          label: "LinkedIn IT Support EU",
        }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    });

    render(<LinkedInSearchPortfolio apiBase="http://127.0.0.1:8000" active />);
    expect(await screen.findByText("LinkedIn IT Support")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Actions for LinkedIn IT Support"));
    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    const name = screen.getByLabelText("Name");
    fireEvent.change(name, { target: { value: "LinkedIn IT Support EU" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText("Saved search updated.")).toBeInTheDocument());
  });
});


it("keeps retired searches out of the primary list and collapses search URLs", async () => {
  const retiredSearch = {
    id: "s3",
    label: "Acceptance - LinkedIn IT Support",
    search_url: "https://www.linkedin.com/jobs/search/?keywords=Acceptance",
    notes: "Historical acceptance search",
    enabled: false,
    max_jobs: 25,
    max_pages: 3,
    created_at: "2026-09-23T00:00:00Z",
    updated_at: "2026-09-23T00:00:00Z",
  };

  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/linkedin-searches")) {
      return new Response(JSON.stringify([...savedSearches, retiredSearch]), { status: 200 });
    }
    if (url.endsWith("/api/linkedin-discovery-batches")) {
      return new Response(JSON.stringify([]), { status: 200 });
    }
    throw new Error(`Unexpected request: GET ${url}`);
  });

  render(<LinkedInSearchPortfolio apiBase="http://127.0.0.1:8000" active />);

  expect(await screen.findByText("LinkedIn IT Support")).toBeInTheDocument();
  expect(screen.getByText("Retired searches (1)")).toBeInTheDocument();
  expect(screen.getAllByText("Search URL")).toHaveLength(3);
  expect(screen.queryByText("https://www.linkedin.com/jobs/search/?keywords=IT+Support")).not.toBeInTheDocument();
});


it("keeps critical discovery controls visible when search and batch lists are long", async () => {
  const manySearches = Array.from({ length: 21 }, (_, index) => ({
    id: `s${index + 1}`,
    label: `Saved search ${index + 1}`,
    search_url: `https://www.linkedin.com/jobs/search/?keywords=Search+${index + 1}`,
    notes: "",
    enabled: true,
    max_jobs: 50,
    max_pages: 5,
    created_at: "2026-09-25T00:00:00Z",
    updated_at: "2026-09-25T00:00:00Z",
  }));

  const batchSearches = manySearches.map((search, index) => ({
    id: `bs${index + 1}`,
    saved_search_id: search.id,
    position: index + 1,
    label: search.label,
    search_url: search.search_url,
    max_jobs: 50,
    max_pages: 5,
    status: "completed",
    capture_run_id: `c${index + 1}`,
    captured_count: 50,
    verified_count: 50,
    new_posting_count: 10,
    duplicate_count: 40,
    error: "",
    started_at: "2026-09-25T00:00:00Z",
    completed_at: "2026-09-25T01:00:00Z",
  }));

  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/linkedin-searches")) {
      return new Response(JSON.stringify(manySearches), { status: 200 });
    }
    if (url.endsWith("/api/linkedin-discovery-batches")) {
      return new Response(JSON.stringify([{
        id: "b-long",
        status: "completed",
        selected_search_count: 21,
        completed_search_count: 21,
        failed_search_count: 0,
        captured_count: 1050,
        verified_count: 1050,
        new_posting_count: 210,
        duplicate_count: 840,
        started_at: "2026-09-25T00:00:00Z",
        completed_at: "2026-09-25T01:00:00Z",
        created_at: "2026-09-25T00:00:00Z",
        searches: batchSearches,
      }]), { status: 200 });
    }
    throw new Error(`Unexpected request: GET ${url}`);
  });

  const { container } = render(
    <LinkedInSearchPortfolio apiBase="http://127.0.0.1:8000" active />,
  );

  expect(await screen.findByText("Saved searches (21)")).toBeInTheDocument();
  expect(screen.getByText("Download this discovery batch for AI review")).toBeInTheDocument();
  expect(screen.getByText("Import returned AI review")).toBeInTheDocument();

  const activeDetails = container.querySelector(".active-searches-details");
  const batchDetails = container.querySelector(".batch-search-details");
  expect(activeDetails).not.toHaveAttribute("open");
  expect(batchDetails).not.toHaveAttribute("open");
});

it("keeps live batch progress expanded while discovery is running", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/linkedin-searches")) {
      return new Response(JSON.stringify(savedSearches), { status: 200 });
    }
    if (url.endsWith("/api/linkedin-discovery-batches")) {
      return new Response(JSON.stringify([{
        id: "b-live",
        status: "running",
        selected_search_count: 2,
        completed_search_count: 1,
        failed_search_count: 0,
        captured_count: 50,
        verified_count: 50,
        new_posting_count: 20,
        duplicate_count: 30,
        started_at: "2026-09-25T00:00:00Z",
        completed_at: null,
        created_at: "2026-09-25T00:00:00Z",
        searches: [],
      }]), { status: 200 });
    }
    if (url.endsWith("/api/linkedin-discovery-batches/b-live")) {
      return new Response(JSON.stringify({
        id: "b-live",
        status: "running",
        selected_search_count: 2,
        completed_search_count: 1,
        failed_search_count: 0,
        captured_count: 50,
        verified_count: 50,
        new_posting_count: 20,
        duplicate_count: 30,
        started_at: "2026-09-25T00:00:00Z",
        completed_at: null,
        created_at: "2026-09-25T00:00:00Z",
        searches: [],
      }), { status: 200 });
    }
    throw new Error(`Unexpected request: GET ${url}`);
  });

  const { container, unmount } = render(
    <LinkedInSearchPortfolio apiBase="http://127.0.0.1:8000" active />,
  );

  expect(await screen.findByText("Search-by-search details (0)")).toBeInTheDocument();
  expect(container.querySelector(".batch-search-details")).toHaveAttribute("open");
  unmount();
});
