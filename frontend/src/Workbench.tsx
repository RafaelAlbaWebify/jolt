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
type PrimaryView = "professional" | "opportunities" | "applications" | "linkedin" | "market";
type WorkbenchView = PrimaryView | "settings";

const PRIMARY_VIEWS: Array<{ id: PrimaryView; label: string; description: string }> = [
  { id: "professional", label: "Capture Jobs", description: "Capture LinkedIn job searches and send verified opportunities into JOLT." },
  { id: "opportunities", label: "Review Inbox", description: "Review captured or manually added jobs and decide what moves forward." },
  { id: "applications", label: "Applications", description: "Track preparation, submissions, interviews, offers, outcomes, and archived records." },
  { id: "linkedin", label: "LinkedIn Profile", description: "Refresh profile evidence and manage concrete profile improvements." },
  { id: "market", label: "Market Insights", description: "Use retained job evidence to improve search strategy and preparation priorities." },
];

const WORKFLOW_STEPS = ["Capture jobs", "Review opportunities", "Prepare and apply", "Track outcomes", "Learn from the market"];

export function Workbench() {
  const [activeView, setActiveView] = useState<WorkbenchView>("professional");
  const primary = PRIMARY_VIEWS.find((item) => item.id === activeView);
  const description = primary?.description ?? "Manage capture history, reviewed decisions, exports, and developer diagnostics.";
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
            {PRIMARY_VIEWS.map((item) => (
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

          <button
            type="button"
            className={activeView === "settings" ? "workspace-nav-active" : "secondary"}
            aria-pressed={activeView === "settings"}
            onClick={() => setActiveView("settings")}
          >
            Settings & Data
          </button>
          <p className="workspace-description">{description}</p>
        </header>
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
          <div className="workspace-view workspace-view-settings" hidden={activeView !== "settings"}>
            <section className="panel" aria-labelledby="settings-data-heading">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Secondary utility</p>
                  <h2 id="settings-data-heading">Settings & Data</h2>
                  <p>Operational history, reviewed decisions, exports, and diagnostics live here instead of competing with daily work.</p>
                </div>
              </div>
              <DataTools apiBase={API_BASE} />
              <RuntimeIdentityPanel apiBase={API_BASE} />
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
