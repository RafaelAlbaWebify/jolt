REPO_ROOT = __import__("pathlib").Path(__file__).parents[2]
WORKFLOW = REPO_ROOT / "frontend" / "src" / "ApplicationWorkflow.tsx"
DASHBOARD = REPO_ROOT / "frontend" / "src" / "ApplicationDashboard.tsx"


def test_application_workflow_uses_native_disclosure_state() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "function handleWorkflowToggle" in source
    assert "event.currentTarget.open" in source
    assert "if (event.currentTarget.open) void loadApplication();" in source
    assert 'onToggle={handleWorkflowToggle}' in source
    assert "const [workflowOpen, setWorkflowOpen]" not in source
    assert "event.preventDefault();" not in source
    assert "open={workflowOpen}" not in source
    assert "<summary>Manage application" in source


def test_application_timelines_humanize_outcome_codes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert "function formatEventNotes(notes: string)" in workflow
    assert "formatEventNotes(event.notes)" in workflow
    assert "function formatEventNotes(notes: string)" in dashboard
    assert "formatEventNotes(event.notes)" in dashboard
    assert '"rejected_by_employer"' in dashboard
