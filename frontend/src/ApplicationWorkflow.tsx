import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

export type ApplicationStatus =
  | "preparing"
  | "submitted"
  | "acknowledged"
  | "recruiter_screen"
  | "technical_interview"
  | "hiring_manager_interview"
  | "final_interview"
  | "offer"
  | "rejected"
  | "withdrawn"
  | "no_response"
  | "closed";

type OutcomeType =
  | "rejected_by_employer"
  | "withdrawn_by_user"
  | "no_response"
  | "offer_declined"
  | "offer_accepted"
  | "role_closed";

type ApplicationEvent = {
  event_id: string;
  event_type: string;
  from_status: string;
  to_status: string;
  notes: string;
  occurred_at: string;
};

type ApplicationData = {
  application_id: string;
  posting_id: string;
  status: ApplicationStatus;
  application_url: string;
  resume_used: string;
  notes: string;
  outcome_type: OutcomeType | null;
  events: ApplicationEvent[];
};

type Props = {
  apiBase: string;
  postingId: string;
  title: string;
  reviewDecision: string | null;
  applicationId?: string | null;
  applicationStatus?: ApplicationStatus | null;
  disabled: boolean;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

type StageAction = { status: ApplicationStatus; label: string; guidance: string };

const APPLICATION_STAGES: { value: ApplicationStatus; label: string }[] = [
  { value: "preparing", label: "Preparing" },
  { value: "submitted", label: "Applied" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "recruiter_screen", label: "Recruiter screen" },
  { value: "technical_interview", label: "Technical interview" },
  { value: "hiring_manager_interview", label: "Hiring-manager interview" },
  { value: "final_interview", label: "Final interview" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
  { value: "no_response", label: "No response" },
  { value: "closed", label: "Closed" },
];

const STAGE_ACTIONS: Partial<Record<ApplicationStatus, StageAction[]>> = {
  preparing: [{ status: "submitted", label: "Record external submission", guidance: "Use this after you submit on LinkedIn or the employer site." }],
  submitted: [
    { status: "acknowledged", label: "Record acknowledgement", guidance: "The employer confirmed receipt." },
    { status: "recruiter_screen", label: "Record recruiter screen", guidance: "A recruiter conversation is scheduled or completed." },
  ],
  acknowledged: [{ status: "recruiter_screen", label: "Record recruiter screen", guidance: "A recruiter conversation is scheduled or completed." }],
  recruiter_screen: [
    { status: "technical_interview", label: "Record technical interview", guidance: "A technical assessment or interview is scheduled or completed." },
    { status: "hiring_manager_interview", label: "Record hiring-manager interview", guidance: "The process moved directly to the hiring manager." },
  ],
  technical_interview: [
    { status: "hiring_manager_interview", label: "Record hiring-manager interview", guidance: "The next stage is with the hiring manager." },
    { status: "final_interview", label: "Record final interview", guidance: "The next stage is the final interview." },
  ],
  hiring_manager_interview: [
    { status: "final_interview", label: "Record final interview", guidance: "The process has reached its final interview." },
    { status: "offer", label: "Record offer", guidance: "An offer has been made." },
  ],
  final_interview: [{ status: "offer", label: "Record offer", guidance: "An offer has been made." }],
};

const GENERAL_OUTCOMES: { value: OutcomeType; label: string }[] = [
  { value: "rejected_by_employer", label: "Rejected by employer" },
  { value: "withdrawn_by_user", label: "Withdrawn by me" },
  { value: "no_response", label: "No response" },
  { value: "role_closed", label: "Role closed" },
];
const OFFER_OUTCOMES: { value: OutcomeType; label: string }[] = [
  { value: "offer_accepted", label: "Offer accepted" },
  { value: "offer_declined", label: "Offer declined" },
];
const OUTCOME_CODES = [...GENERAL_OUTCOMES, ...OFFER_OUTCOMES].map((item) => item.value);

function label(value: string) { return value.replaceAll("_", " "); }
function formatEventNotes(notes: string) {
  return OUTCOME_CODES.reduce((formatted, code) => formatted.replaceAll(code, label(code)), notes);
}
function stageGuidance(status: ApplicationStatus | null | undefined) {
  switch (status) {
    case "preparing": return "Finish the application materials, submit externally, then record the submission here.";
    case "submitted": return "The application is sent. Record acknowledgement, recruiter contact, or a final outcome.";
    case "acknowledged": return "The employer confirmed receipt. Record recruiter contact when it happens.";
    case "recruiter_screen": return "Capture the recruiter conversation and move to the next interview stage.";
    case "technical_interview": return "Record the technical-stage result and the next interview.";
    case "hiring_manager_interview": return "Record the hiring-manager result, final interview, or offer.";
    case "final_interview": return "Record the final result or offer.";
    case "offer": return "Record whether the offer is accepted or declined.";
    default: return "Open the workflow to review the complete history.";
  }
}

export function ApplicationWorkflow({ apiBase, postingId, title, reviewDecision, applicationId, applicationStatus, disabled, onChanged, onError }: Props) {
  const [application, setApplication] = useState<ApplicationData | null>(null);
  const [applicationUrl, setApplicationUrl] = useState("");
  const [resumeUsed, setResumeUsed] = useState("");
  const [notes, setNotes] = useState("");
  const [activityNotes, setActivityNotes] = useState("");
  const [selectedOutcome, setSelectedOutcome] = useState<OutcomeType>("rejected_by_employer");
  const [selectedStage, setSelectedStage] = useState<ApplicationStatus | "">(applicationStatus ?? "");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [workflowOpen, setWorkflowOpen] = useState(false);

  useEffect(() => {
    setWorkflowOpen(false);
    setApplication(null);
  }, [applicationId]);
  useEffect(() => {
    const status = application?.status ?? applicationStatus;
    if (status) setSelectedStage(status);
  }, [application?.status, applicationStatus]);

  const displayedStatus = application?.status ?? applicationStatus;
  const actions = useMemo(() => (application ? STAGE_ACTIONS[application.status] ?? [] : []), [application]);
  const outcomes = displayedStatus === "offer" ? OFFER_OUTCOMES : GENERAL_OUTCOMES;

  async function loadApplication() {
    if (!applicationId || application || loading) return;
    setLoading(true);
    onError("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}`);
      if (!response.ok) throw new Error("Unable to load application history.");
      const loaded = (await response.json()) as ApplicationData;
      setApplication(loaded);
      setSelectedStage(loaded.status);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application history failed.");
    } finally { setLoading(false); }
  }

  function toggleWorkflow() {
    const nextOpen = !workflowOpen;
    setWorkflowOpen(nextOpen);
    if (nextOpen) void loadApplication();
  }

  async function post(url: string, body: object) {
    setBusy(true);
    onError("");
    try {
      const response = await fetch(`${apiBase}${url}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The application workflow change could not be saved.");
      }
      const changed = (await response.json()) as ApplicationData;
      setApplication(changed);
      setSelectedStage(changed.status);
      setActivityNotes("");
      await onChanged();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unexpected application workflow error.");
    } finally { setBusy(false); }
  }

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await post(`/api/opportunities/${postingId}/applications`, { application_url: applicationUrl, resume_used: resumeUsed, notes });
  }

  if (!applicationId && reviewDecision !== "pursue") return <p>Record a pursue decision before preparing an application.</p>;
  if (!applicationId) return <details className="application-workflow">
    <summary>Prepare application</summary>
    <div className="workflow-guidance"><strong>Preparation stage</strong><p>Create the local record before submitting externally. This does not apply to the role.</p></div>
    <form className="application-preparation-form" onSubmit={start}>
      <label>External application URL <span>(optional)</span><input type="url" value={applicationUrl} onChange={(event) => setApplicationUrl(event.target.value)} /></label>
      <label>CV or resume version <span>(optional)</span><input value={resumeUsed} onChange={(event) => setResumeUsed(event.target.value)} placeholder="Example: Rafael_Application_Support_CV.pdf" /></label>
      <label className="application-form-wide">Preparation notes <span>(optional)</span><textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Tailoring, cover letter, questions to confirm, or blockers." /></label>
      <button disabled={disabled || busy} type="submit">Create preparation record</button>
    </form>
  </details>;

  const panelId = `application-workflow-panel-${applicationId}`;
  return <section className="application-workflow">
    <button
      aria-controls={panelId}
      aria-expanded={workflowOpen}
      className="application-workflow-toggle"
      type="button"
      onClick={toggleWorkflow}
    >
      Manage application · {displayedStatus ? label(displayedStatus) : "loading"}
    </button>
    {workflowOpen && <div className="application-workflow-panel" id={panelId}>
      {loading && <p role="status">Loading application history…</p>}
      {!loading && !application && <p>Application history could not be loaded.</p>}
      {application && <div className="application-workflow-body">
        <section className="workflow-current-stage">
          <div><p className="eyebrow">Current stage</p><h4>{label(application.status)}</h4><p>{stageGuidance(application.status)}</p></div>
          <div className="workflow-record-details">
            {application.application_url && <a href={application.application_url} target="_blank" rel="noreferrer">Open external application page</a>}
            {application.resume_used && <span><strong>CV:</strong> {application.resume_used}</span>}
            {application.notes && <span><strong>Preparation:</strong> {application.notes}</span>}
          </div>
        </section>
        <label className="workflow-notes">Activity or correction notes <span>(recommended)</span><textarea rows={2} value={activityNotes} onChange={(event) => setActivityNotes(event.target.value)} placeholder="Date, contact, result, correction reason, next action, interview details, or follow-up context." /></label>
        <section className="workflow-outcome-section">
          <h4>Change stage</h4>
          <div className="workflow-outcome-controls">
            <label>Stage<select value={selectedStage || application.status} onChange={(event) => setSelectedStage(event.target.value as ApplicationStatus)}>{APPLICATION_STAGES.map((stage) => <option key={stage.value} value={stage.value}>{stage.label}</option>)}</select></label>
            <button className="secondary" disabled={disabled || busy || !selectedStage || selectedStage === application.status} type="button" onClick={() => post(`/api/applications/${application.application_id}/transitions`, { status: selectedStage, notes: activityNotes })}>Save stage</button>
          </div>
          <p>Stages can move backward or forward. Reopening keeps the previous outcome in the timeline.</p>
        </section>
        {!application.outcome_type && actions.length > 0 && <section className="workflow-actions-section">
          <h4>Suggested next actions</h4>
          <div className="workflow-action-grid" aria-label={`Advance ${title}`}>{actions.map((action) => <button disabled={disabled || busy} type="button" key={action.status} onClick={() => post(`/api/applications/${application.application_id}/transitions`, { status: action.status, notes: activityNotes })}><strong>{action.label}</strong><span>{action.guidance}</span></button>)}</div>
        </section>}
        {!application.outcome_type && <section className="workflow-outcome-section">
          <h4>{application.status === "offer" ? "Close the offer" : "Close the application"}</h4>
          <div className="workflow-outcome-controls">
            <label>Outcome<select value={outcomes.some((item) => item.value === selectedOutcome) ? selectedOutcome : outcomes[0].value} onChange={(event) => setSelectedOutcome(event.target.value as OutcomeType)}>{outcomes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <button className="secondary" disabled={disabled || busy} type="button" onClick={() => {
              const effectiveOutcome = outcomes.some((item) => item.value === selectedOutcome) ? selectedOutcome : outcomes[0].value;
              void post(`/api/applications/${application.application_id}/outcomes`, { outcome_type: effectiveOutcome, notes: activityNotes });
            }}>Record final outcome</button>
          </div>
        </section>}
        {application.outcome_type && <div className="workflow-closed-state"><strong>Final outcome: {label(application.outcome_type)}</strong><span>Use Change stage above to reopen this application. The previous outcome remains in the timeline.</span></div>}
        <details className="application-event-history">
          <summary>Complete application history ({application.events.length})</summary>
          <ol>{application.events.map((event) => <li key={event.event_id}><strong>{label(event.event_type)}</strong>: {event.from_status ? `${label(event.from_status)} → ` : ""}{label(event.to_status)}{event.notes && <> · {formatEventNotes(event.notes)}</>}<br /><small>{new Date(event.occurred_at).toLocaleString()}</small></li>)}</ol>
        </details>
      </div>}
    </div>}
  </section>;
}
