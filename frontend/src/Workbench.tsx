import { useMemo, useState } from "react";

import { App } from "./App";
import { ApplicationDashboard } from "./ApplicationDashboard";
import { DataTools } from "./DataTools";
import { LinkedInCommandCenter } from "./LinkedInCommandCenter";
import { MarketIntelligence } from "./MarketIntelligence";
import { ProfessionalIntelligence } from "./ProfessionalIntelligence";
import { RuntimeIdentityPanel } from "./RuntimeIdentity";
import "./Workbench.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
type WorkbenchView = "professional" | "opportunities" | "applications" | "linkedin" | "market";

const VIEWS: Array<{ id: WorkbenchView; label: string; description: string }> = [
  {
    id: "professional",
    label: "Capture Jobs",
    description: "Capture LinkedIn job searches and send verified opportunities into JOLT.",
  },
  {
    id: "opportunities",
    label: "Review Inbox",
    description: "Review captured or manually added job opportunities before they move forward.",
  },
  {
    id: "applications",
    label: "Applications",
    description: "Track preparation, submissions, interviews, offers, outcomes, and archived records.",
  },
  {
    id: "linkedin",
    label: "LinkedIn Profile",
    description: "Capture and improve profile positioning, skills, activity, and professional presence.",
  },
  {
    id: "market",
    label: "Market Insights",
    description: "Learn from active retained jobs: roles, skills, locations, salaries, and fit.",
  },
];

const WORKFLOW_STEPS = [
  "Capture jobs",
  "Review opportunities",
  "Prepare and apply",
  "Track outcomes",
  "Learn from the market",
];

export function Workbench() {
  const [activeView, setActiveView] = useState<WorkbenchView>("professional");
  const view = VIEWS.find((item) => item.id === activeView) ?? VIEWS[0];
  const hiddenReviewInboxToolsTarget = useMemo(() => document.createElement("div"), []);

  return (
    <div className="shell workspace-shell">
      <aside className="workspace-sidebar" aria-label="JOLT workspace navigation">
        <header className="workspace-header">
          <div className="hero">
            <p className="eyebrow">Job Opportunity Learning & Tracking</p>
            <h1>JOLT</h1>
            <p>Capture suitable jobs, make review decisions, track applications, and improve your market positioning.</p>
          </div>

          <ol className="workspace-flow" aria-label="JOLT workflow order">
            {WORKFLOW_STEPS.map((step) => <li key={step}>{step}</li>)}
          </ol>

          <nav className="workspace-nav" aria-label="JOLT workspace views">
            {VIEWS.map((item) => (
              <button
                type="button"
                className={activeView === item.id ? "workspace-nav-active" : "secondary"}
                aria-pressed={activeView === item.id}
                onClick={() => setActiveView(item.id)}
                key={item.id}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <p className="workspace-description">{view.description}</p>
        </header>

        <RuntimeIdentityPanel apiBase={API_BASE} />

        <div className="workspace-sidebar-tools" aria-label="Global data tools">
          <DataTools apiBase={API_BASE} />
        </div>
      </aside>

      <main className="workspace-content">
        <div className="workspace-view-stack">
          <div className="workspace-view workspace-view-professional" hidden={activeView !== "professional"}>
            <ProfessionalIntelligence apiBase={API_BASE} active={activeView === "professional"} />
          </div>
          <div className="workspace-view workspace-view-opportunities" hidden={activeView !== "opportunities"}>
            <App sidebarToolsTarget={hiddenReviewInboxToolsTarget} />
          </div>
          <div className="workspace-view workspace-view-applications" hidden={activeView !== "applications"}>
            <ApplicationDashboard apiBase={API_BASE} active={activeView === "applications"} />
          </div>
          <div className="workspace-view workspace-view-linkedin" hidden={activeView !== "linkedin"}>
            <LinkedInCommandCenter apiBase={API_BASE} active={activeView === "linkedin"} />
          </div>
          <div className="workspace-view workspace-view-market" hidden={activeView !== "market"}>
            <MarketIntelligence apiBase={API_BASE} active={activeView === "market"} />
          </div>
        </div>
      </main>
    </div>
  );
}
