import { useMemo, useState } from "react";

import { App } from "./App";
import { ApplicationDashboard } from "./ApplicationDashboard";
import { DataTools } from "./DataTools";
import { JobPreferences } from "./JobPreferences";
import { LinkedInAIAnalysisStatus } from "./LinkedInAIAnalysisStatus";
import { LinkedInCommandCenter } from "./LinkedInCommandCenter";
import { MarketIntelligence } from "./MarketIntelligence";
import { ProfessionalIntelligence } from "./ProfessionalIntelligence";
import { RuntimeIdentityPanel, RuntimeStalenessGuard } from "./RuntimeIdentity";
import "./Workbench.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
type PrimaryView = "professional" | "opportunities" | "applications" | "linkedin" | "market";
type WorkbenchView = PrimaryView | "settings";

const PRIMARY_VIEWS: Array<{ id: PrimaryView; label: string; description: string }> = [
  { id: "professional", label: "Capture Jobs", description: "Run your LinkedIn job searches and bring new opportunities into JOLT." },
  { id: "opportunities", label: "Review Inbox", description: "Review new jobs and decide which ones deserve your time." },
  { id: "applications", label: "Applications", description: "Track preparation, submissions, interviews, offers, outcomes, and hidden applications." },
  { id: "linkedin", label: "LinkedIn Profile", description: "Refresh profile data and work through concrete profile improvements." },
  { id: "market", label: "Market Insights", description: "Use your job-search data to improve search strategy and preparation priorities." },
];


export function Workbench() {
  const [activeView, setActiveView] = useState<WorkbenchView>("professional");
  const [evaluationRevision, setEvaluationRevision] = useState(0);
  const [aiImportRevision, setAIImportRevision] = useState(0);
  const primary = PRIMARY_VIEWS.find((item) => item.id === activeView);
  const description = primary?.description ?? "Preferences, data exchange, and advanced diagnostics.";
  const hiddenReviewInboxToolsTarget = useMemo(() => document.createElement("div"), []);

  return (
    <div className="shell workspace-shell">
      <aside className="workspace-sidebar" aria-label="JOLT workspace navigation">
        <header className="workspace-header">
          <div className="hero">
            <p className="eyebrow">Job Opportunity Learning & Tracking</p>
            <h1>JOLT</h1>
            <p>Find suitable jobs, decide what to pursue, track applications, and improve your market positioning.</p>
          </div>

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
        <RuntimeStalenessGuard apiBase={API_BASE} />
        <div className="workspace-view-stack">
          <div className="workspace-view workspace-view-professional" hidden={activeView !== "professional"}>
            <ProfessionalIntelligence
              apiBase={API_BASE}
              active={activeView === "professional"}
              onAIImported={() => setEvaluationRevision((value) => value + 1)}
            />
          </div>
          <div className="workspace-view workspace-view-opportunities" hidden={activeView !== "opportunities"}>
            <App
              sidebarToolsTarget={hiddenReviewInboxToolsTarget}
              evaluationRevision={evaluationRevision}
            />
          </div>
          <div className="workspace-view workspace-view-applications" hidden={activeView !== "applications"}>
            <ApplicationDashboard apiBase={API_BASE} active={activeView === "applications"} />
          </div>
          <div className="workspace-view workspace-view-linkedin" hidden={activeView !== "linkedin"}>
            <LinkedInCommandCenter apiBase={API_BASE} active={activeView === "linkedin"} />
            <LinkedInAIAnalysisStatus
              apiBase={API_BASE}
              active={activeView === "linkedin"}
              importRevision={aiImportRevision}
            />
          </div>
          <div className="workspace-view workspace-view-market" hidden={activeView !== "market"}>
            <MarketIntelligence apiBase={API_BASE} active={activeView === "market"} />
          </div>
          <div className="workspace-view workspace-view-settings" hidden={activeView !== "settings"}>
            <section className="panel" aria-labelledby="settings-data-heading">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Job strategy</p>
                  <h2 id="settings-data-heading">Settings & Data</h2>
                  <p>
                    Set your job-search preferences. JOLT refreshes job matching without changing
                    your review decisions or application records.
                  </p>
                </div>
              </div>
              <details className="settings-preferences">
                <summary>Job Search Preferences</summary>
                <JobPreferences
                  apiBase={API_BASE}
                  active={activeView === "settings"}
                  onEvaluationsRefreshed={() =>
                    setEvaluationRevision((value) => value + 1)
                  }
                />
              </details>
            </section>

            <section className="panel" aria-labelledby="operational-data-heading">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Advanced</p>
                  <h2 id="operational-data-heading">Data & Diagnostics</h2>
                  <p>
                    AI exchange, compatibility tools, runtime checks, and technical diagnostics.
                  </p>
                </div>
              </div>
              <DataTools
                apiBase={API_BASE}
                onImported={() => setAIImportRevision((value) => value + 1)}
              />
              <RuntimeIdentityPanel apiBase={API_BASE} />
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
