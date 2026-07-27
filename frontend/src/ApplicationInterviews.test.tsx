import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationInterviews } from "./ApplicationInterviews";

const interviewRecord = {
  interview_id: "interview-1",
  interview_type: "recruiter_screen",
  scheduled_at: "2026-07-28T10:00:00.000Z",
  timezone: "Europe/Madrid",
  format_location: "Teams",
  participants: "Recruiter",
  preparation_notes: "Review examples",
  outcome_notes: "",
  status: "scheduled" as const,
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApplicationInterviews", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("edits and reloads a persisted interview", async () => {
    const updated = { ...interviewRecord, interview_type: "technical_interview", format_location: "Office" };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([interviewRecord]))
      .mockResolvedValueOnce(jsonResponse(updated))
      .mockResolvedValueOnce(jsonResponse([updated]));
    const onChanged = vi.fn().mockResolvedValue(undefined);

    render(<ApplicationInterviews apiBase="http://api" applicationId="application-1" onChanged={onChanged} onError={vi.fn()} />);
    expect(await screen.findByText("recruiter screen")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit interview" }));
    fireEvent.change(screen.getByLabelText("Interview type"), { target: { value: "technical_interview" } });
    fireEvent.change(screen.getByLabelText("Format or location"), { target: { value: "Office" } });
    fireEvent.click(screen.getByRole("button", { name: "Save interview changes" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/application-interviews/interview-1/update",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("technical interview")).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("cancels editing without changing the saved interview", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([interviewRecord]));
    render(<ApplicationInterviews apiBase="http://api" applicationId="application-1" onChanged={vi.fn()} onError={vi.fn()} />);
    await screen.findByText("recruiter screen");
    fireEvent.click(screen.getByRole("button", { name: "Edit interview" }));
    fireEvent.change(screen.getByLabelText("Format or location"), { target: { value: "Local only" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel edit" }));
    expect(screen.getByLabelText("Format or location")).toHaveValue("");
    expect(screen.getByText("Teams")).toBeInTheDocument();
  });

  it("retries an initial load failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse([interviewRecord]));
    render(<ApplicationInterviews apiBase="http://api" applicationId="application-1" onChanged={vi.fn()} onError={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load application interviews.");
    fireEvent.click(screen.getByRole("button", { name: "Retry interviews" }));
    expect(await screen.findByText("recruiter screen")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
