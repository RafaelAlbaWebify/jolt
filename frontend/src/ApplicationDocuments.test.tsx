import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDocuments } from "./ApplicationDocuments";

const documentRecord = {
  document_id: "document-1",
  application_id: "application-1",
  document_type: "resume" as const,
  title: "Support resume",
  file_path: "",
  source_url: "https://example.test/resume-v1",
  status: "ready" as const,
  notes: "First tailored version.",
  stored_filename: "resume-v1.pdf",
  mime_type: "application/pdf",
  file_size: 2048,
  file_sha256: "abc123",
  has_file: true,
  created_at: "2026-08-15T10:00:00Z",
  updated_at: "2026-08-15T10:00:00Z",
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

  it("uploads a selected file into JOLT and exposes its download", async () => {
    const created = {
      ...documentRecord,
      stored_filename: "",
      mime_type: "",
      file_size: 0,
      file_sha256: "",
      has_file: false,
    };

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(created))
      .mockResolvedValueOnce(jsonResponse(documentRecord))
      .mockResolvedValueOnce(jsonResponse([documentRecord]));

    const onChanged = vi.fn().mockResolvedValue(undefined);

    render(
      <ApplicationDocuments
        apiBase="http://api"
        applicationId="application-1"
        onChanged={onChanged}
        onError={vi.fn()}
      />,
    );

    await screen.findByText("No document records yet.");

    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Support resume" },
    });

    const file = new File(["resume bytes"], "resume v1.pdf", {
      type: "application/pdf",
    });

    fireEvent.change(screen.getByLabelText("File"), {
      target: { files: [file] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add document" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api/api/application-documents/document-1/file?filename=resume%20v1.pdf",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/pdf" },
          body: file,
        }),
      ),
    );

    expect(await screen.findByText(/Stored in JOLT: resume-v1\.pdf/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download file" })).toHaveAttribute(
      "href",
      "http://api/api/application-documents/document-1/file",
    );
    expect(screen.queryByLabelText("Local file path")).not.toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("edits metadata without replacing the stored file", async () => {
    const updated = {
      ...documentRecord,
      title: "Support resume final",
      status: "submitted" as const,
    };

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([documentRecord]))
      .mockResolvedValueOnce(jsonResponse(updated))
      .mockResolvedValueOnce(jsonResponse([updated]));

    const onChanged = vi.fn().mockResolvedValue(undefined);

    render(
      <ApplicationDocuments
        apiBase="http://api"
        applicationId="application-1"
        onChanged={onChanged}
        onError={vi.fn()}
      />,
    );

    expect(await screen.findByText("Support resume")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit document" }));
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Support resume final" },
    });
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "submitted" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save document changes" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api/api/application-documents/document-1/update",
        expect.objectContaining({ method: "POST" }),
      ),
    );

    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/api/application-documents/document-1/file?"),
      ),
    ).toBe(false);

    expect(await screen.findByText("Support resume final")).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("keeps stored files downloadable when the application is archived", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([documentRecord]));

    render(
      <ApplicationDocuments
        apiBase="http://api"
        applicationId="application-1"
        readOnly
        onChanged={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(await screen.findByText("Support resume")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download file" })).toHaveAttribute(
      "href",
      "http://api/api/application-documents/document-1/file",
    );
    expect(screen.queryByRole("button", { name: "Edit document" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("File")).not.toBeInTheDocument();
  });

  it("cancels editing without changing the saved record", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([documentRecord]));

    render(
      <ApplicationDocuments
        apiBase="http://api"
        applicationId="application-1"
        onChanged={vi.fn()}
        onError={vi.fn()}
      />,
    );

    await screen.findByText("Support resume");

    fireEvent.click(screen.getByRole("button", { name: "Edit document" }));
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Local only" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cancel edit" }));

    expect(screen.getByLabelText("Title")).toHaveValue("");
    expect(screen.getByText("Support resume")).toBeInTheDocument();
  });

  it("retries an initial load failure", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse([documentRecord]));

    render(
      <ApplicationDocuments
        apiBase="http://api"
        applicationId="application-1"
        onChanged={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to load application documents.",
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry documents" }));

    expect(await screen.findByText("Support resume")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});