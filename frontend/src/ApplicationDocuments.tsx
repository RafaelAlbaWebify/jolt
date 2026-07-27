import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

type DocumentRecord = {
  document_id: string;
  document_type: "resume" | "cover_letter" | "preparation_pack" | "portfolio" | "certificate" | "other";
  title: string;
  file_path: string;
  source_url: string;
  status: "draft" | "ready" | "submitted" | "superseded";
  notes: string;
};

type Props = {
  apiBase: string;
  applicationId?: string | null;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

const EMPTY: Omit<DocumentRecord, "document_id"> = {
  document_type: "resume",
  title: "",
  file_path: "",
  source_url: "",
  status: "draft",
  notes: "",
};

export function ApplicationDocuments({ apiBase, applicationId, onChanged, onError }: Props) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!applicationId) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/documents`);
      if (!response.ok) throw new Error("Unable to load application documents.");
      setDocuments((await response.json()) as DocumentRecord[]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Application document loading failed.";
      setError(message);
      onError(message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, applicationId, onError]);

  useEffect(() => {
    setEditingId(null);
    setForm(EMPTY);
    void load();
  }, [load]);

  function edit(document: DocumentRecord) {
    setEditingId(document.document_id);
    setForm({
      document_type: document.document_type,
      title: document.title,
      file_path: document.file_path,
      source_url: document.source_url,
      status: document.status,
      notes: document.notes,
    });
    setError("");
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY);
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId || !form.title.trim()) return;
    setBusy(true);
    setError("");
    try {
      const endpoint = editingId
        ? `${apiBase}/api/application-documents/${editingId}/update`
        : `${apiBase}/api/applications/${applicationId}/documents`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, title: form.title.trim(), file_path: form.file_path.trim(), source_url: form.source_url.trim(), notes: form.notes.trim() }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string | Array<{ msg?: string }> } | null;
        const detail = Array.isArray(payload?.detail) ? payload?.detail[0]?.msg : payload?.detail;
        throw new Error(detail || `The document record could not be ${editingId ? "updated" : "created"}.`);
      }
      cancelEdit();
      await load();
      await onChanged();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Application document save failed.";
      setError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  }

  if (!applicationId) {
    return <section className="application-tab-placeholder"><h4>Create the preparation record first</h4><p>Document records attach to a persisted application and its Timeline.</p></section>;
  }

  return <section className="work-items-panel" aria-labelledby="application-documents-heading">
    <div className="application-tab-heading"><div><p className="eyebrow">Application materials</p><h4 id="application-documents-heading">Documents</h4></div><span>{documents.length} recorded</span></div>
    <form className="work-item-form" onSubmit={submit}>
      <label>Document type<select value={form.document_type} onChange={(event) => setForm((value) => ({ ...value, document_type: event.target.value as DocumentRecord["document_type"] }))}><option value="resume">Resume</option><option value="cover_letter">Cover letter</option><option value="preparation_pack">Preparation pack</option><option value="portfolio">Portfolio</option><option value="certificate">Certificate</option><option value="other">Other</option></select></label>
      <label>Status<select value={form.status} onChange={(event) => setForm((value) => ({ ...value, status: event.target.value as DocumentRecord["status"] }))}><option value="draft">Draft</option><option value="ready">Ready</option><option value="submitted">Submitted</option><option value="superseded">Superseded</option></select></label>
      <label className="work-item-form-wide">Title<input required maxLength={240} value={form.title} onChange={(event) => setForm((value) => ({ ...value, title: event.target.value }))} /></label>
      <label>Local file path<input value={form.file_path} onChange={(event) => setForm((value) => ({ ...value, file_path: event.target.value }))} /></label>
      <label>Source URL<input type="url" value={form.source_url} onChange={(event) => setForm((value) => ({ ...value, source_url: event.target.value }))} /></label>
      <label className="work-item-form-wide">Notes<textarea rows={2} value={form.notes} onChange={(event) => setForm((value) => ({ ...value, notes: event.target.value }))} /></label>
      <button type="submit" disabled={busy || !form.title.trim()}>{busy ? "Saving…" : editingId ? "Save document changes" : "Add document"}</button>
      {editingId && <button type="button" className="secondary" disabled={busy} onClick={cancelEdit}>Cancel edit</button>}
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {error && !loading && documents.length === 0 && <button type="button" className="secondary" onClick={() => void load()}>Retry documents</button>}
    {loading ? <p role="status">Loading documents…</p> : documents.length === 0 ? <p className="work-items-empty">No document records yet.</p> : <ul className="work-item-list">{documents.map((document) => <li key={document.document_id}><div><strong>{document.title}</strong><span>{document.document_type.replaceAll("_", " ")} · {document.status}</span>{document.file_path && <p>{document.file_path}</p>}{document.source_url && <p><a href={document.source_url} target="_blank" rel="noreferrer">Open source</a></p>}{document.notes && <p>{document.notes}</p>}</div><div><span className="work-item-status">{document.status}</span><button type="button" className="secondary" disabled={busy} onClick={() => edit(document)}>Edit document</button></div></li>)}</ul>}
  </section>;
}
