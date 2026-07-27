import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationContacts } from "./ApplicationContacts";

const contact = {
  contact_id: "contact-1",
  name: "Morgan Lee",
  role: "Technical recruiter",
  company: "Example Systems",
  email: "morgan@example.test",
  phone: "+34 600 000 000",
  linkedin_url: "https://www.linkedin.com/in/morgan-lee",
  notes: "Initial contact.",
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApplicationContacts", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("edits a persisted contact, reloads it, and resets edit state", async () => {
    const updated = { ...contact, role: "Senior technical recruiter" };
    const onChanged = vi.fn().mockResolvedValue(undefined);
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([contact]))
      .mockResolvedValueOnce(jsonResponse(updated))
      .mockResolvedValueOnce(jsonResponse([updated]));

    render(
      <ApplicationContacts
        apiBase="http://api"
        applicationId="application-1"
        onChanged={onChanged}
        onError={vi.fn()}
      />,
    );

    expect(await screen.findByText("Technical recruiter · Example Systems")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit contact" }));
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "Senior technical recruiter" } });
    fireEvent.click(screen.getByRole("button", { name: "Save contact changes" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api/api/application-contacts/contact-1/update",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ ...contact, contact_id: undefined, role: "Senior technical recruiter" }),
        }),
      ),
    );
    expect(await screen.findByText("Senior technical recruiter · Example Systems")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add contact" })).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("cancels editing without mutating the saved contact", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([contact]));
    render(
      <ApplicationContacts
        apiBase="http://api"
        applicationId="application-1"
        onChanged={vi.fn()}
        onError={vi.fn()}
      />,
    );

    await screen.findByText("Technical recruiter · Example Systems");
    fireEvent.click(screen.getByRole("button", { name: "Edit contact" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Changed locally" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel edit" }));

    expect(screen.getByLabelText("Name")).toHaveValue("");
    expect(screen.getByText("Morgan Lee")).toBeInTheDocument();
  });

  it("surfaces a load failure and retries explicitly", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse([contact]));

    render(
      <ApplicationContacts
        apiBase="http://api"
        applicationId="application-1"
        onChanged={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load application contacts.");
    fireEvent.click(screen.getByRole("button", { name: "Retry contacts" }));
    expect(await screen.findByText("Morgan Lee")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
