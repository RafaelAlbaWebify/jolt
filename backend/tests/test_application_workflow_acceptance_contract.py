REPO_ROOT = __import__("pathlib").Path(__file__).parents[2]
WORKFLOW = REPO_ROOT / "frontend" / "src" / "ApplicationWorkflow.tsx"
DASHBOARD = REPO_ROOT / "frontend" / "src" / "ApplicationDashboard.tsx"


def test_application_workflow_controls_disclosure_state() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "const [workflowOpen, setWorkflowOpen] = useState(false);" in source
    assert "open={workflowOpen} onToggle={handleToggle}" in source
    assert "setWorkflowOpen(open);" in source


def test_application_timelines_humanize_outcome_codes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert "function formatEventNotes(notes: string)" in workflow
    assert "formatEventNotes(event.notes)" in workflow
    assert "function formatEventNotes(notes: string)" in dashboard
    assert "formatEventNotes(event.notes)" in dashboard
    assert '"rejected_by_employer"' in dashboard
