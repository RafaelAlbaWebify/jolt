from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected {label} marker was not found.")
    return text.replace(old, new, 1)


def patch_backend(root: Path) -> None:
    path = root / "backend/src/jolt/workflow.py"
    text = path.read_text(encoding="utf-8")
    old = '''def transition_application(
    session: Session, application_id: str, request: ApplicationTransitionRequest
) -> ApplicationResponse:
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
    allowed = ALLOWED_TRANSITIONS.get(application.status, set())
    if request.status not in allowed:
        raise ValueError(f"Invalid transition from {application.status} to {request.status}.")
    previous = application.status
    now = utc_now()
    application.status = request.status
    application.updated_at = now
    session.add(
        ApplicationEvent(
            id=str(uuid4()),
            application_id=application.id,
            event_type="status_changed",
            from_status=previous,
            to_status=request.status,
            notes=request.notes,
            occurred_at=now,
        )
    )
    session.commit()
    return _application_response(session, application)
'''
    new = '''def transition_application(
    session: Session, application_id: str, request: ApplicationTransitionRequest
) -> ApplicationResponse:
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError("Application was not found.")
    if request.status == application.status:
        raise ValueError(f"Application is already in {request.status}.")

    active_statuses = {
        "preparing",
        "submitted",
        "acknowledged",
        "recruiter_screen",
        "technical_interview",
        "hiring_manager_interview",
        "final_interview",
        "offer",
    }
    allowed = ALLOWED_TRANSITIONS.get(application.status, set())
    is_correction = request.status in active_statuses and request.status not in allowed
    if request.status not in allowed and not is_correction:
        raise ValueError(f"Invalid transition from {application.status} to {request.status}.")

    previous = application.status
    now = utc_now()
    outcome = session.scalar(select(Outcome).where(Outcome.application_id == application.id))
    reopening = outcome is not None and request.status in active_statuses
    if reopening:
        session.delete(outcome)

    application.status = request.status
    application.updated_at = now
    session.add(
        ApplicationEvent(
            id=str(uuid4()),
            application_id=application.id,
            event_type=(
                "application_reopened"
                if reopening
                else "status_corrected"
                if is_correction
                else "status_changed"
            ),
            from_status=previous,
            to_status=request.status,
            notes=request.notes,
            occurred_at=now,
        )
    )
    session.commit()
    return _application_response(session, application)
'''
    text = replace_once(text, old, new, "transition_application")
    path.write_text(text, encoding="utf-8")


def patch_dashboard(root: Path) -> None:
    path = root / "frontend/src/ApplicationDashboard.tsx"
    text = path.read_text(encoding="utf-8")
    old = '''function availableTargetLanes(item: Opportunity): PipelineLane[] {
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
'''
    new = '''function availableTargetLanes(item: Opportunity): PipelineLane[] {
  const currentLane = laneFor(item);
  if (!item.application_id || !item.application_status) return [currentLane];
  const activeLanes: PipelineLane[] = ["preparing", "applied", "interviewing", "offer"];
  if (currentLane === "closed" || item.outcome_type) return ["closed", ...activeLanes];
  return activeLanes;
}
'''
    text = replace_once(text, old, new, "availableTargetLanes")
    text = replace_once(
        text,
        '''              if (draggedItem && laneFor(draggedItem) !== lane.id) {
                event.preventDefault();
                setDragOverLane(lane.id);
              }''',
        '''              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id) && laneFor(draggedItem) !== lane.id) {
                event.preventDefault();
                setDragOverLane(lane.id);
              }''',
        "drag enter rule",
    )
    text = replace_once(
        text,
        '''              if (draggedItem && laneFor(draggedItem) !== lane.id) event.preventDefault();''',
        '''              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id) && laneFor(draggedItem) !== lane.id) {
                event.preventDefault();
              }''',
        "drag over rule",
    )
    text = replace_once(
        text,
        '''              if (draggedItem) void moveApplication(draggedItem, lane.id);''',
        '''              if (draggedItem && availableTargetLanes(draggedItem).includes(lane.id)) {
                void moveApplication(draggedItem, lane.id);
              }''',
        "drop rule",
    )
    text = replace_once(
        text,
        "Drag cards between lanes or use each card’s Move control. Every move is recorded in history.",
        "Move cards forward or backward to correct the pipeline. Closing still requires a recorded outcome, and every correction is preserved in history.",
        "board guidance",
    )
    path.write_text(text, encoding="utf-8")


