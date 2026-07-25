from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected {label} marker was not found.")
    return text.replace(old, new, 1)


def patch_frontend_test(root: Path) -> None:
    path = root / "frontend/src/ApplicationDashboard.test.tsx"
    text = path.read_text(encoding="utf-8")
    old = '''  it("disables terminal and unsupported lane moves instead of offering rejected transitions", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    const closedMove = await screen.findByLabelText("Move Support Operations Engineer to lane");
    expect(closedMove).toBeDisabled();
    expect(closedMove.querySelectorAll("option")).toHaveLength(1);
    expect(closedMove).toHaveValue("closed");

    const technicalMove = screen.getByLabelText("Move Production Support Analyst to lane");
    expect(technicalMove).toBeDisabled();
    expect(technicalMove.querySelectorAll("option")).toHaveLength(1);
    expect(technicalMove).toHaveValue("interviewing");
  });
'''
    new = '''  it("offers reversible active-lane corrections and reopening targets", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(pipeline));

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    const closedMove = await screen.findByLabelText("Move Support Operations Engineer to lane");
    expect(closedMove).not.toBeDisabled();
    expect(Array.from(closedMove.querySelectorAll("option")).map((option) => option.value)).toEqual([
      "closed",
      "preparing",
      "applied",
      "interviewing",
      "offer",
    ]);

    const technicalMove = screen.getByLabelText("Move Production Support Analyst to lane");
    expect(technicalMove).not.toBeDisabled();
    expect(Array.from(technicalMove.querySelectorAll("option")).map((option) => option.value)).toEqual([
      "preparing",
      "applied",
      "interviewing",
      "offer",
    ]);
  });
'''
    text = replace_once(text, old, new, "frontend reversible-lane test")
    path.write_text(text, encoding="utf-8")


def patch_playwright(root: Path) -> None:
    path = root / "tools/jolt-sidebar-kanban-playwright-audit.py"
    text = path.read_text(encoding="utf-8")
    old = '''        page.screenshot(path=output_dir / "applications-after-drag.png", full_page=True)

        page.reload(wait_until="networkidle")
        page.get_by_role("button", name="Applications", exact=True).click()
        page.get_by_role("heading", name="Applications", exact=True).wait_for()
        persisted_card = page.locator("section.application-lane-interviewing article.application-card").filter(has_text=title)
        persisted_card.wait_for(timeout=30_000)
        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Moved card is duplicated after reload")
        persisted_card.get_by_role("button", name=f"Open {title}").click()
        page.get_by_role("dialog", name=title).wait_for()
        page.get_by_role("tab", name="Timeline", exact=True).click()
        page.get_by_text("submitted → recruiter screen", exact=True).wait_for(timeout=30_000)
        move_notes = page.get_by_text("Moved on application board from applied to interviewing.", exact=True)
        move_notes.wait_for(timeout=30_000)
        assert_true(move_notes.count() == 1, "The board move produced duplicate timeline events")
        page.screenshot(path=output_dir / "timeline-audited-move.png", full_page=True)
'''
    new = '''        page.screenshot(path=output_dir / "applications-after-forward-drag.png", full_page=True)

        backward_control = moved_card.get_by_label(f"Move {title} to lane")
        backward_control.select_option("applied")
        page.get_by_text(f"{title} moved to Applied.", exact=True).wait_for(timeout=30_000)
        corrected_card = applied_lane.locator(f'article[data-application-id="{fixture["application_id"]}"]')
        corrected_card.wait_for(timeout=30_000)
        assert_true(interviewing_lane.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 0, "Corrected card remains in Interviewing")
        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Corrected card is duplicated after the backward move")
        page.screenshot(path=output_dir / "applications-after-backward-correction.png", full_page=True)

        page.reload(wait_until="networkidle")
        page.get_by_role("button", name="Applications", exact=True).click()
        page.get_by_role("heading", name="Applications", exact=True).wait_for()
        persisted_card = page.locator("section.application-lane-applied article.application-card").filter(has_text=title)
        persisted_card.wait_for(timeout=30_000)
        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Corrected card is duplicated after reload")
        persisted_card.get_by_role("button", name=f"Open {title}").click()
        page.get_by_role("dialog", name=title).wait_for()
        page.get_by_role("tab", name="Timeline", exact=True).click()
        page.get_by_text("submitted → recruiter screen", exact=True).wait_for(timeout=30_000)
        page.get_by_text("recruiter screen → submitted", exact=True).wait_for(timeout=30_000)
        forward_notes = page.get_by_text("Moved on application board from applied to interviewing.", exact=True)
        backward_notes = page.get_by_text("Moved on application board from interviewing to applied.", exact=True)
        forward_notes.wait_for(timeout=30_000)
        backward_notes.wait_for(timeout=30_000)
        assert_true(forward_notes.count() == 1, "The forward board move produced duplicate timeline events")
        assert_true(backward_notes.count() == 1, "The backward board correction produced duplicate timeline events")
        page.screenshot(path=output_dir / "timeline-audited-forward-and-backward.png", full_page=True)
'''
    text = replace_once(text, old, new, "current Playwright move-and-timeline block")
    text = text.replace('"drag_persisted_after_reload": True,', '"forward_and_backward_moves_persisted_after_reload": True,', 1)
    text = text.replace('"timeline_contains_audited_move": True,', '"timeline_contains_audited_forward_and_backward_moves": True,', 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    patch_frontend_test(root)
    patch_playwright(root)
    print("Reversible board validation patch applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
