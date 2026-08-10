import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDashboard } from "./ApplicationDashboard";
import type { ApplicationStatus } from "./ApplicationWorkflow";

type TestApplicationStatus = ApplicationStatus | "archived";

type TestOpportunity = {
  posting_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  review_decision: string | null;
  application_id: string | null;
  application_status: TestApplicationStatus | null;
  outcome_type: string | null;
};

type TestApplication = {
  application_id: string;
  posting_id: string;
  status: TestApplicationStatus;
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

function jsonResponse(value: object, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const preparingOpportunity: TestOpportunity = {
  posting_id: "posting-preparing",
  source_url: "https://www.linkedin.com/jobs/view/100",
  title: "Cloud Support Engineer",
  company: "Example Systems",
  location: "Remote Spain",
  review_decision: "pursue",
  application_id: "application-0",
  application_status: "preparing",
  outcome_type: null,
};

const submittedOpportunity: TestOpportunity = {
  ...preparingOpportunity,
  posting_id: "posting-applied",
  title: "Application Support Engineer",
  source_url: "https://www.linkedin.com/jobs/view/101",
  application_id: "application-1",
  application_status: "submitted",
};

const interviewOpportunity: TestOpportunity = {
  ...preparingOpportunity,
  posting_id: "posting-interview",
  title: "Production Support Analyst",
  application_id: "application-2",
  application_status: "technical_interview",
};

const offerOpportunity: TestOpportunity = {
  ...preparingOpportunity,
  posting_id: "posting-offer",
  title: "Technical Support Engineer",
  application_id: "application-3",
  application_status: "offer",
};

const closedOpportunity: TestOpportunity = {
  ...preparingOpportunity,
  posting_id: "posting-closed",
  title: "Support Operations Engineer",
  application_id: "application-4",
  application_status: "rejected",
  outcome_type: "rejected_by_employer",
};

const pipeline: TestOpportunity[] = [
  preparingOpportunity,
  submittedOpportunity,
  interviewOpportunity,
  offerOpportunity,
  closedOpportunity,
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

function currentDataTransfer() {
  return {
    effectAllowed: "",
    setData: vi.fn(),
    getData: vi.fn(),
    clearData: vi.fn(),
    dropEffect: "move",
    files: [],
    items: [],
    types: [],
    setDragImage: vi.fn(),
  } as unknown as DataTransfer;
}

describe("ApplicationDashboard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.body.style.overflow = "";
  });

  it("groups durable applications into the five commercial pipeline lanes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));
    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findByRole("heading", { name: "Application Pipeline" })).toBeInTheDocument();
    expect(screen.getByLabelText("Preparing count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Applied count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Interviewing count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Offer count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Closed count")).toHaveTextContent("1");
  });

  it("ignores reviewed rows that no longer own an Application record", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([
      {
        ...preparingOpportunity,
        application_id: null,
        application_status: null,
      },
    ]));

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    await screen.findByRole("heading", { name: "Application Pipeline" });
    expect(screen.getByLabelText("Preparing count")).toHaveTextContent("0");
    expect(screen.queryByRole("button", { name: "Open Cloud Support Engineer" })).not.toBeInTheDocument();
  });

  it("moves an application through the audited transition endpoint", async () => {
    let currentPipeline = pipeline;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse(currentPipeline);
      if (url.endsWith("/api/applications/application-1/transitions") && init?.method === "POST") {
        currentPipeline = currentPipeline.map((item) =>
          item.posting_id === "posting-applied"
            ? { ...item, application_status: "recruiter_screen" as ApplicationStatus }
            : item,
        );
        return jsonResponse({ ...application, status: "recruiter_screen" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);
    fireEvent.change(await screen.findByLabelText("Move Application Support Engineer to stage"), {
      target: { value: "interviewing" },
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/transitions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          status: "recruiter_screen",
          notes: "Moved on application board from applied to interviewing.",
        }),
      }),
    ));
    expect(await screen.findByText("Application Support Engineer moved to Interviewing.")).toBeInTheDocument();
  });

  it("isolates dragging to an explicit handle instead of the interactive card", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));
    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    const openButton = await screen.findByRole("button", { name: "Open Application Support Engineer" });
    expect(openButton.closest("article")).toHaveAttribute("draggable", "false");
    expect(screen.getByRole("button", { name: "Drag Application Support Engineer to another stage" })).toHaveAttribute("draggable", "true");
    expect(screen.getByLabelText("Move Application Support Engineer to stage")).toBeEnabled();
  });

  it.each([
    ["Cloud Support Engineer", "application-0", "preparing"],
    ["Application Support Engineer", "application-1", "submitted"],
    ["Production Support Analyst", "application-2", "technical_interview"],
  ])("opens a viewport-level general-outcome dialog when closing %s", async (title, applicationId, status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));
    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.change(await screen.findByLabelText(`Move ${title} to stage`), { target: { value: "closed" } });

    const dialog = screen.getByRole("dialog", { name: `Close ${title}` });
    expect(dialog.closest("article")).toBeNull();
    expect(dialog.closest(".application-lane")).toBeNull();
    expect(screen.getByLabelText(`Close ${title} with outcome`)).toHaveValue("rejected_by_employer");
    expect(screen.getByText(`Current stage: ${String(status).replaceAll("_", " ")}`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm close" })).toBeInTheDocument();
  });

  it("uses offer-specific outcomes when closing an offer card", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));
    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.change(await screen.findByLabelText("Move Technical Support Engineer to stage"), {
      target: { value: "closed" },
    });
    const outcome = screen.getByLabelText("Close Technical Support Engineer with outcome");
    expect(Array.from(outcome.querySelectorAll("option")).map((option) => option.value)).toEqual([
      "offer_accepted",
      "offer_declined",
    ]);
  });

  it("cancels the close dialog without mutating the application", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));
    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.change(await screen.findByLabelText("Move Application Support Engineer to stage"), {
      target: { value: "closed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog", { name: "Close Application Support Engineer" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("routes drag-and-drop to Closed through the same close dialog", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));
    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    const handle = await screen.findByRole("button", { name: "Drag Application Support Engineer to another stage" });
    const closedLane = screen.getByRole("heading", { name: "Closed" }).closest("section");
    expect(closedLane).not.toBeNull();
    const dataTransfer = currentDataTransfer();
    fireEvent.dragStart(handle, { dataTransfer });
    fireEvent.dragEnter(closedLane!, { dataTransfer });
    fireEvent.dragOver(closedLane!, { dataTransfer });
    fireEvent.drop(closedLane!, { dataTransfer });

    expect(screen.getByRole("dialog", { name: "Close Application Support Engineer" })).toBeInTheDocument();
    expect(screen.getByLabelText("Close Application Support Engineer with outcome")).toBeInTheDocument();
  });

  it("closes an applied card through an explicit final outcome", async () => {
    let currentPipeline: TestOpportunity[] = pipeline;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse(currentPipeline);
      if (url.endsWith("/api/applications/application-1/outcomes") && init?.method === "POST") {
        currentPipeline = currentPipeline.map((item) =>
          item.posting_id === "posting-applied"
            ? { ...item, application_status: "rejected", outcome_type: "rejected_by_employer" }
            : item,
        );
        return jsonResponse({ ...application, status: "rejected", outcome_type: "rejected_by_employer" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);
    fireEvent.change(await screen.findByLabelText("Move Application Support Engineer to stage"), {
      target: { value: "closed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm close" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/outcomes",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          outcome_type: "rejected_by_employer",
          notes: "Closed from the Applications board.",
        }),
      }),
    ));
    expect(await screen.findByText("Application Support Engineer closed as Rejected by employer.")).toBeInTheDocument();
    expect(screen.getByLabelText("Closed count")).toHaveTextContent("2");
  });

  it("does not downgrade a precise interview status inside Interviewing", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));
    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    fireEvent.change(await screen.findByLabelText("Move Production Support Analyst to stage"), {
      target: { value: "interviewing" },
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/api/applications/application-2/transitions"))).toHaveLength(0);
  });

  it("moves Offer back to final interview instead of recruiter screen", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse(pipeline);
      if (url.endsWith("/api/applications/application-3/transitions") && init?.method === "POST") {
        return jsonResponse({ ...application, application_id: "application-3", posting_id: "posting-offer", status: "final_interview" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);
    fireEvent.change(await screen.findByLabelText("Move Technical Support Engineer to stage"), {
      target: { value: "interviewing" },
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-3/transitions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          status: "final_interview",
          notes: "Moved on application board from offer to interviewing.",
        }),
      }),
    ));
  });

  it("keeps archived applications separate from Closed and makes their workspace read-only", async () => {
    const archivedOpportunity: TestOpportunity = {
      ...submittedOpportunity,
      posting_id: "posting-archived",
      title: "Archived Support Engineer",
      application_id: "application-archived",
      application_status: "archived",
    };
    const archivedDetail: TestApplication = {
      ...application,
      application_id: "application-archived",
      posting_id: "posting-archived",
      status: "archived",
    };

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/application-index")) {
        return jsonResponse(url.includes("include_archived=true") ? [...pipeline, archivedOpportunity] : pipeline);
      }
      if (url.endsWith("/api/applications/application-archived")) return jsonResponse(archivedDetail);
      if (url.endsWith("/api/applications/application-archived/tasks")) return jsonResponse([]);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);
    fireEvent.click(await screen.findByRole("checkbox", { name: "Show archived cards" }));

    expect(await screen.findByLabelText("Archived count")).toHaveTextContent("1");
    expect(screen.getByLabelText("Closed count")).toHaveTextContent("1");
    expect(screen.getByRole("heading", { name: "Archived applications" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Open Archived Support Engineer" }));
    const workspace = screen.getByRole("dialog", { name: "Archived Support Engineer" });
    expect(within(workspace).getByText(/Archived application — this workspace is read-only/)).toBeInTheDocument();
    expect(within(workspace).getByRole("button", { name: "Restore application" })).toBeInTheDocument();

    fireEvent.click(within(workspace).getByRole("tab", { name: "Tasks" }));
    expect(await within(workspace).findByText(/tasks are read-only until the application is restored/)).toBeInTheDocument();
    expect(within(workspace).queryByRole("button", { name: "Add task" })).not.toBeInTheDocument();
  });

  it("surfaces workflow mutation errors inside the open application workspace", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/application-index")) return jsonResponse(pipeline);
      if (url.endsWith("/api/applications/application-1") && !init?.method) return jsonResponse(application);
      if (url.endsWith("/api/applications/application-1/transitions") && init?.method === "POST") {
        return jsonResponse({ detail: "Transition rejected for test." }, 409);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);
    fireEvent.click(await screen.findByRole("button", { name: "Open Application Support Engineer" }));
    const workspace = screen.getByRole("dialog", { name: "Application Support Engineer" });
    fireEvent.click(within(workspace).getByText("Manage application · submitted"));
    await within(workspace).findByText("Rafael_Application_Support_CV.pdf");
    fireEvent.change(within(workspace).getByLabelText("Stage"), { target: { value: "technical_interview" } });
    fireEvent.click(within(workspace).getByRole("button", { name: "Save stage" }));

    expect(await within(workspace).findByRole("alert")).toHaveTextContent("Transition rejected for test.");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/transitions",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("does not resurrect a deleted application if a stale pursued row is returned", async () => {
    const archivedOpportunity: TestOpportunity = {
      ...submittedOpportunity,
      application_status: "archived",
    };
    let currentPipeline: TestOpportunity[] = [archivedOpportunity];
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/application-index")) return jsonResponse(currentPipeline);
      if (url.endsWith("/api/applications/application-1/delete") && init?.method === "POST") {
        currentPipeline = [{
          ...submittedOpportunity,
          application_id: null,
          application_status: null,
        }];
        return jsonResponse({ application_id: "application-1", posting_id: "posting-applied", deleted: true });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);
    fireEvent.click(await screen.findByRole("checkbox", { name: "Show archived cards" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete permanently" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/delete",
      { method: "POST" },
    ));
    expect(await screen.findByText(/Application Support Engineer permanently deleted/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Application Support Engineer" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Preparing count")).toHaveTextContent("0");
  });
});
