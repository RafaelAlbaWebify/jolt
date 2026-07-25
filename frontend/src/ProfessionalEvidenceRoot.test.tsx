import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProfessionalEvidenceRoot } from "./ProfessionalEvidenceRoot";

const emptyRoot = {
  configured: false,
  root_path: null,
  exists: false,
  writable: false,
  verified_at: null,
};

const configuredRoot = {
  configured: true,
  root_path: "C:\\Users\\ralba\\Documents\\JOLT Evidence",
  exists: true,
  writable: true,
  verified_at: "2026-07-25T08:00:00Z",
};

describe("ProfessionalEvidenceRoot", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("verifies, displays, and clears the local evidence root", async () => {
    const onChanged = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (!init?.method) return new Response(JSON.stringify(emptyRoot), { status: 200 });
      if (init.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          root_path: "C:\\Users\\ralba\\Documents\\JOLT Evidence",
        });
        return new Response(JSON.stringify(configuredRoot), { status: 200 });
      }
      if (init.method === "DELETE") {
        return new Response(JSON.stringify(emptyRoot), { status: 200 });
      }
      throw new Error(`Unexpected method: ${init.method}`);
    });

    render(
      <ProfessionalEvidenceRoot
        apiBase="http://127.0.0.1:8000"
        active
        onChanged={onChanged}
      />,
    );

    expect(await screen.findByText("Not configured")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Local directory path"), {
      target: { value: "C:\\Users\\ralba\\Documents\\JOLT Evidence" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Verify and save" }));

    expect(await screen.findByText("Verified")).toBeInTheDocument();
    expect(screen.getByText(/Resolved path:/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear configuration" }));

    await waitFor(() => expect(screen.getByText("Not configured")).toBeInTheDocument());
    expect(onChanged).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
