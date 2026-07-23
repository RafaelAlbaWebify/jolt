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
  source_url: "https://www.linkedin.com/jobs/view/123",
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

  it("loads the action queue and advances a submitted application with activity notes", async () => {
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
      if (url.endsWith("/api/applications/application-1") && !init) return jsonResponse(currentApplication);
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
    expect(screen.getByRole("button", { name: "attention (1)" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith("http://127.0.0.1:8000/api/application-index");

    fireEvent.click(screen.getByText("Manage application · submitted"));
    expect(await screen.findByText("Rafael_Application_Support_CV.pdf")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Activity or correction notes (recommended)"), {
      target: { value: "Recruiter call booked." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Record recruiter screen/ }));

    expect(await screen.findByText("Manage application · recruiter screen")).toBeInTheDocument();
  });

  it("creates a preparation record without pretending the external application was submitted", async () => {
    let created = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) {
        return jsonResponse([{
          ...opportunity,
          application_id: created ? "application-1" : null,
          application_status: created ? "preparing" : null,
        }]);
      }
      if (url.endsWith("/api/opportunities/posting-1/applications") && init?.method === "POST") {
        created = true;
        return jsonResponse({ ...application, status: "preparing", events: [application.events[0]] });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.click(await screen.findByText("Prepare application"));
    fireEvent.change(screen.getByLabelText("CV or resume version (optional)"), {
      target: { value: "Rafael_Application_Support_CV.pdf" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create preparation record" }));

    expect(await screen.findByText("Manage application · preparing")).toBeInTheDocument();
    expect(screen.getByText("Finish documents and record external submission")).toBeInTheDocument();
  });

  it("groups preparation, attention, interviews, and closed applications", async () => {
    const preparation = {
      ...opportunity,
      posting_id: "posting-2",
      title: "Cloud Support Engineer",
      application_id: "application-2",
      application_status: "preparing",
    };
    const interview = {
      ...opportunity,
      posting_id: "posting-3",
      title: "Production Support Analyst",
      application_id: "application-3",
      application_status: "technical_interview",
    };
    const closed = {
      ...opportunity,
      posting_id: "posting-4",
      title: "Technical Support Engineer",
      application_id: "application-4",
      application_status: "rejected",
      outcome_type: "rejected_by_employer",
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse([opportunity, preparation, interview, closed]),
    );

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByText("Application Support Engineer")).toBeInTheDocument();
    expect(screen.getByText("Action required").previousSibling).toHaveTextContent("1");
    expect(screen.getByText("Preparation").previousSibling).toHaveTextContent("1");
    expect(screen.getByText("Interviews").previousSibling).toHaveTextContent("1");
    expect(screen.getByText("Closed").previousSibling).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: "active (1)" }));
    expect(screen.getByText("Production Support Analyst")).toBeInTheDocument();
    expect(screen.queryByText("Application Support Engineer")).not.toBeInTheDocument();
  });
});