def patch_workflow_ui(root: Path) -> None:
    path = root / "frontend/src/ApplicationWorkflow.tsx"
    text = path.read_text(encoding="utf-8")
    for line in [
        '  { value: "rejected", label: "Rejected" },\n',
        '  { value: "withdrawn", label: "Withdrawn" },\n',
        '  { value: "no_response", label: "No response" },\n',
        '  { value: "closed", label: "Closed" },\n',
    ]:
        text = replace_once(text, line, "", f"remove terminal stage {line.strip()}")
    text = replace_once(
        text,
        "Stages can move backward or forward. Reopening keeps the previous outcome in the timeline.",
        "Active stages can move backward or forward as audited corrections. Use a final outcome to close an application; reopening preserves that outcome event in the timeline.",
        "workflow correction guidance",
    )
    path.write_text(text, encoding="utf-8")


def patch_playwright(root: Path) -> None:
    path = root / "tools/jolt-sidebar-kanban-playwright-audit.py"
    text = path.read_text(encoding="utf-8")
    marker = '''        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Moved card is duplicated after the transition")
        page.screenshot(path=output_dir / "applications-after-drag.png", full_page=True)

        page.reload(wait_until="networkidle")'''
    replacement = '''        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Moved card is duplicated after the transition")
        page.screenshot(path=output_dir / "applications-after-drag.png", full_page=True)

        move_select = moved_card.get_by_label(f"Move {title} to lane")
        move_select.select_option("applied")
        page.get_by_text(f"{title} moved to Applied.", exact=True).wait_for(timeout=30_000)
        corrected_card = applied_lane.locator(f'article[data-application-id="{fixture["application_id"]}"]')
        corrected_card.wait_for(timeout=30_000)
        assert_true(interviewing_lane.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 0, "Corrected card remains in Interviewing")
        assert_true(page.locator(f'article[data-application-id="{fixture["application_id"]}"]').count() == 1, "Corrected card is duplicated")
        page.screenshot(path=output_dir / "applications-after-backward-correction.png", full_page=True)

        page.reload(wait_until="networkidle")'''
    text = replace_once(text, marker, replacement, "Playwright backward correction")
    text = replace_once(
        text,
        '''        persisted_card = page.locator("section.application-lane-interviewing article.application-card").filter(has_text=title)''',
        '''        persisted_card = page.locator("section.application-lane-applied article.application-card").filter(has_text=title)''',
        "Playwright persisted lane",
    )
    text = replace_once(
        text,
        '''        page.get_by_text("Moved on application board from applied to interviewing.", exact=True).wait_for(timeout=30_000)
        move_notes = page.get_by_text("Moved on application board from applied to interviewing.", exact=True)
        move_notes.wait_for(timeout=30_000)
        assert_true(move_notes.count() == 1, "The board move produced duplicate timeline events")''',
        '''        forward_notes = page.get_by_text("Moved on application board from applied to interviewing.", exact=True)
        forward_notes.wait_for(timeout=30_000)
        backward_notes = page.get_by_text("Moved on application board from interviewing to applied.", exact=True)
        backward_notes.wait_for(timeout=30_000)
        assert_true(forward_notes.count() == 1, "The forward board move produced duplicate timeline events")
        assert_true(backward_notes.count() == 1, "The backward correction produced duplicate timeline events")''',
        "Playwright timeline correction",
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    patch_backend(root)
    patch_dashboard(root)
    patch_workflow_ui(root)
    patch_playwright(root)
    print("Reversible application board patch applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
