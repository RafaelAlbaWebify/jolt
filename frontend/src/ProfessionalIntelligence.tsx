import { LinkedInJobCaptureLauncher } from "./LinkedInJobCaptureLauncher";

type Props = {
  apiBase: string;
  active: boolean;
};

export function ProfessionalIntelligence({ apiBase, active }: Props) {
  return (
    <main className="professional-intelligence" aria-labelledby="job-capture-heading">
      <section className="panel professional-intelligence-overview">
        <div>
          <p className="eyebrow">Job discovery</p>
          <h2 id="job-capture-heading">Capture Jobs</h2>
          <p>
            Capture a LinkedIn job search in a visible browser. Verified jobs are deduplicated,
            evaluated, and sent to Review Inbox and Market Insights.
          </p>
        </div>
        <div className="professional-safety-boundary" role="note">
          <strong>Read-only boundary</strong>
          <span>No messages, reactions, applications, invitations, or account changes.</span>
        </div>
      </section>

      <LinkedInJobCaptureLauncher apiBase={apiBase} active={active} />

      <section className="panel" aria-labelledby="profile-capture-location-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">LinkedIn profile evidence</p>
            <h2 id="profile-capture-location-heading">Profile capture has moved</h2>
            <p>
              Profile, experience, skills, certifications, and activity belong in LinkedIn Profile.
              This workspace is intentionally limited to job discovery.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
