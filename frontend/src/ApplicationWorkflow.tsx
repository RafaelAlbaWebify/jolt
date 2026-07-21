import { useEffect, useMemo, useState } from "react";
import type { FormEvent, SyntheticEvent } from "react";

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

const TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  preparing: ["submitted"],
  submitted: ["acknowledged", "recruiter_screen"],
  acknowledged: ["recruiter_screen"],
  recruiter_screen: ["technical_interview", "hiring_manager_interview"],
  technical_interview: ["hiring_manager_interview", "final_interview"],
  hiring_manager_interview: ["final_interview", "offer"],
  final_interview: ["offer"],
  offer: [],
  rejected: ["closed"],
  withdrawn: ["closed"],
  no_response: ["closed"],
  closed: [],
};

const OUTCOMES: { value: OutcomeType; label: string }[] = [
  { value: "rejected_by_employer", label: "Rejected by employer" },
  { value: "withdrawn_by_user", label: "Withdrawn by me" },
  { value: "no_response", label: "No response" },
  { value: "offer_declined", label: "Offer declined" },
  { value: "offer_accepted", label: "Offer accepted" },
  { value: "role_closed", label: "Role closed" },
];

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function ApplicationWorkflow({
  apiBase,
  postingId,
  title,
  reviewDecision,
  applicationId,
  applicationStatus,
  disabled,
  onChanged,
  onError,
}: Props) {
  const [application, setApplication] = useState<ApplicationData | null>(null);
  const [applicationUrl, setApplicationUrl] = useState("");
  const [resumeUsed, setResumeUsed] = useState("");
  const [notes, setNotes] = useState("");
  const [transitionNotes, setTransitionNotes] = useState("");
  const [outcome, setOutcome] = useState<OutcomeType>("rejected_by_employer");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!applicationId) {
      setApplication(null);
      return;
    }
    if (application && application.application_id !== applicationId) {
      setApplication(null);
    }
  }, [application, applicationId]);

  const transitions = useMemo(
    () => (application ? TRANSITIONS[application.status] : []),
    [application],
  );

  async function loadApplication() {
    if (!applicationId || application || loading) return;
    setLoading(true);
    onError("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}`);
      if (!response.ok) throw new Error("Unable to load application history.");
      setApplication((await response.json()) as ApplicationData);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application history failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleToggle(event: SyntheticEvent<HTMLDetailsElement>) {
    if (event.currentTarget.open) void loadApplication();
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
      setApplication((await response.json()) as ApplicationData);
      await onChanged();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unexpected application workflow error.");
    } finally {
      setBusy(false);
    }
  }

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await post(`/api/opportunities/${postingId}/applications`, {
      application_url: applicationUrl,
      resume_used: resumeUsed,
      notes,
    });
  }

  if (!applicationId && reviewDecision !== "pursue") {
    return <p>Record a pursue decision before starting an application.</p>;
  }

  if (!applicationId) {
    return (
      <details className="application-workflow">
        <summary>Start application workflow</summary>
        <form onSubmit={start}>
          <label>
            Application URL <span>(optional)</span>
            <input type="url" value={applicationUrl} onChange={(event) => setApplicationUrl(event.target.value)} />
          </label>
          <label>
            Resume or CV used <span>(optional)</span>
            <input value={resumeUsed} onChange={(event) => setResumeUsed(event.target.value)} />
          </label>
          <label>
            Preparation notes <span>(optional)</span>
            <textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
          <button disabled={disabled || busy} type="submit">Create application record</button>
        </form>
      </details>
    );
  }

  const displayedStatus = application?.status ?? applicationStatus;

  return (
    <details className="application-workflow" onToggle={handleToggle}>
      <summary>Application workflow{displayedStatus ? ` · ${label(displayedStatus)}` : ""}</summary>
      {loading && <p role="status">Loading application history…</p>}
      {!loading && !application && <p>Open this workflow to load its application history.</p>}
      {application && (
        <>
          <p><strong>Current stage:</strong> {label(application.status)}</p>
          {application.application_url && <p><a href={application.application_url} target="_blank" rel="noreferrer">Open application page</a></p>}
          {application.resume_used && <p><strong>CV used:</strong> {application.resume_used}</p>}
          {application.notes && <p><strong>Preparation notes:</strong> {application.notes}</p>}

          {!application.outcome_type && transitions.length > 0 && (
            <div>
              <label>
                Stage notes <span>(optional)</span>
                <input value={transitionNotes} onChange={(event) => setTransitionNotes(event.target.value)} />
              </label>
              <div className="review-actions application-actions" aria-label={`Advance ${title}`}>
                {transitions.map((status) => (
                  <button
                    disabled={disabled || busy}
                    type="button"
                    key={status}
                    onClick={() => post(`/api/applications/${application.application_id}/transitions`, {
                      status,
                      notes: transitionNotes,
                    })}
                  >
                    Mark {label(status)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {!application.outcome_type && (
            <div>
              <label>
                Final outcome
                <select value={outcome} onChange={(event) => setOutcome(event.target.value as OutcomeType)}>
                  {OUTCOMES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <button
                className="secondary"
                disabled={disabled || busy}
                type="button"
                onClick={() => post(`/api/applications/${application.application_id}/outcomes`, {
                  outcome_type: outcome,
                  notes: transitionNotes,
                })}
              >
                Record outcome
              </button>
            </div>
          )}

          {application.outcome_type && <p><strong>Outcome:</strong> {label(application.outcome_type)}</p>}

          <h4>Application event history</h4>
          <ol>
            {application.events.map((event) => (
              <li key={event.event_id}>
                <strong>{label(event.event_type)}</strong>: {event.from_status ? `${label(event.from_status)} → ` : ""}{label(event.to_status)}
                {event.notes && <> · {event.notes}</>}
                <br />
                <small>{new Date(event.occurred_at).toLocaleString()}</small>
              </li>
            ))}
          </ol>
        </>
      )}
    </details>
  );
}
