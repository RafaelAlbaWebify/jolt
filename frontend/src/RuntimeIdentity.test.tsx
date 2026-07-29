import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RuntimeIdentityPanel } from "./RuntimeIdentity";

const runtimeIdentity = {
  service: "jolt-backend",
  version: "0.8.0",
  git: {
    repository_root: "C:/Users/ralba/Documents/GitHub/jolt",
    branch: "agent/runtime-identity-baseline",
    commit_sha: "1234567890abcdef",
    dirty: false,
    source: "git",
  },
  database: {
    database_url: "sqlite:///C:/Users/ralba/Documents/GitHub/jolt/backend/data/jolt.db",
    database_path: "C:/Users/ralba/Documents/GitHub/jolt/backend/data/jolt.db",
    alembic_revision: "20260728_0017",
    record_counts: {
      postings: 12,
      applications: 3,
      professional_capture_runs: 1,
    },
  },
  evidence_root: {
    configured: true,
    root_path: "C:/Users/ralba/Documents/GitHub/jolt/backend/data/professional-evidence",
    exists: true,
    writable: true,
    verified_at: "2026-07-28T10:00:00Z",
  },
  process: {
    process_id: 4242,
    current_working_directory: "C:/Users/ralba/Documents/GitHub/jolt/backend",
    python_executable: "C:/Users/ralba/Documents/GitHub/jolt/backend/.venv/Scripts/python.exe",
    python_version: "3.13.5",
    platform: "Windows-10",
  },
};

describe("RuntimeIdentityPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("surfaces the active checkout, database, evidence root, and process", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(runtimeIdentity), { status: 200 }),
    );

    render(<RuntimeIdentityPanel apiBase="http://127.0.0.1:8000" />);

    expect(await screen.findByText("Developer diagnostics")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/agent\/runtime-identity-baseline/)).toBeInTheDocument());
    expect(screen.getByText(/1234567890ab/)).toBeInTheDocument();
    expect(screen.getByText("C:/Users/ralba/Documents/GitHub/jolt/backend/data/jolt.db")).toBeInTheDocument();
    expect(screen.getByText("Alembic 20260728_0017")).toBeInTheDocument();
    expect(screen.getByText(/12 opportunities/)).toBeInTheDocument();
    expect(screen.getByText(/3 applications/)).toBeInTheDocument();
    expect(screen.getByText(/1 professional captures/)).toBeInTheDocument();
    expect(screen.getByText(/professional-evidence/)).toBeInTheDocument();
    expect(screen.getByText("PID 4242")).toBeInTheDocument();
  });
});