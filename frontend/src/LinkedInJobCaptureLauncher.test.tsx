import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkedInJobCaptureLauncher } from "./LinkedInJobCaptureLauncher";

const idleStatus = {
  status: "idle",
  search_url: "",
  max_jobs: 0,
  max_pages: 0,
  export_format: "json",
  output_json: "",
  output_zip: "",
  started_at: "",
  completed_at: "",
  error: "",
};

describe("LinkedInJobCaptureLauncher", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("submits the exact search URL, multi-page limits, and recommended JSON export", async () => {
    const searchUrl = (
      "https://www.linkedin.com/jobs/search/?currentJobId=4434526277"
      + "&geoId=91000000&keywords=IT%20Support&refresh=true"
    );
    let submitted: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/status")) {
        return new Response(JSON.stringify(idleStatus), { status: 200 });
      }
      if (url.endsWith("/api/captures/linkedin/local") && init?.method === "POST") {
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
        return new Response(JSON.stringify({
          ...idleStatus,
          status: "queued",
          search_url: searchUrl,
          max_jobs: 20,
          max_pages: 4,
        }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);
    await screen.findByRole("button", { name: "Start LinkedIn job capture" });

    expect(screen.getByLabelText(/JSON — Recommended/)).toBeChecked();

    fireEvent.change(screen.getByLabelText("LinkedIn search URL"), {
      target: { value: searchUrl },
    });
    fireEvent.change(screen.getByLabelText("Maximum jobs"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("Maximum pages"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Start LinkedIn job capture" }));

    await waitFor(() => expect(submitted).toEqual({
      search_url: searchUrl,
      max_jobs: 20,
      max_pages: 4,
      export_format: "json",
    }));
    expect(await screen.findByText("Status: queued")).toBeInTheDocument();
    expect(screen.getByText("20 jobs maximum across 4 page(s).")).toBeInTheDocument();
  });

  it("supports ZIP-only and both-format capture exports", async () => {
    let submitted: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/status")) {
        return new Response(JSON.stringify(idleStatus), { status: 200 });
      }
      if (url.endsWith("/api/captures/linkedin/local") && init?.method === "POST") {
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
        return new Response(JSON.stringify({
          ...idleStatus,
          status: "queued",
          search_url: "https://www.linkedin.com/jobs/search/",
          max_jobs: 100,
          max_pages: 10,
          export_format: submitted?.export_format ?? "json",
        }), { status: 200 });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);
    await screen.findByRole("button", { name: "Start LinkedIn job capture" });

    fireEvent.click(screen.getByLabelText(/ZIP — Full archive/));
    fireEvent.click(screen.getByRole("button", { name: "Start LinkedIn job capture" }));
    await waitFor(() => expect(submitted?.export_format).toBe("zip"));

    cleanup();
    submitted = null;
    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);
    await screen.findByRole("button", { name: "Start LinkedIn job capture" });
    expect(screen.getByLabelText(/ZIP — Full archive/)).toBeChecked();

    fireEvent.click(screen.getByLabelText("Also create the other format"));
    fireEvent.click(screen.getByRole("button", { name: "Start LinkedIn job capture" }));
    await waitFor(() => expect(submitted?.export_format).toBe("both"));
  });

  it("renders the completed export paths for the chosen format", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      ...idleStatus,
      status: "completed",
      max_jobs: 100,
      max_pages: 10,
      export_format: "json",
      output_json: "C:\\Users\\user\\Downloads\\JOLT_LINKEDIN_CAPTURE_20260901_050000.json",
      captured_count: 100,
      verified_count: 100,
      health: "green",
    }), { status: 200 }));

    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);

    expect(await screen.findByText(
      "Capture completed. The structured JSON working export was saved to Downloads.",
    )).toBeInTheDocument();
    expect(screen.getByText(/JOLT_LINKEDIN_CAPTURE_20260901_050000\.json/)).toBeInTheDocument();
  });

  it("never submits more than 100 jobs", async () => {
    let submitted: Record<string, unknown> | null = null;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return new Response(JSON.stringify(idleStatus), { status: 200 });
      }

      if (url.endsWith("/api/captures/linkedin/local") && init?.method === "POST") {
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;

        return new Response(JSON.stringify({
          ...idleStatus,
          status: "queued",
          search_url: "https://www.linkedin.com/jobs/search/",
          max_jobs: 100,
          max_pages: 10,
        }), { status: 200 });
      }

      throw new Error(`Unexpected request: ${url}`);
    });

    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);

    await screen.findByRole("button", {
      name: "Start LinkedIn job capture",
    });

    const jobsInput = screen.getByLabelText(
      "Maximum jobs",
    ) as HTMLInputElement;

    expect(jobsInput.max).toBe("100");
    expect(jobsInput.value).toBe("100");

    const pagesInput = screen.getByLabelText(
      "Maximum pages",
    ) as HTMLInputElement;

    expect(pagesInput.max).toBe("10");
    expect(pagesInput.value).toBe("10");

    fireEvent.change(jobsInput, {
      target: { value: "150" },
    });

    expect(jobsInput.value).toBe("100");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Start LinkedIn job capture",
      }),
    );

    await waitFor(() => {
      expect(submitted).toEqual({
        search_url: "https://www.linkedin.com/jobs/search/",
        max_jobs: 100,
        max_pages: 10,
        export_format: "json",
      });
    });
  });

  it("renders FastAPI validation details as readable field messages", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return new Response(JSON.stringify(idleStatus), { status: 200 });
      }

      if (url.endsWith("/api/captures/linkedin/local") && init?.method === "POST") {
        return new Response(JSON.stringify({
          detail: [
            {
              type: "less_than_equal",
              loc: ["body", "max_jobs"],
              msg: "Input should be less than or equal to 100",
              input: 101,
              ctx: { le: 100 },
            },
          ],
        }), {
          status: 422,
          headers: {
            "Content-Type": "application/json",
          },
        });
      }

      throw new Error(`Unexpected request: ${url}`);
    });

    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);

    await screen.findByRole("button", {
      name: "Start LinkedIn job capture",
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Start LinkedIn job capture",
      }),
    );

    expect(
      await screen.findByText(
        "max_jobs: Input should be less than or equal to 100",
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("[object Object]"),
    ).not.toBeInTheDocument();
  });
});