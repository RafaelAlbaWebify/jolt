import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationWorkflow } from "./ApplicationWorkflow";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), { status: 200 });
}

const application = {
  application_id: "application-1",
  posting_id: "posting-1",
  status: "technical_interview",
  application_url: "https://example.com/apply",
  resume_used: "support-cv.pdf",
  notes: "Prepared",
  outcome_type: null,
  events: [],
};

describe("ApplicationWorkflow", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("ignores a superseded application-history response", async () => {
    let resolveFirst: ((response: Response) => void) | undefined;
    let resolveSecond: ((response: Response) => void) | undefined;

    const firstResponse = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    const secondResponse = new Promise<Response>((resolve) => {
      resolveSecond = resolve;
    });

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input, init) => {
        const url = String(input);

        if (url.endsWith("/api/applications/application-1")) {
          expect(init?.signal).toBeInstanceOf(AbortSignal);
          return firstResponse;
        }

        if (url.endsWith("/api/applications/application-2")) {
          expect(init?.signal).toBeInstanceOf(AbortSignal);
          return secondResponse;
        }

        throw new Error(`Unexpected request: ${url}`);
      });

    const onError = vi.fn();
    const { rerender } = render(
      <ApplicationWorkflow
        apiBase="http://127.0.0.1:8000"
        postingId="posting-1"
        title="First role"
        reviewDecision="pursue"
        applicationId="application-1"
        applicationStatus="technical_interview"
        disabled={false}
        onChanged={async () => undefined}
        onError={onError}
      />,
    );

    fireEvent.click(screen.getByText(/Manage application/));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    rerender(
      <ApplicationWorkflow
        apiBase="http://127.0.0.1:8000"
        postingId="posting-2"
        title="Second role"
        reviewDecision="pursue"
        applicationId="application-2"
        applicationStatus="offer"
        disabled={false}
        onChanged={async () => undefined}
        onError={onError}
      />,
    );

    fireEvent.click(screen.getByText(/Manage application/));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    resolveSecond?.(
      jsonResponse({
        ...application,
        application_id: "application-2",
        posting_id: "posting-2",
        status: "offer",
        resume_used: "second-role-cv.pdf",
      }),
    );

    expect(await screen.findByText("second-role-cv.pdf")).toBeInTheDocument();

    resolveFirst?.(
      jsonResponse({
        ...application,
        application_id: "application-1",
        posting_id: "posting-1",
        status: "technical_interview",
        resume_used: "stale-first-role-cv.pdf",
      }),
    );

    await waitFor(() => {
      expect(screen.queryByText("stale-first-role-cv.pdf")).not.toBeInTheDocument();
      expect(screen.getByText("second-role-cv.pdf")).toBeInTheDocument();
    });
    expect(onError).not.toHaveBeenCalledWith("Application history failed.");
  });

  it("lets the user move an application back to an earlier stage", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/applications/application-1") && !init?.method) {
        return jsonResponse(application);
      }
      if (url.endsWith("/api/applications/application-1/transitions")) {
        expect(JSON.parse(String(init?.body))).toEqual({
          status: "recruiter_screen",
          notes: "Corrected the recorded stage.",
        });
        return jsonResponse({ ...application, status: "recruiter_screen" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ApplicationWorkflow
        apiBase="http://127.0.0.1:8000"
        postingId="posting-1"
        title="Support Engineer"
        reviewDecision="pursue"
        applicationId="application-1"
        applicationStatus="technical_interview"
        disabled={false}
        onChanged={async () => undefined}
        onError={() => undefined}
      />,
    );

    fireEvent.click(screen.getByText(/Manage application/));
    expect(await screen.findByText("Correct stage manually")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Notes for this update (recommended)"), {
      target: { value: "Corrected the recorded stage." },
    });
    fireEvent.change(screen.getByLabelText("Correct stage"), { target: { value: "recruiter_screen" } });
    fireEvent.click(screen.getByRole("button", { name: "Save correction" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("recruiter screen")).toBeInTheDocument();
  });


  it("uses Documents as the CV source of truth for new applications", async () => {
    let submittedBody: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/opportunities/posting-1/applications") && init?.method === "POST") {
        submittedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
        return jsonResponse({
          ...application,
          status: "preparing",
          resume_used: "",
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ApplicationWorkflow
        apiBase="http://127.0.0.1:8000"
        postingId="posting-1"
        title="Support Engineer"
        reviewDecision="pursue"
        applicationId={null}
        applicationStatus={null}
        disabled={false}
        onChanged={async () => undefined}
        onError={() => undefined}
      />,
    );

    fireEvent.click(screen.getByText("Prepare application"));
    expect(screen.queryByText("CV or resume version")).not.toBeInTheDocument();
    expect(screen.getByText(/attach the exact CV you will use from the Documents tab/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start preparing application" }));

    await waitFor(() => expect(submittedBody).toMatchObject({
      resume_used: "",
    }));
  });

});
