from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected {label} marker was not found.")
    return text.replace(old, new, 1)


def patch_dashboard(root: Path) -> None:
    path = root / "frontend/src/ApplicationDashboard.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'import { useCallback, useEffect, useMemo, useState } from "react";',
        'import { useCallback, useEffect, useMemo, useRef, useState } from "react";',
        "React import",
    )
    text = replace_once(
        text,
        "function nextAction(item: Opportunity) {",
        '''function opportunityIdentity(item: Opportunity) {
  return item.application_id ? `application:${item.application_id}` : `posting:${item.posting_id}`;
}

function deduplicateOpportunities(items: Opportunity[]) {
  const unique = new Map<string, Opportunity>();
  for (const item of items) {
    const identity = opportunityIdentity(item);
    if (!unique.has(identity)) unique.set(identity, item);
  }
  return [...unique.values()];
}

function availableTargetLanes(item: Opportunity): PipelineLane[] {
  const currentLane = laneFor(item);
  if (!item.application_id || !item.application_status || item.outcome_type) return [currentLane];
  const directTargets: Partial<Record<ApplicationStatus, PipelineLane[]>> = {
    preparing: ["applied", "closed"],
    submitted: ["interviewing"],
    acknowledged: ["interviewing"],
    hiring_manager_interview: ["offer"],
    final_interview: ["offer"],
    offer: ["closed"],
  };
  return [currentLane, ...(directTargets[item.application_status] ?? [])].filter(
    (lane, index, lanes) => lanes.indexOf(lane) === index,
  );
}

function nextAction(item: Opportunity) {''',
        "board helper insertion",
    )
    text = replace_once(
        text,
        '  const [moveNotice, setMoveNotice] = useState("");',
        '  const [moveNotice, setMoveNotice] = useState("");\n  const movingApplicationIds = useRef(new Set<string>());',
        "move state",
    )
    text = replace_once(
        text,
        '    setOpportunities((await response.json()) as Opportunity[]);',
        '    const rows = (await response.json()) as Opportunity[];\n    setOpportunities(deduplicateOpportunities(rows));',
        "application index refresh",
    )
    text = replace_once(
        text,
        '''  async function moveApplication(item: Opportunity, targetLane: PipelineLane) {
    if (!item.application_id || laneFor(item) === targetLane || busy) return;
    setBusy(true);''',
        '''  async function moveApplication(item: Opportunity, targetLane: PipelineLane) {
    if (!item.application_id || laneFor(item) === targetLane || busy) return;
    if (!availableTargetLanes(item).includes(targetLane)) {
      setError(`The application cannot move directly from ${laneFor(item)} to ${targetLane}.`);
      return;
    }
    if (movingApplicationIds.current.has(item.application_id)) return;
    movingApplicationIds.current.add(item.application_id);
    setBusy(true);''',
        "move guard",
    )
    text = replace_once(
        text,
        '''    } finally {
      setBusy(false);
      setDraggedPostingId(null);
      setDragOverLane(null);
    }
  }''',
        '''    } finally {
      if (item.application_id) movingApplicationIds.current.delete(item.application_id);
      setBusy(false);
      setDraggedPostingId(null);
      setDragOverLane(null);
    }
  }''',
        "move cleanup",
    )
    text = replace_once(
        text,
        '''                    key={opportunity.posting_id}
                    draggable={Boolean(opportunity.application_id) && !busy}
                    onDragStart={(event) => {
                      if (!opportunity.application_id) {''',
        '''                    key={opportunityIdentity(opportunity)}
                    data-application-id={opportunity.application_id ?? undefined}
                    data-posting-id={opportunity.posting_id}
                    draggable={availableTargetLanes(opportunity).length > 1 && !busy}
                    onDragStart={(event) => {
                      if (!opportunity.application_id || availableTargetLanes(opportunity).length <= 1) {''',
        "card identity",
    )
    text = replace_once(
        text,
        '''                          disabled={!opportunity.application_id || busy}
                          onChange={(event) => void moveApplication(opportunity, event.target.value as PipelineLane)}
                        >
                          {LANES.map((target) => (
                            <option key={target.id} value={target.id}>
                              {target.label}
                            </option>
                          ))}''',
        '''                          disabled={availableTargetLanes(opportunity).length <= 1 || busy}
                          onChange={(event) => void moveApplication(opportunity, event.target.value as PipelineLane)}
                        >
                          {availableTargetLanes(opportunity).map((targetLane) => {
                            const target = LANES.find((lane) => lane.id === targetLane)!;
                            return (
                              <option key={target.id} value={target.id}>
                                {target.label}
                              </option>
                            );
                          })}''',
        "move selector",
    )
    path.write_text(text, encoding="utf-8")


