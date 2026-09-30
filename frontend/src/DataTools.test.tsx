import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTools } from "./DataTools";

const EMPTY_STATUS = {
  overall_status: "no_evidence",
  last_intelligence_update_at: null,
  context_updated_at: null,
  current_sections: 0,
  attention_sections: 0,
  sections: {
    review_inbox: {
      state: "no_evidence",
      evidence_at: null,
      analyzed_at: null,
      reason: "No captured job evidence is waiting for AI review.",
      operator_relevant: true,
    },
  },
};

const CURRENT_STATUS = {
  overall_status: "current",
  last_intelligence_update_at: "2026-09-30T09:00:00Z",
  context_updated_at: "2026-09-30T09:00:00Z",
  current_sections: 6,
  attention_sections: 0,
  sections: {
    review_inbox: {
      state: "current",
      evidence_at: "2026-09-30T08:00:00Z",
      analyzed_at: "2026-09-30T09:00:00Z",
      reason: "No pending Review Inbox job is waiting for AI analysis.",
      operator_relevant: true,
    },
  },
};

describe("DataTools", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("shows backend-owned intelligence status as the primary Settings surface", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/ai-status")) {
        return new Response(JSON.stringify(CURRENT_STATUS), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<DataTools apiBase="http://127.0.0.1:8000" />);

    expect(await screen.findByText("Up to date")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "JOLT intelligence" })).toBeInTheDocument();
    expect(screen.getByText("Last update")).toBeInTheDocument();
    expect(screen.getByText("Need update")).toBeInTheDocument();
    expect(screen.getByText(/Discovery reviews keep normal intelligence updates in sync automatically/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/ai-status");
    expect(window.localStorage.length).toBe(0);
  });

  it("keeps deliberate strategy refresh and legacy exports in Advanced only", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/ai-work-package/import") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            imported_sections: ["market_insights", "skills_gaps"],
            review_inbox_imported: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    const onImported = vi.fn();

    render(
      <DataTools
        apiBase="http://127.0.0.1:8000"
        advancedOnly
        onImported={onImported}
      />,
    );

    expect(fetchMock).not.toHaveBeenCalledWith("http://127.0.0.1:8000/api/ai-status");

    const exportLink = screen.getByRole("link", { name: "Export strategy package" });
    expect(exportLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/ai-work-package/export",
    );
    expect(screen.getByLabelText("Import reviewed strategy update")).toBeInTheDocument();
    expect(screen.getByText("Legacy compatibility exports")).toBeInTheDocument();
    expect(screen.getByText(/Normal discovery review already refreshes job review and stale intelligence together/i)).toBeInTheDocument();

    const file = new File(
      [JSON.stringify({
        contract_type: "jolt_ai_work_package_update",
        contract_version: "1.0",
        package_id: "package-1",
        source_context_version: "context-1",
        reviewed_at: "2026-09-01T16:00:00Z",
        review_source: "chatgpt",
        review_version: "test-v1",
        exchanges: [],
        context_patch: {},
        summary: {},
      })],
      "JOLT_AI_UPDATE.json",
      { type: "application/json" },
    );

    fireEvent.change(screen.getByLabelText("Import reviewed strategy update"), {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/ai-work-package/import",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Strategy update imported successfully. Review Inbox updated. 2 intelligence sections imported.",
    );
    expect(onImported).toHaveBeenCalledTimes(1);
    expect(window.localStorage.length).toBe(0);
  });

  it("renders FastAPI validation details instead of object placeholders", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/ai-work-package/import") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            detail: [
              {
                type: "model_attributes_type",
                loc: ["body", "review_inbox", "jobs", 7, "mandatory_requirements", 0],
                msg: "Input should be a valid dictionary or object to extract fields from",
              },
            ],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<DataTools apiBase="http://127.0.0.1:8000" advancedOnly />);

    const file = new File([JSON.stringify({ contract_type: "bad" })], "BAD.json", {
      type: "application/json",
    });
    fireEvent.change(screen.getByLabelText("Import reviewed strategy update"), {
      target: { files: [file] },
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "body → review_inbox → jobs → 7 → mandatory_requirements → 0: Input should be a valid dictionary or object to extract fields from",
    );
    expect(alert).not.toHaveTextContent("[object Object]");
  });
});
