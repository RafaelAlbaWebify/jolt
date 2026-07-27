import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationTasks } from "./ApplicationTasks";

const task = {
  task_id: "task-1",
  title: "Prepare support examples",
  notes: "Use two production incidents.",
  due_at: "2026-07-28T10:00:00+00:00",
  status: "open" as const,
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApplicationTasks", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("edits and reloads a persisted task", async () => {
    const updated = { ...task, title: "Prepare final support examples" };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([task]))
      .mockResolvedValueOnce(jsonResponse(updated))
      .mockResolvedValueOnce(jsonResponse([updated]));
    const onChanged = vi.fn().mockResolvedValue(undefined);

    render(<ApplicationTasks apiBase="http://api" applicationId="application-1" onChanged={onChanged} onError={vi.fn()} />);
    expect(await screen.findByText("Prepare support examples")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit task" }));
    fireEvent.change(screen.getByLabelText("Task title"), { target: { value: "Prepare final support examples" } });
    fireEvent.click(screen.getByRole("button", { name: "Save task changes" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/application-tasks/task-1/update",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("Prepare final support examples")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add task" })).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("cancels editing without changing the saved task", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([task]));
    render(<ApplicationTasks apiBase="http://api" applicationId="application-1" onChanged={vi.fn()} onError={vi.fn()} />);
    await screen.findByText("Prepare support examples");
    fireEvent.click(screen.getByRole("button", { name: "Edit task" }));
    fireEvent.change(screen.getByLabelText("Task title"), { target: { value: "Local only" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel edit" }));
    expect(screen.getByLabelText("Task title")).toHaveValue("");
    expect(screen.getByText("Prepare support examples")).toBeInTheDocument();
  });

  it("retries an initial load failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse([task]));
    render(<ApplicationTasks apiBase="http://api" applicationId="application-1" onChanged={vi.fn()} onError={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load application tasks.");
    fireEvent.click(screen.getByRole("button", { name: "Retry tasks" }));
    expect(await screen.findByText("Prepare support examples")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows API validation detail and keeps the edit form", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([task]))
      .mockResolvedValueOnce(jsonResponse({ detail: "Task title is required." }, 422));
    render(<ApplicationTasks apiBase="http://api" applicationId="application-1" onChanged={vi.fn()} onError={vi.fn()} />);
    await screen.findByText("Prepare support examples");
    fireEvent.click(screen.getByRole("button", { name: "Edit task" }));
    fireEvent.change(screen.getByLabelText("Task title"), { target: { value: "Revised task" } });
    fireEvent.click(screen.getByRole("button", { name: "Save task changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Task title is required.");
    expect(screen.getByRole("button", { name: "Save task changes" })).toBeInTheDocument();
  });
});
