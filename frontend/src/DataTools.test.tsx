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

  it("presents strategy updates as an advanced workflow and reads status from JOLT", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/ai-status")) {
        return new Response(JSON.stringify(EMPTY_STATUS), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<DataTools apiBase="http://127.0.0.1:8000" />);

    expect(await screen.findByText("No analysis yet")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/ai-status");

    const exportLink = screen.getByRole("link", { name: "Export strategy update package" });
    expect(exportLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/ai-work-package/export",
    );
    expect(exportLink).toHaveAttribute("download", "JOLT_AI_WORK_PACKAGE.json");
    expect(exportLink).toHaveAttribute(
      "title",
      expect.stringContaining("full strategy context"),
    );
    expect(screen.getByLabelText("Import reviewed strategy update")).toBeInTheDocument();
    expect(screen.getByText("Legacy compatibility exports")).toBeInTheDocument();
    expect(
      screen.getByText(/Normal discovery review now updates job review and intelligence together/i),
    ).toBeInTheDocument();
    expect(window.localStorage.length).toBe(0);
  });

  it("refreshes backend intelligence status after importing a unified update", async () => {
    const onImported = vi.fn();
    let statusReads = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/ai-status")) {
        statusReads += 1;
        return new Response(
          JSON.stringify(statusReads === 1 ? EMPTY_STATUS : CURRENT_STATUS),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      if (url.endsWith("/api/ai-work-package/import") && method === "POST") {
        return new Response(
          JSON.stringify({
            imported_sections: ["market_insights", "skills_gaps"],
            review_inbox_imported: true,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      return new Response(JSON.stringify([]), { status: 200 });
    });

    const { unmount } = render(
      <DataTools
        apiBase="http://127.0.0.1:8000"
        onImported={onImported}
      />,
    );

    expect(await screen.findByText("No analysis yet")).toBeInTheDocument();

    const file = new File(
      [
        JSON.stringify({
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
        }),
      ],
      "JOLT_AI_UPDATE.json",
      { type: "application/json" },
    );

    fireEvent.change(screen.getByLabelText("Import reviewed strategy update"), {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/api/ai-work-package/import",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Strategy update imported successfully. Review Inbox updated. 2 intelligence sections imported.",
    );
    expect(await screen.findByText("Up to date")).toBeInTheDocument();
    expect(screen.getByText("6", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("current", { selector: "strong" })).toBeInTheDocument();
    expect(onImported).toHaveBeenCalledTimes(1);
    expect(window.localStorage.length).toBe(0);

    unmount();

    render(<DataTools apiBase="http://127.0.0.1:8000" />);
    expect(await screen.findByText("Up to date")).toBeInTheDocument();
    expect(window.localStorage.length).toBe(0);
  });

  it("renders FastAPI validation details instead of object placeholders", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/ai-status")) {
        return new Response(JSON.stringify(EMPTY_STATUS), { status: 200 });
      }
      if (url.endsWith("/api/ai-work-package/import") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            detail: [
              {
                type: "model_attributes_type",
                loc: ["body", "review_inbox", "jobs", 7, "mandatory_requirements", 0],
                msg: "Input should be a valid dictionary or object to extract fields from",
              },
              {
                type: "model_attributes_type",
                loc: ["body", "review_inbox", "jobs", 24, "mandatory_requirements", 0],
                msg: "Input should be a valid dictionary or object to extract fields from",
              },
            ],
          }),
          {
            status: 422,
            headers: { "Content-Type": "application/json" },
          },
        );
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<DataTools apiBase="http://127.0.0.1:8000" />);
    await screen.findByText("No analysis yet");

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
    expect(alert).toHaveTextContent(
      "body → review_inbox → jobs → 24 → mandatory_requirements → 0: Input should be a valid dictionary or object to extract fields from",
    );
    expect(alert).not.toHaveTextContent("[object Object]");
  });
});
