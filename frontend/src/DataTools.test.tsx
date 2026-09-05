import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTools } from "./DataTools";

describe("DataTools", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("makes the unified AI work package the primary workflow", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    render(<DataTools apiBase="http://127.0.0.1:8000" />);

    const exportLink = screen.getByRole("link", { name: "Export AI work package" });
    expect(exportLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/ai-work-package/export",
    );
    expect(exportLink).toHaveAttribute("download", "JOLT_AI_WORK_PACKAGE.json");
    expect(screen.getByLabelText("Import AI update")).toBeInTheDocument();
    expect(screen.getByText("Advanced / compatibility exports")).toBeInTheDocument();
    expect(
      screen.getByText(/one JOLT work package, analyze it in ChatGPT/i),
    ).toBeInTheDocument();
    expect(screen.getByText("No import yet")).toBeInTheDocument();
  });

  it("imports the returned unified update and shows a persistent receipt", async () => {
    const onImported = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          imported_sections: ["market_insights", "skills_gaps"],
          review_inbox_imported: true,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const { unmount } = render(
      <DataTools
        apiBase="http://127.0.0.1:8000"
        onImported={onImported}
      />,
    );

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

    fireEvent.change(screen.getByLabelText("Import AI update"), {
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
      "AI update imported successfully. Review Inbox updated. 2 intelligence sections imported.",
    );
    expect(screen.getByText("Imported")).toBeInTheDocument();
    expect(screen.getByText("JOLT_AI_UPDATE.json")).toBeInTheDocument();
    expect(screen.getByText("market_insights, skills_gaps")).toBeInTheDocument();
    expect(screen.getByText("Updated", { selector: "strong" })).toBeInTheDocument();
    expect(onImported).toHaveBeenCalledTimes(1);

    unmount();
    render(<DataTools apiBase="http://127.0.0.1:8000" />);
    expect(screen.getByText("Imported")).toBeInTheDocument();
    expect(screen.getByText("JOLT_AI_UPDATE.json")).toBeInTheDocument();
  });

  it("renders FastAPI validation details instead of object placeholders", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
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
      ),
    );

    render(<DataTools apiBase="http://127.0.0.1:8000" />);

    const file = new File([JSON.stringify({ contract_type: "bad" })], "BAD.json", {
      type: "application/json",
    });
    fireEvent.change(screen.getByLabelText("Import AI update"), {
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
