REPO_ROOT = __import__("pathlib").Path(__file__).parents[2]
WORKFLOW = REPO_ROOT / "frontend" / "src" / "ApplicationWorkflow.tsx"
DASHBOARD = REPO_ROOT / "frontend" / "src" / "ApplicationDashboard.tsx"
AUDIT = REPO_ROOT / "tools" / "jolt-stage-reversal-audit.py"


def test_application_workflow_uses_explicit_button_panel() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    audit = AUDIT.read_text(encoding="utf-8")

    assert "const [workflowOpen, setWorkflowOpen] = useState(false);" in source
    assert "function toggleWorkflow()" in source
    assert "aria-expanded={workflowOpen}" in source
    assert "aria-controls={panelId}" in source
    assert 'className="application-workflow-toggle"' in source
    assert 'className="application-workflow-panel"' in source
    assert "{workflowOpen && <div" in source
    assert "if (nextOpen) void loadApplication();" in source
    assert "handleWorkflowToggle" not in source
    assert "onToggle={" not in source
    assert "<summary>Manage application" not in source
    assert 'get_by_role("button", name="Manage application", exact=False)' in audit
    assert 'get_attribute("aria-expanded")' in audit
    assert 'locator(".application-workflow-panel")' in audit
    assert "element.open = true" not in audit


def test_application_timelines_humanize_outcome_codes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert "function formatEventNotes(notes: string)" in workflow
    assert "formatEventNotes(event.notes)" in workflow
    assert "function formatEventNotes(notes: string)" in dashboard
    assert "formatEventNotes(event.notes)" in dashboard
    assert '"rejected_by_employer"' in dashboard
