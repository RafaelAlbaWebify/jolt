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
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

export function ApplicationTasks({ apiBase, applicationId, onChanged, onError }: Props) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!applicationId) { setTasks([]); return; }
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/tasks`);
      if (!response.ok) throw new Error("Unable to load application tasks.");
      setTasks((await response.json()) as Task[]);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application task loading failed.");
    } finally {
      setLoading(false);
    }
  }, [apiBase, applicationId, onError]);

  useEffect(() => { void load(); }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId || !title.trim()) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          notes: notes.trim(),
          due_at: dueAt ? new Date(dueAt).toISOString() : null,
        }),
      });
      if (!response.ok) throw new Error("The task could not be created.");
      setTitle(""); setNotes(""); setDueAt("");
      await load();
      await onChanged();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application task creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(task: Task) {
    setBusy(true);
    try {
      const action = task.status === "completed" ? "reopen" : "complete";
      const response = await fetch(`${apiBase}/api/application-tasks/${task.task_id}/${action}`, { method: "POST" });
      if (!response.ok) throw new Error("The task status could not be changed.");
      await load();
      await onChanged();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application task update failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!applicationId) return <section className="application-tab-placeholder"><h4>Create the preparation record first</h4><p>Tasks attach to a persisted application and its Timeline.</p></section>;

  return <section className="work-items-panel" aria-labelledby="application-tasks-heading">
    <div className="application-tab-heading"><div><p className="eyebrow">Next actions</p><h4 id="application-tasks-heading">Tasks</h4></div><span>{tasks.filter((task) => task.status === "open").length} open</span></div>
    <form className="work-item-form" onSubmit={submit}>
      <label>Task title<input required maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <label>Due date and time<input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label>
      <label className="work-item-form-wide">Notes<textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <button type="submit" disabled={busy || !title.trim()}>{busy ? "Saving…" : "Add task"}</button>
    </form>
    {loading ? <p role="status">Loading tasks…</p> : tasks.length === 0 ? <p className="work-items-empty">No tasks recorded yet.</p> : <ul className="work-item-list">{tasks.map((task) => <li key={task.task_id} className={task.status === "completed" ? "work-item-completed" : ""}><div><strong>{task.title}</strong><span>{task.due_at ? new Date(task.due_at).toLocaleString() : "No due date"}</span>{task.notes && <p>{task.notes}</p>}</div><button type="button" className="secondary" disabled={busy} onClick={() => void changeStatus(task)}>{task.status === "completed" ? "Reopen" : "Complete"}</button></li>)}</ul>}
  </section>;
}
