import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationContacts } from "./ApplicationContacts";
import { ApplicationDocuments } from "./ApplicationDocuments";
import { ApplicationInterviews } from "./ApplicationInterviews";
import { ApplicationTasks } from "./ApplicationTasks";

function jsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const sharedProps = {
  apiBase: "http://api",
  applicationId: "application-1",
  readOnly: true,
  onChanged: vi.fn().mockResolvedValue(undefined),
  onError: vi.fn(),
};

describe("archived application workspace resources", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("keeps tasks visible but removes task mutations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([{
      task_id: "task-1",
      title: "Follow up",
      notes: "Recorded before archive.",
      due_at: null,
      status: "open",
    }]));

    render(<ApplicationTasks {...sharedProps} />);
    expect(await screen.findByText("Follow up")).toBeInTheDocument();
    expect(screen.getByText(/tasks are read-only until the application is restored/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add task" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit task" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Complete" })).not.toBeInTheDocument();
  });

  it("keeps interviews visible but removes interview mutations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([{
      interview_id: "interview-1",
      interview_type: "technical_interview",
      scheduled_at: "2026-08-10T10:00:00Z",
      timezone: "Europe/Madrid",
      format_location: "Teams",
      participants: "Recruiter",
      preparation_notes: "Prepare examples.",
      outcome_notes: "",
      status: "scheduled",
    }]));

    render(<ApplicationInterviews {...sharedProps} />);
    expect(await screen.findByText("technical interview")).toBeInTheDocument();
    expect(screen.getByText(/interviews are read-only until the application is restored/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Schedule interview" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit interview" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Complete" })).not.toBeInTheDocument();
  });

  it("keeps contacts visible but removes contact mutations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([{
      contact_id: "contact-1",
      name: "Morgan Lee",
      role: "Recruiter",
      company: "Example Systems",
      email: "morgan@example.test",
      phone: "",
      linkedin_url: "",
      notes: "Recorded before archive.",
    }]));

    render(<ApplicationContacts {...sharedProps} />);
    expect(await screen.findByText("Morgan Lee")).toBeInTheDocument();
    expect(screen.getByText(/contacts are read-only until the application is restored/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add contact" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit contact" })).not.toBeInTheDocument();
  });

  it("keeps documents visible but removes document mutations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([{
      document_id: "document-1",
      document_type: "resume",
      title: "Submitted resume",
      file_path: "C:/resume.pdf",
      source_url: "",
      status: "submitted",
      notes: "Recorded before archive.",
    }]));

    render(<ApplicationDocuments {...sharedProps} />);
    expect(await screen.findByText("Submitted resume")).toBeInTheDocument();
    expect(screen.getByText(/documents are read-only until the application is restored/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add document" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit document" })).not.toBeInTheDocument();
  });
});
