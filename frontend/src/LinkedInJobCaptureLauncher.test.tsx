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
});
