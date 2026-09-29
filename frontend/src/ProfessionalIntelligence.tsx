import { LinkedInJobCaptureLauncher } from "./LinkedInJobCaptureLauncher";
import { LinkedInSearchPortfolio } from "./LinkedInSearchPortfolio";

export type ProfessionalIntelligenceSource = {
  source_id: string;
  label: string;
  category: "profile" | "network" | "career";
  url: string;
  initial_scope: boolean;
  enabled: boolean;
  capture_mode: "supervised_read_only";
};

type Props = {
  apiBase: string;
  active: boolean;
  onAIImported?: () => void;
};

export function ProfessionalIntelligence({ apiBase, active, onAIImported }: Props) {
  return (
    <main className="professional-intelligence" aria-labelledby="job-capture-heading">
      <section className="panel professional-intelligence-overview">
        <div>
          <p className="eyebrow">Job discovery</p>
          <h2 id="job-capture-heading">Capture Jobs</h2>
          <p>Run saved LinkedIn searches and send only new jobs to review.</p>
        </div>
        <div className="professional-safety-boundary professional-readonly-badge" role="note">
          <strong>Read-only</strong>
          <span>Browser capture only</span>
        </div>
      </section>

      <LinkedInSearchPortfolio apiBase={apiBase} active={active} onAIImported={onAIImported} />

      <details className="panel professional-single-capture-fallback">
        <summary>Advanced capture</summary>
        <LinkedInJobCaptureLauncher apiBase={apiBase} active={active} />
      </details>
    </main>
  );
}
