import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

type Interview = {
  interview_id: string;
  interview_type: string;
  scheduled_at: string;
  timezone: string;
  format_location: string;
  participants: string;
  preparation_notes: string;
  outcome_notes: string;
  status: "scheduled" | "completed" | "cancelled";
};

type Props = {
  apiBase: string;
  applicationId?: string | null;
  readOnly?: boolean;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

function toLocalDateTime(value: string) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

async function responseError(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || fallback;
  } catch {
    return fallback;
  }
}

export function ApplicationInterviews({ apiBase, applicationId, readOnly = false, onChanged, onError }: Props) {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [editingInterviewId, setEditingInterviewId] = useState<string | null>(null);
  const [interviewType, setInterviewType] = useState("recruiter_screen");
  const [scheduledAt, setScheduledAt] = useState("");
  const [timezone, setTimezone] = useState("Europe/Madrid");
  const [formatLocation, setFormatLocation] = useState("");
  const [participants, setParticipants] = useState("");
  const [preparationNotes, setPreparationNotes] = useState("");
  const [outcomeNotes, setOutcomeNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");

  const resetForm = useCallback(() => {
    setEditingInterviewId(null);
    setInterviewType("recruiter_screen");
    setScheduledAt("");
    setTimezone("Europe/Madrid");
    setFormatLocation("");
    setParticipants("");
    setPreparationNotes("");
    setOutcomeNotes("");
    setFormError("");
  }, []);

  const load = useCallback(async () => {
    if (!applicationId) { setInterviews([]); setLoadError(""); return; }
    setLoading(true);
    setLoadError("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/interviews`);
      if (!response.ok) throw new Error("Unable to load application interviews.");
      setInterviews((await response.json()) as Interview[]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Interview loading failed.";
      setLoadError(message);
      onError(message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, applicationId, onError]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { resetForm(); }, [applicationId, readOnly, resetForm]);

  function beginEdit(interview: Interview) {
    if (readOnly) return;
    setEditingInterviewId(interview.interview_id);
    setInterviewType(interview.interview_type);
    setScheduledAt(toLocalDateTime(interview.scheduled_at));
    setTimezone(interview.timezone);
    setFormatLocation(interview.format_location);
    setParticipants(interview.participants);
    setPreparationNotes(interview.preparation_notes);
    setOutcomeNotes(interview.outcome_notes);
    setFormError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (readOnly || !applicationId || !scheduledAt) return;
    setBusy(true);
    setFormError("");
    try {
      const editing = editingInterviewId !== null;
      const url = editing
        ? `${apiBase}/api/application-interviews/${editingInterviewId}/update`
        : `${apiBase}/api/applications/${applicationId}/interviews`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interview_type: interviewType,
          scheduled_at: new Date(scheduledAt).toISOString(),
          timezone: timezone.trim(),
          format_location: formatLocation.trim(),
          participants: participants.trim(),
          preparation_notes: preparationNotes.trim(),
          ...(editing ? { outcome_notes: outcomeNotes.trim() } : {}),
        }),
      });
      if (!response.ok) throw new Error(await responseError(response, editing ? "The interview could not be updated." : "The interview could not be scheduled."));
      resetForm();
      await load();
      await onChanged();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Interview save failed.";
      setFormError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  }

  async function finish(interview: Interview, action: "complete" | "cancel") {
    if (readOnly) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBase}/api/application-interviews/${interview.interview_id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome_notes: interview.outcome_notes }),
      });
      if (!response.ok) throw new Error("The interview status could not be changed.");
      await load();
      await onChanged();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Interview update failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!applicationId) return <section className="application-tab-placeholder"><h4>Create the preparation record first</h4><p>Interviews attach to a persisted application and its Timeline.</p></section>;

  return <section className="work-items-panel" aria-labelledby="application-interviews-heading">
    <div className="application-tab-heading"><div><p className="eyebrow">Scheduled conversations</p><h4 id="application-interviews-heading">Interviews</h4></div><span>{interviews.filter((item) => item.status === "scheduled").length} scheduled</span></div>
    {readOnly ? <p className="application-read-only-notice" role="status">Archived application — interviews are read-only until the application is restored.</p> : <form className="work-item-form" onSubmit={submit}>
      <label>Interview type<select value={interviewType} onChange={(event) => setInterviewType(event.target.value)}><option value="recruiter_screen">Recruiter screen</option><option value="technical_interview">Technical interview</option><option value="hiring_manager_interview">Hiring-manager interview</option><option value="final_interview">Final interview</option><option value="other">Other</option></select></label>
      <label>Date and time<input required type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} /></label>
      <label>Timezone<input required maxLength={80} value={timezone} onChange={(event) => setTimezone(event.target.value)} /></label>
      <label>Format or location<input value={formatLocation} onChange={(event) => setFormatLocation(event.target.value)} placeholder="Teams, phone, office..." /></label>
      <label className="work-item-form-wide">Participants<input value={participants} onChange={(event) => setParticipants(event.target.value)} /></label>
      <label className="work-item-form-wide">Preparation notes<textarea rows={2} value={preparationNotes} onChange={(event) => setPreparationNotes(event.target.value)} /></label>
      {editingInterviewId && <label className="work-item-form-wide">Outcome notes<textarea rows={2} value={outcomeNotes} onChange={(event) => setOutcomeNotes(event.target.value)} /></label>}
      {formError && <p role="alert" className="form-error">{formError}</p>}
      <div className="work-item-actions">
        <button type="submit" disabled={busy || !scheduledAt || !timezone.trim()}>{busy ? "Saving…" : editingInterviewId ? "Save interview changes" : "Schedule interview"}</button>
        {editingInterviewId && <button type="button" className="secondary" disabled={busy} onClick={resetForm}>Cancel edit</button>}
      </div>
    </form>}
    {loadError && <div className="load-error" role="alert"><p>{loadError}</p><button type="button" className="secondary" onClick={() => void load()}>Retry interviews</button></div>}
    {loading ? <p role="status">Loading interviews…</p> : interviews.length === 0 ? <p className="work-items-empty">No interviews recorded yet.</p> : <ul className="work-item-list interview-list">{interviews.map((interview) => <li key={interview.interview_id} className={interview.status !== "scheduled" ? "work-item-completed" : ""}><div><strong>{interview.interview_type.replaceAll("_", " ")}</strong><span>{new Date(interview.scheduled_at).toLocaleString()} · {interview.timezone}</span>{interview.format_location && <p>{interview.format_location}</p>}{interview.participants && <p>{interview.participants}</p>}</div><div className="work-item-actions">{readOnly ? <span className="work-item-status">{interview.status}</span> : <><button type="button" className="secondary" disabled={busy} onClick={() => beginEdit(interview)}>Edit interview</button>{interview.status === "scheduled" ? <><button type="button" disabled={busy} onClick={() => void finish(interview, "complete")}>Complete</button><button type="button" className="secondary" disabled={busy} onClick={() => void finish(interview, "cancel")}>Cancel</button></> : <span className="work-item-status">{interview.status}</span>}</>}</div></li>)}</ul>}
  </section>;
}
