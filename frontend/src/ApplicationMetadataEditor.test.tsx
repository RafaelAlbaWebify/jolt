import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationMetadataEditor } from "./ApplicationMetadataEditor";

const application = {
  application_id: "application-1",
  title: "IT Infrastructure Engineer",
  company: "PSI CRO",
  location: "St.-Maur-des-Fossés, Île-de-France, France",
  job_url: "https://jobs.example.test/france-role",
  source_url: "https://www.linkedin.com/jobs/view/123",
};

function jsonResponse(value: object, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApplicationMetadataEditor", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads the current application metadata into the form", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        application_url: "https://apply.example.test/123",
        notes: "Tailored CV pending.",
      }),
    );

    render(
      <ApplicationMetadataEditor
        apiBase="http://127.0.0.1:8000"
        application={application}
        onCancel={() => undefined}
        onSaved={async () => undefined}
      />,
    );

    expect(screen.getByLabelText("Job title")).toHaveValue("IT Infrastructure Engineer");
    expect(screen.getByLabelText("Company")).toHaveValue("PSI CRO");
    expect(screen.getByLabelText("Location")).toHaveValue(
      "St.-Maur-des-Fossés, Île-de-France, France",
    );
    expect(screen.getByLabelText("Job posting URL")).toHaveValue(
      "https://jobs.example.test/france-role",
    );
    expect(await screen.findByLabelText("Application/Apply URL")).toHaveValue(
      "https://apply.example.test/123",
    );
    expect(screen.getByLabelText("Notes")).toHaveValue("Tailored CV pending.");
  });

  it("cancels without writing metadata", async () => {
    const onCancel = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ application_url: "", notes: "" }),
    );

    render(
      <ApplicationMetadataEditor
        apiBase="http://127.0.0.1:8000"
        application={application}
        onCancel={onCancel}
        onSaved={async () => undefined}
      />,
    );

    await screen.findByLabelText("Notes");
    fireEvent.change(screen.getByLabelText("Location"), {
      target: { value: "Madrid, Spain" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);
  });

  it("saves changes and reports the updated metadata", async () => {
    const onSaved = vi.fn(async () => undefined);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/applications/application-1") && !init?.method) {
        return jsonResponse({ application_url: "", notes: "Old note" });
      }
      if (url.endsWith("/api/applications/application-1/metadata") && init?.method === "PATCH") {
        return jsonResponse({
          application_id: "application-1",
          posting_id: "posting-1",
          status: "preparing",
          title: "IT Infrastructure Engineer",
          company: "PSI CRO",
          location: "Madrid, Spain",
          job_url: "https://jobs.smartrecruiters.com/psicro/744000151009639-role",
          application_url: "",
          notes: "Old note",
          changed_fields: ["Location", "Job URL"],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ApplicationMetadataEditor
        apiBase="http://127.0.0.1:8000"
        application={application}
        onCancel={() => undefined}
        onSaved={onSaved}
      />,
    );

    await screen.findByLabelText("Notes");
    fireEvent.change(screen.getByLabelText("Location"), {
      target: { value: "Madrid, Spain" },
    });
    fireEvent.change(screen.getByLabelText("Job posting URL"), {
      target: { value: "https://jobs.smartrecruiters.com/psicro/744000151009639-role" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/applications/application-1/metadata",
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
    const request = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH")![1];
    expect(JSON.parse(String(request?.body))).toMatchObject({
      location: "Madrid, Spain",
      job_url: "https://jobs.smartrecruiters.com/psicro/744000151009639-role",
    });
    expect(onSaved).toHaveBeenCalledWith(
      expect.objectContaining({ location: "Madrid, Spain" }),
    );
  });

  it("shows a backend error and keeps the editor open", async () => {
    const onSaved = vi.fn(async () => undefined);
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/applications/application-1") && !init?.method) {
        return jsonResponse({ application_url: "", notes: "" });
      }
      if (init?.method === "PATCH") {
        return jsonResponse({ detail: "Metadata validation failed." }, 409);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ApplicationMetadataEditor
        apiBase="http://127.0.0.1:8000"
        application={application}
        onCancel={() => undefined}
        onSaved={onSaved}
      />,
    );

    await screen.findByLabelText("Notes");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Metadata validation failed.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("shows a useful duplicate job URL error without closing", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/applications/application-1") && !init?.method) {
        return jsonResponse({ application_url: "", notes: "" });
      }
      if (init?.method === "PATCH") {
        return jsonResponse(
          {
            detail:
              "This job URL already belongs to another JOLT opportunity (posting_id=posting-2).",
          },
          409,
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    render(
      <ApplicationMetadataEditor
        apiBase="http://127.0.0.1:8000"
        application={application}
        onCancel={() => undefined}
        onSaved={async () => undefined}
      />,
    );

    await screen.findByLabelText("Notes");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This job URL already belongs to another JOLT opportunity",
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
