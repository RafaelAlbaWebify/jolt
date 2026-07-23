import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDashboard } from "./ApplicationDashboard";
import type { ApplicationStatus } from "./ApplicationWorkflow";

type TestOpportunity = {
  posting_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  review_decision: string | null;
  application_id: string | null;
  application_status: ApplicationStatus | null;
  outcome_type: string | null;
};

type TestApplication = {
  application_id: string;
  posting_id: string;
  status: ApplicationStatus;
  application_url: string;
  resume_used: string;
  notes: string;
  outcome_type: string | null;
  events: Array<{
    event_id: string;
    event_type: string;
    from_status: string;
    to_status: string;
    notes: string;
    occurred_at: string;
  }>;
};

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const baseOpportunity: TestOpportunity = {
  posting_id: "posting-preparing",
  source_url: "https://www.linkedin.com/jobs/view/100",
  title: "Cloud Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",
  review_decision: "pursue",
  application_id: null,
  application_status: null,
  outcome_type: null,
};

const submittedOpportunity: TestOpportunity = {
  ...baseOpportunity,
  posting_id: "posting-applied",
  title: "Application Support Engineer",
  source_url: "https://www.linkedin.com/jobs/view/101",
  application_id: "application-1",
  application_status: "submitted",
};

const pipeline: TestOpportunity[] = [
  baseOpportunity,
  submittedOpportunity,
  {
    ...baseOpportunity,
    posting_id: "posting-interview",
    title: "Production Support Analyst",
    application_id: "application-2",
    application_status: "technical_interview",
  },
  {
    ...baseOpportunity,
    posting_id: "posting-offer",
    title: "Technical Support Engineer",
    application_id: "application-3",
    application_status: "offer",
  },
  {
    ...baseOpportunity,
    posting_id: "posting-closed",
    title: "Support Operations Engineer",
    application_id: "application-4",
    application_status: "rejected",
    outcome_type: "rejected_by_employer",
  },
];

const application: TestApplication = {
  application_id: "application-1",
  posting_id: "posting-applied",
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
      notes: "Submitted manually.",
      occurred_at: "2026-07-14T11:00:00+00:00",
    },
  ],
};

describe("ApplicationDashboard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.body.style.overflow = "";
  });

  it("groups applications into the five commercial pipeline lanes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByRole("heading", { name: "Application management" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Preparing" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Applied" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Interviewing" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Offer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Closed" })).toBeInTheDocument();

    expect(screen.getByLabelText("Preparing count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Applied count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Interviewing count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Offer count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Closed count")).toHaveTextContent("1");
  });

  it("opens one application in a dedicated workspace instead of expanding it inline", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse(pipeline);
      if (url.endsWith("/api/applications/application-1")) return jsonResponse(application);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.click(await screen.findByRole("button", { name: "Open Application Support Engineer" }));

    expect(screen.getByRole("dialog", { name: "Application Support Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Overview")).toHaveClass("application-detail-tab-active");
    expect(screen.getByText("Tasks")).toBeInTheDocument();
    expect(screen.getByText("Interviews")).toBeInTheDocument();
    expect(screen.getByText("Contacts")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Timeline")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Manage application · submitted"));
    expect(await screen.findByText("Rafael_Application_Support_CV.pdf")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("saves an audited stage change from the selected application workspace", async () => {
    let currentApplication: TestApplication = application;
    let currentPipeline: TestOpportunity[] = pipeline;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse(currentPipeline);
      if (url.endsWith("/api/applications/application-1") && !init) return jsonResponse(currentApplication);
      if (url.endsWith("/api/applications/application-1/transitions") && init?.method === "POST") {
        currentApplication = {
          ...currentApplication,
          status: "technical_interview",
          events: [
            ...currentApplication.events,
            {
              event_id: "event-3",
              event_type: "status_changed",
              from_status: "submitted",
              to_status: "technical_interview",
              notes: "Technical interview booked.",
              occurred_at: "2026-07-14T12:00:00+00:00",
            },
          ],
        };
        currentPipeline = currentPipeline.map((item): TestOpportunity => item.posting_id === "posting-applied"
          ? { ...item, application_status: "technical_interview" }
          : item);
        return jsonResponse(currentApplication);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.click(await screen.findByRole("button", { name: "Open Application Support Engineer" }));
    fireEvent.click(screen.getByText("Manage application · submitted"));
    await screen.findByText("Rafael_Application_Support_CV.pdf");

    fireEvent.change(screen.getByLabelText("Activity or correction notes (recommended)"), {
      target: { value: "Technical interview booked." },
    });
    fireEvent.change(screen.getByLabelText("Stage"), { target: { value: "technical_interview" } });
    fireEvent.click(screen.getByRole("button", { name: "Save stage" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/transitions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          status: "technical_interview",
          notes: "Technical interview booked.",
        }),
      }),
    ));

    expect(await screen.findByText("Manage application · technical interview")).toBeInTheDocument();
  });
});
