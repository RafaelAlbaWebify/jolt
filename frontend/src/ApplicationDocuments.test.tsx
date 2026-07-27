import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDocuments } from "./ApplicationDocuments";

const documentRecord = {
  document_id: "document-1",
  document_type: "resume" as const,
  title: "Support resume",
  file_path: "C:/resume-v1.pdf",
  source_url: "https://example.test/resume-v1",
  status: "ready" as const,
  notes: "First tailored version.",
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApplicationDocuments", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("edits and reloads a persisted document", async () => {
    const updated = { ...documentRecord, title: "Support resume final", status: "submitted" as const };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([documentRecord]))
      .mockResolvedValueOnce(jsonResponse(updated))
      .mockResolvedValueOnce(jsonResponse([updated]));
    const onChanged = vi.fn().mockResolvedValue(undefined);

    render(<ApplicationDocuments apiBase="http://api" applicationId="application-1" onChanged={onChanged} onError={vi.fn()} />);
    expect(await screen.findByText("Support resume")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit document" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Support resume final" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "submitted" } });
    fireEvent.click(screen.getByRole("button", { name: "Save document changes" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/application-documents/document-1/update",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("Support resume final")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add document" })).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("cancels editing without changing the saved record", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([documentRecord]));
    render(<ApplicationDocuments apiBase="http://api" applicationId="application-1" onChanged={vi.fn()} onError={vi.fn()} />);
    await screen.findByText("Support resume");
    fireEvent.click(screen.getByRole("button", { name: "Edit document" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Local only" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel edit" }));
    expect(screen.getByLabelText("Title")).toHaveValue("");
    expect(screen.getByText("Support resume")).toBeInTheDocument();
  });

  it("retries an initial load failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse([documentRecord]));
    render(<ApplicationDocuments apiBase="http://api" applicationId="application-1" onChanged={vi.fn()} onError={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load application documents.");
    fireEvent.click(screen.getByRole("button", { name: "Retry documents" }));
    expect(await screen.findByText("Support resume")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
