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
type WorkbenchView = "opportunities" | "applications" | "market" | "linkedin" | "professional";

const VIEWS: Array<{ id: WorkbenchView; label: string; description: string }> = [
  { id: "professional", label: "Capture & Evidence", description: "Start user-present capture from trusted sources and review local evidence batches." },
  { id: "opportunities", label: "Review Inbox", description: "Review newly captured or manually added jobs before they move forward." },
  { id: "applications", label: "Application Pipeline", description: "Track applications, interviews, offers, outcomes, and archived cards." },
  { id: "market", label: "Market Insights", description: "Learn from active retained jobs: roles, skills, locations, salaries, and fit." },
  { id: "linkedin", label: "LinkedIn Command Center", description: "Improve profile positioning, network quality, activity, and outreach from user-approved LinkedIn evidence." },
];

const WORKFLOW_STEPS = [
  "Capture / intake",
  "Review",
  "Apply / track",
  "Improve presence",
  "Learn from market",
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
            <p>Turn job evidence into review decisions, application tracking, market learning, and public career positioning.</p>
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
          <div className="workspace-view workspace-view-opportunities" hidden={activeView !== "opportunities"}>
            <App sidebarToolsTarget={hiddenReviewInboxToolsTarget} />
          </div>
          <div className="workspace-view workspace-view-applications" hidden={activeView !== "applications"}>
            <ApplicationDashboard apiBase={API_BASE} active={activeView === "applications"} />
          </div>
          <div className="workspace-view workspace-view-market" hidden={activeView !== "market"}>
            <MarketIntelligence apiBase={API_BASE} active={activeView === "market"} />
          </div>
          <div className="workspace-view workspace-view-linkedin" hidden={activeView !== "linkedin"}>
            <LinkedInCommandCenter apiBase={API_BASE} active={activeView === "linkedin"} />
          </div>
          <div className="workspace-view workspace-view-professional" hidden={activeView !== "professional"}>
            <ProfessionalIntelligence apiBase={API_BASE} active={activeView === "professional"} />
          </div>
        </div>
      </main>
    </div>
  );
}
