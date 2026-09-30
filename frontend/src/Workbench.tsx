import { useState } from "react";

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
  const description = primary?.description ?? "Preferences and data tools.";

  return (
    <div className="shell workspace-shell">
      <aside className="workspace-sidebar" aria-label="JOLT workspace navigation">
        <header className="workspace-header">
          <div className="hero">
            <h1>JOLT</h1>
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
            <section className="settings-workspace" aria-labelledby="settings-data-heading">
              <header className="settings-workspace-header">
                <div>
                  <p className="eyebrow">Preferences & maintenance</p>
                  <h2 id="settings-data-heading">Settings & Data</h2>
                  <p>Keep your search preferences current. Open maintenance tools only when you need them.</p>
                </div>
              </header>

              <div className="settings-primary-grid">
                <details className="settings-primary-card settings-preferences">
                  <summary>
                    <span>
                      <strong>Job search</strong>
                      <small>Roles, locations, work mode, salary and matching preferences</small>
                    </span>
                    <span>Edit preferences</span>
                  </summary>
                  <div className="settings-primary-card-body">
                    <JobPreferences
                      apiBase={API_BASE}
                      active={activeView === "settings"}
                      onEvaluationsRefreshed={() =>
                        setEvaluationRevision((value) => value + 1)
                      }
                    />
                  </div>
                </details>

                <DataTools
                  apiBase={API_BASE}
                  active={activeView === "settings"}
                  onImported={() => setAIImportRevision((value) => value + 1)}
                />
              </div>

              <details className="settings-advanced">
                <summary>
                  <span>
                    <strong>Advanced</strong>
                    <small>Strategy refresh, reviewed decisions, capture history and developer diagnostics</small>
                  </span>
                  <span>Open tools</span>
                </summary>
                <div className="settings-advanced-body">
                  <DataTools
                    apiBase={API_BASE}
                    active={activeView === "settings"}
                    onImported={() => setAIImportRevision((value) => value + 1)}
                    advancedOnly
                  />
                  <RuntimeIdentityPanel apiBase={API_BASE} />
                </div>
              </details>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
