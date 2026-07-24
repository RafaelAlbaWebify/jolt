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

export function ApplicationDocuments({ apiBase, applicationId, onChanged, onError }: Props) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentType, setDocumentType] = useState<DocumentRecord["document_type"]>("resume");
  const [title, setTitle] = useState("");
  const [filePath, setFilePath] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [status, setStatus] = useState<DocumentRecord["status"]>("draft");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!applicationId) { setDocuments([]); return; }
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/documents`);
      if (!response.ok) throw new Error("Unable to load application documents.");
      setDocuments((await response.json()) as DocumentRecord[]);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application document loading failed.");
    } finally { setLoading(false); }
  }, [apiBase, applicationId, onError]);

  useEffect(() => { void load(); }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId || !title.trim()) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_type: documentType,
          title: title.trim(),
          file_path: filePath.trim(),
          source_url: sourceUrl.trim(),
          status,
          notes: notes.trim(),
        }),
      });
      if (!response.ok) throw new Error("The document record could not be created.");
      setDocumentType("resume"); setTitle(""); setFilePath(""); setSourceUrl(""); setStatus("draft"); setNotes("");
      await load();
      await onChanged();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application document creation failed.");
    } finally { setBusy(false); }
  }

  if (!applicationId) return <section className="application-tab-placeholder"><h4>Create the preparation record first</h4><p>Document records attach to a persisted application and its Timeline.</p></section>;

  return <section className="work-items-panel" aria-labelledby="application-documents-heading">
    <div className="application-tab-heading"><div><p className="eyebrow">Application materials</p><h4 id="application-documents-heading">Documents</h4></div><span>{documents.length} recorded</span></div>
    <form className="work-item-form" onSubmit={submit}>
      <label>Document type<select value={documentType} onChange={(event) => setDocumentType(event.target.value as DocumentRecord["document_type"])}><option value="resume">Resume</option><option value="cover_letter">Cover letter</option><option value="preparation_pack">Preparation pack</option><option value="portfolio">Portfolio</option><option value="certificate">Certificate</option><option value="other">Other</option></select></label>
      <label>Status<select value={status} onChange={(event) => setStatus(event.target.value as DocumentRecord["status"])}><option value="draft">Draft</option><option value="ready">Ready</option><option value="submitted">Submitted</option><option value="superseded">Superseded</option></select></label>
      <label className="work-item-form-wide">Title<input required maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <label>Local file path<input value={filePath} onChange={(event) => setFilePath(event.target.value)} /></label>
      <label>Source URL<input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></label>
      <label className="work-item-form-wide">Notes<textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <button type="submit" disabled={busy || !title.trim()}>{busy ? "Saving…" : "Add document"}</button>
    </form>
    {loading ? <p role="status">Loading documents…</p> : documents.length === 0 ? <p className="work-items-empty">No document records yet.</p> : <ul className="work-item-list">{documents.map((document) => <li key={document.document_id}><div><strong>{document.title}</strong><span>{document.document_type.replaceAll("_", " ")} · {document.status}</span>{document.file_path && <p>{document.file_path}</p>}{document.source_url && <p><a href={document.source_url} target="_blank" rel="noreferrer">Open source</a></p>}{document.notes && <p>{document.notes}</p>}</div><span className="work-item-status">{document.status}</span></li>)}</ul>}
  </section>;
}
