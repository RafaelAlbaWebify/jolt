import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationContacts } from "./ApplicationContacts";
import { ApplicationDocuments } from "./ApplicationDocuments";

function jsonResponse(value: object) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("application contacts and documents", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads and creates a persisted contact", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ contact_id: "contact-1" }))
      .mockResolvedValueOnce(jsonResponse([{
        contact_id: "contact-1",
        name: "Morgan Lee",
        role: "Technical recruiter",
        company: "Example Systems",
        email: "morgan@example.test",
        phone: "",
        linkedin_url: "",
        notes: "",
      }]))
      .mockResolvedValueOnce(jsonResponse([]));

    render(<ApplicationContacts apiBase="http://127.0.0.1:8000" applicationId="application-1" onChanged={vi.fn().mockResolvedValue(undefined)} onError={vi.fn()} />);
    await screen.findByText("No contacts recorded yet.");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Morgan Lee" } });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "Technical recruiter" } });
    fireEvent.click(screen.getByRole("button", { name: "Add contact" }));

    expect(await screen.findByText("Morgan Lee")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/applications/application-1/contacts",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("loads and creates a persisted document record", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ document_id: "document-1" }))
      .mockResolvedValueOnce(jsonResponse([{
        document_id: "document-1",
        document_type: "resume",
        title: "Tailored support resume",
        file_path: "C:/resume.pdf",
        source_url: "",
        status: "ready",
        notes: "",
      }]))
      .mockResolvedValueOnce(jsonResponse([]));

    render(<ApplicationDocuments apiBase="http://127.0.0.1:8000" applicationId="application-1" onChanged={vi.fn().mockResolvedValue(undefined)} onError={vi.fn()} />);
    await screen.findByText("No document records yet.");
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Tailored support resume" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "ready" } });
    fireEvent.click(screen.getByRole("button", { name: "Add document" }));

    await waitFor(() => expect(screen.getByText("Tailored support resume")).toBeInTheDocument());
    expect(screen.getByText("resume · ready")).toBeInTheDocument();
  });
});