def patch_tests(root: Path) -> None:
    path = root / "frontend/src/ApplicationDashboard.test.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    expect(screen.getByLabelText("Interviewing count")).toHaveTextContent("2");',
        '    expect(screen.getByLabelText("Applied count")).toHaveTextContent("0");\n    expect(screen.getByLabelText("Interviewing count")).toHaveTextContent("2");\n    expect(screen.getAllByRole("button", { name: "Open Application Support Engineer" })).toHaveLength(1);',
        "move assertion",
    )
    marker = '  it("opens one application in a dedicated workspace instead of expanding it inline", async () => {'
    tests = '''  it("renders one card per stable application identity when the API repeats a row", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([...pipeline, { ...submittedOpportunity }]));

    render(<ApplicationDashboard apiBase="http://127.0.0.1:8000" active />);

    expect(await screen.findAllByRole("button", { name: "Open Application Support Engineer" })).toHaveLength(1);
    expect(screen.getByLabelText("Applied count")).toHaveTextContent("1");
  });

  it("disables terminal and unsupported lane moves instead of offering rejected transitions", async () => {
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
    text = replace_once(text, marker, tests + marker, "test insertion")
    path.write_text(text, encoding="utf-8")


def patch_playwright(root: Path) -> None:
    path = root / "tools/jolt-sidebar-kanban-playwright-audit.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''        card = page.locator("article.application-card").filter(has_text=title)
        card.wait_for(timeout=30_000)
        assert_true(card.get_attribute("draggable") == "true", "Prepared audit card is not draggable")
        interviewing_lane = page.locator("section.application-lane-interviewing")
        card.drag_to(interviewing_lane)''',
        '''        card = page.locator(f'article.application-card[data-application-id="{fixture["application_id"]}"]')
        assert_true(card.count() == 1, "Audit application is not rendered exactly once before the move")
        card.wait_for(timeout=30_000)
        assert_true(card.get_attribute("draggable") == "true", "Prepared audit card is not draggable")
        applied_lane = page.locator("section.application-lane-applied")
        interviewing_lane = page.locator("section.application-lane-interviewing")
        assert_true(applied_lane.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Audit card is not in Applied before the move")
        card.drag_to(interviewing_lane)''',
        "Playwright pre-move identity",
    )
    text = replace_once(
        text,
        '''        interviewing_lane.locator("article.application-card").filter(has_text=title).wait_for()
        page.screenshot''',
        '''        moved_card = interviewing_lane.locator(f'article[data-application-id="{fixture["application_id"]}"]')
        moved_card.wait_for()
        assert_true(applied_lane.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 0, "Moved card remains in the source lane")
        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Moved card is duplicated after the transition")
        page.screenshot''',
        "Playwright post-move identity",
    )
    text = replace_once(
        text,
        '''        persisted_card.wait_for(timeout=30_000)
        persisted_card.get_by_role''',
        '''        persisted_card.wait_for(timeout=30_000)
        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Moved card is duplicated after reload")
        persisted_card.get_by_role''',
        "Playwright reload identity",
    )
    text = replace_once(
        text,
        '''        page.get_by_text("Moved on application board from applied to interviewing.", exact=True).wait_for(timeout=30_000)
        page.screenshot''',
        '''        move_notes = page.get_by_text("Moved on application board from applied to interviewing.", exact=True)
        move_notes.wait_for(timeout=30_000)
        assert_true(move_notes.count() == 1, "The board move produced duplicate timeline events")
        page.screenshot''',
        "Playwright timeline uniqueness",
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    patch_dashboard(root)
    patch_tests(root)
    patch_playwright(root)
    print("Application board hardening patch applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
