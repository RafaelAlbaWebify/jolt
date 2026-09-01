import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTools } from "./DataTools";

describe("DataTools", () => {
  afterEach(() => {
    cleanup();
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
  });

  it("imports the returned unified update and refreshes the inbox", async () => {
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

    render(
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
      "Review Inbox updated. 2 intelligence sections imported.",
    );
    expect(onImported).toHaveBeenCalledTimes(1);
  });
});
