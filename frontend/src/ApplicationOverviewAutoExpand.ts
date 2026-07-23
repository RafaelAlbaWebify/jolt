const expandedWorkflows = new WeakSet<HTMLDetailsElement>();

function expandVisibleOverviewWorkflow(root: ParentNode = document) {
  const workflow = root.querySelector<HTMLDetailsElement>(
    ".application-detail-body .application-workflow:not([open])",
  );
  if (!workflow || expandedWorkflows.has(workflow)) return;

  expandedWorkflows.add(workflow);
  const summary = workflow.querySelector<HTMLElement>(":scope > summary");
  summary?.click();
}

if (typeof document !== "undefined") {
  const observer = new MutationObserver(() => expandVisibleOverviewWorkflow());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.requestAnimationFrame(() => expandVisibleOverviewWorkflow());
}
