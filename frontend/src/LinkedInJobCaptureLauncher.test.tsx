import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkedInJobCaptureLauncher } from "./LinkedInJobCaptureLauncher";

const idleStatus = {
  status: "idle",
  search_url: "",
  max_jobs: 0,
  max_pages: 0,
  output_zip: "",
  started_at: "",
  completed_at: "",
  error: "",
};

describe("LinkedInJobCaptureLauncher", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("submits the exact search URL and multi-page limits", async () => {
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
    }));
    expect(await screen.findByText("Status: queued")).toBeInTheDocument();
    expect(screen.getByText("20 jobs maximum across 4 page(s).")).toBeInTheDocument();
  });
  it("clamps maximum jobs to the backend limit before submission", async () => {
    let submitted: Record<string, unknown> | null = null;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/status")) {
        return new Response(JSON.stringify(idleStatus), { status: 200 });
      }
      if (url.endsWith("/api/captures/linkedin/local") && init?.method === "POST") {
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
        return new Response(
          JSON.stringify({
            ...idleStatus,
            status: "queued",
            max_jobs: 50,
            max_pages: 3,
          }),
          { status: 200 },
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);
    await screen.findByRole("button", { name: "Start LinkedIn job capture" });

    fireEvent.change(screen.getByLabelText("Maximum jobs"), {
      target: { value: "100" },
    });

    expect(screen.getByLabelText("Maximum jobs")).toHaveValue(50);

    fireEvent.click(
      screen.getByRole("button", { name: "Start LinkedIn job capture" }),
    );

    await waitFor(() =>
      expect(submitted).toMatchObject({
        max_jobs: 50,
        max_pages: 3,
      }),
    );
  });

  it("renders structured FastAPI validation details as readable text", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/status")) {
        return new Response(JSON.stringify(idleStatus), { status: 200 });
      }
      if (url.endsWith("/api/captures/linkedin/local") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            detail: [
              {
                loc: ["body", "max_jobs"],
                msg: "Input should be less than or equal to 50",
                type: "less_than_equal",
              },
            ],
          }),
          { status: 422 },
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<LinkedInJobCaptureLauncher apiBase="http://api" active />);
    await screen.findByRole("button", { name: "Start LinkedIn job capture" });

    fireEvent.click(
      screen.getByRole("button", { name: "Start LinkedIn job capture" }),
    );

    expect(
      await screen.findByText(
        "max_jobs: Input should be less than or equal to 50",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("[object Object]")).not.toBeInTheDocument();
  });

});
