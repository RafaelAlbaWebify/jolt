import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

type Task = {
  task_id: string;
  title: string;
  notes: string;
  due_at: string | null;
  status: "open" | "completed";
};

type Props = {
  apiBase: string;
  applicationId?: string | null;
  readOnly?: boolean;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

function localDateTime(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

export function ApplicationTasks({ apiBase, applicationId, readOnly = false, onChanged, onError }: Props) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");

  const resetForm = useCallback(() => {
    setTitle("");
    setNotes("");
    setDueAt("");
    setEditingId(null);
    setSaveError("");
  }, []);

  const load = useCallback(async () => {
    if (!applicationId) { setTasks([]); setLoadError(""); return; }
    setLoading(true);
    setLoadError("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/tasks`);
      if (!response.ok) throw new Error("Unable to load application tasks.");
      setTasks((await response.json()) as Task[]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Application task loading failed.";
      setLoadError(message);
      onError(message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, applicationId, onError]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (readOnly) resetForm(); }, [readOnly, resetForm]);

  function beginEdit(task: Task) {
    if (readOnly) return;
    setEditingId(task.task_id);
    setTitle(task.title);
    setNotes(task.notes);
    setDueAt(localDateTime(task.due_at));
    setSaveError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (readOnly || !applicationId || !title.trim()) return;
    setBusy(true);
    setSaveError("");
    try {
      const url = editingId
        ? `${apiBase}/api/application-tasks/${editingId}/update`
        : `${apiBase}/api/applications/${applicationId}/tasks`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          notes: notes.trim(),
          due_at: dueAt ? new Date(dueAt).toISOString() : null,
        }),
      });
      if (!response.ok) {
        let detail = editingId ? "The task could not be updated." : "The task could not be created.";
        try {
          const payload = await response.json() as { detail?: string | Array<{ msg?: string }> };
          if (typeof payload.detail === "string") detail = payload.detail;
          else if (Array.isArray(payload.detail) && payload.detail[0]?.msg) detail = payload.detail[0].msg;
        } catch { /* retain fallback */ }
        throw new Error(detail);
      }
      resetForm();
      await load();
      await onChanged();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Application task save failed.";
      setSaveError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(task: Task) {
    if (readOnly) return;
    setBusy(true);
    setSaveError("");
    try {
      const action = task.status === "completed" ? "reopen" : "complete";
      const response = await fetch(`${apiBase}/api/application-tasks/${task.task_id}/${action}`, { method: "POST" });
      if (!response.ok) throw new Error("The task status could not be changed.");
      await load();
      await onChanged();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Application task update failed.";
      setSaveError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  }

  if (!applicationId) return <section className="application-tab-placeholder"><h4>Create the preparation record first</h4><p>Tasks attach to a persisted application and its Timeline.</p></section>;

  return <section className="work-items-panel" aria-labelledby="application-tasks-heading">
    <div className="application-tab-heading"><div><p className="eyebrow">Next actions</p><h4 id="application-tasks-heading">Tasks</h4></div><span>{tasks.filter((task) => task.status === "open").length} open</span></div>
    {readOnly ? <p className="application-read-only-notice" role="status">Archived application — tasks are read-only until the application is restored.</p> : <form className="work-item-form" onSubmit={submit}>
      <label>Task title<input required maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <label>Due date and time<input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label>
      <label className="work-item-form-wide">Notes<textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <button type="submit" disabled={busy || !title.trim()}>{busy ? "Saving…" : editingId ? "Save task changes" : "Add task"}</button>
      {editingId && <button type="button" className="secondary" disabled={busy} onClick={resetForm}>Cancel edit</button>}
    </form>}
    {saveError && <p role="alert">{saveError}</p>}
    {loading ? <p role="status">Loading tasks…</p> : loadError ? <div><p role="alert">{loadError}</p><button type="button" className="secondary" onClick={() => void load()}>Retry tasks</button></div> : tasks.length === 0 ? <p className="work-items-empty">No tasks recorded yet.</p> : <ul className="work-item-list">{tasks.map((task) => <li key={task.task_id} className={task.status === "completed" ? "work-item-completed" : ""}><div><strong>{task.title}</strong><span>{task.due_at ? new Date(task.due_at).toLocaleString() : "No due date"}</span>{task.notes && <p>{task.notes}</p>}</div><div>{readOnly ? <span className="work-item-status">{task.status}</span> : <><button type="button" className="secondary" disabled={busy} onClick={() => beginEdit(task)}>Edit task</button><button type="button" className="secondary" disabled={busy} onClick={() => void changeStatus(task)}>{task.status === "completed" ? "Reopen" : "Complete"}</button></>}</div></li>)}</ul>}
  </section>;
}
