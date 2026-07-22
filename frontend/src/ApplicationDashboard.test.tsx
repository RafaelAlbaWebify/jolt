import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDashboard } from "./ApplicationDashboard";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const opportunity = {
  posting_id: "posting-1",
  title: "Application Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",
  review_decision: "pursue",
  application_id: "application-1",
  application_status: "submitted",
  outcome_type: null,
};

const application = {
  application_id: "application-1",
  posting_id: "posting-1",
  status: "submitted",
  application_url: "https://careers.example.test/apply/1",
  resume_used: "Rafael_Application_Support_CV.pdf",
  notes: "Tailored for application support evidence.",
  outcome_type: null,
  events: [
    {
      event_id: "event-1",
      event_type: "application_created",
      from_status: "",
      to_status: "preparing",
      notes: "Prepared locally.",
      occurred_at: "2026-07-14T10:00:00+00:00",
    },
    {
      event_id: "event-2",
      event_type: "status_changed",
      from_status: "preparing",
      to_status: "submitted",
      notes: "Submitted manually on company site.",
      occurred_at: "2026-07-14T11:00:00+00:00",
    },
  ],
};

describe("ApplicationDashboard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("lazy-loads one application, advances its stage, and displays immutable event history", async () => {
    let currentApplication = application;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) {
        return jsonResponse([{
          ...opportunity,
          application_status: currentApplication.status,
          outcome_type: currentApplication.outcome_type,
        }]);
      }
      if (url.endsWith("/api/applications/application-1") && !init) {
        return jsonResponse(currentApplication);
      }
      if (url.endsWith("/api/applications/application-1/transitions")) {
        currentApplication = {
          ...currentApplication,
          status: "recruiter_screen",
          events: [
            ...currentApplication.events,
            {
              event_id: "event-3",
              event_type: "status_changed",
              from_status: "submitted",
              to_status: "recruiter_screen",
              notes: "Recruiter call booked.",
              occurred_at: "2026-07-14T12:00:00+00:00",
            },
          ],
        };
        return jsonResponse(currentApplication);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByRole("heading", { name: opportunity.title })).toBeInTheDocument();
    const workflowSummary = await screen.findByText("Application workflow · submitted");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenLastCalledWith("http://127.0.0.1:8000/api/application-index");

    fireEvent.click(workflowSummary);
    expect(await screen.findByText("Rafael_Application_Support_CV.pdf")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/preparing → submitted/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Stage notes (optional)"), {
      target: { value: "Recruiter call booked." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Mark recruiter screen" }));

    expect(await screen.findByText("Application workflow · recruiter screen")).toBeInTheDocument();
    expect(screen.getByText(/submitted → recruiter screen/)).toBeInTheDocument();
  });

  it("creates a local application record only after a pursue decision", async () => {
    let created = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) {
        return jsonResponse([{ ...opportunity, application_id: created ? "application-1" : null }]);
      }
      if (url.endsWith("/api/opportunities/posting-1/applications") && init?.method === "POST") {
        created = true;
        return jsonResponse({ ...application, status: "preparing", events: [application.events[0]] });
      }
      if (url.endsWith("/api/applications/application-1")) {
        return jsonResponse({ ...application, status: "preparing", events: [application.events[0]] });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByText("Start application workflow")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Start application workflow"));
    fireEvent.change(screen.getByLabelText("Resume or CV used (optional)"), {
      target: { value: "Rafael_Application_Support_CV.pdf" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create application record" }));

    expect(await screen.findByText("Application workflow · preparing")).toBeInTheDocument();
  });

  it("summarises, filters, and searches without loading collapsed histories", async () => {
    const ready = {
      ...opportunity,
      posting_id: "posting-2",
      title: "Cloud Support Engineer",
      company: "Beta Cloud",
      application_id: null,
      application_status: null,
    };
    const closed = {
      ...opportunity,
      posting_id: "posting-3",
      title: "Production Support Analyst",
      company: "Gamma Systems",
      application_id: "application-3",
      application_status: "closed",
      outcome_type: "rejected_by_employer",
    };

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse([opportunity, ready, closed]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByText("Cloud Support Engineer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "ready (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "active (1)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "closed (1)" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "closed (1)" }));
    expect(screen.getByText("Production Support Analyst")).toBeInTheDocument();
    expect(screen.queryByText("Cloud Support Engineer")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "all (3)" }));
    fireEvent.change(screen.getByLabelText("Search applications"), {
      target: { value: "Beta Cloud" },
    });
    expect(screen.getByText("Cloud Support Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Application Support Engineer")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
