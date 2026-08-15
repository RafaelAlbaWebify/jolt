import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

type DocumentRecord = {
  document_id: string;
  application_id: string;
  document_type: "resume" | "cover_letter" | "preparation_pack" | "portfolio" | "certificate" | "other";
  title: string;
  file_path: string;
  source_url: string;
  status: "draft" | "ready" | "submitted" | "superseded";
  notes: string;
  stored_filename: string;
  mime_type: string;
  file_size: number;
  file_sha256: string;
  has_file: boolean;
  created_at: string;
  updated_at: string;
};

type DocumentForm = {
  document_type: DocumentRecord["document_type"];
  title: string;
  source_url: string;
  status: DocumentRecord["status"];
  notes: string;
};

type Props = {
  apiBase: string;
  applicationId?: string | null;
  readOnly?: boolean;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

const EMPTY: DocumentForm = {
  document_type: "resume",
  title: "",
  source_url: "",
  status: "draft",
  notes: "",
};

function fileSizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function responseDetail(response: Response, fallback: string): Promise<string> {
  const payload = (await response.json().catch(() => null)) as
    | { detail?: string | Array<{ msg?: string }> }
    | null;
  const detail = Array.isArray(payload?.detail) ? payload?.detail[0]?.msg : payload?.detail;
  return detail || fallback;
}

export function ApplicationDocuments({
  apiBase,
  applicationId,
  readOnly = false,
  onChanged,
  onError,
}: Props) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [form, setForm] = useState<DocumentForm>(EMPTY);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
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
      const message =
        caught instanceof Error ? caught.message : "Application document loading failed.";
      setError(message);
      onError(message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, applicationId, onError]);

  useEffect(() => {
    setEditingId(null);
    setForm(EMPTY);
    setSelectedFile(null);
    void load();
  }, [load, readOnly]);

  function edit(document: DocumentRecord) {
    if (readOnly) return;

    setEditingId(document.document_id);
    setSelectedFile(null);
    setForm({
      document_type: document.document_type,
      title: document.title,
      source_url: document.source_url,
      status: document.status,
      notes: document.notes,
    });
    setError("");
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY);
    setSelectedFile(null);
    setError("");
  }

  async function uploadFile(documentId: string, file: File): Promise<void> {
    const response = await fetch(
      `${apiBase}/api/application-documents/${documentId}/file?filename=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        headers: {
          "Content-Type": file.type || "application/octet-stream",
        },
        body: file,
      },
    );

    if (!response.ok) {
      throw new Error(
        await responseDetail(
          response,
          "The document record was saved, but its file could not be stored.",
        ),
      );
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (readOnly || !applicationId || !form.title.trim()) return;

    setBusy(true);
    setError("");

    try {
      const endpoint = editingId
        ? `${apiBase}/api/application-documents/${editingId}/update`
        : `${apiBase}/api/applications/${applicationId}/documents`;

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          title: form.title.trim(),
          file_path: "",
          source_url: form.source_url.trim(),
          notes: form.notes.trim(),
        }),
      });

      if (!response.ok) {
        throw new Error(
          await responseDetail(
            response,
            `The document record could not be ${editingId ? "updated" : "created"}.`,
          ),
        );
      }

      const saved = (await response.json()) as DocumentRecord;

      if (selectedFile) {
        await uploadFile(saved.document_id, selectedFile);
      }

      cancelEdit();
      await load();
      await onChanged();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Application document save failed.";
      setError(message);
      onError(message);
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (!applicationId) {
    return (
      <section className="application-tab-placeholder">
        <h4>Create the preparation record first</h4>
        <p>Document records attach to a persisted application and its Timeline.</p>
      </section>
    );
  }

  return (
    <section className="work-items-panel" aria-labelledby="application-documents-heading">
      <div className="application-tab-heading">
        <div>
          <p className="eyebrow">Application materials</p>
          <h4 id="application-documents-heading">Documents</h4>
        </div>
        <span>{documents.length} recorded</span>
      </div>

      {readOnly ? (
        <p className="application-read-only-notice" role="status">
          Archived application — document metadata is read-only, but stored files remain
          downloadable.
        </p>
      ) : (
        <form className="work-item-form" onSubmit={submit}>
          <label>
            Document type
            <select
              value={form.document_type}
              onChange={(event) =>
                setForm((value) => ({
                  ...value,
                  document_type: event.target.value as DocumentRecord["document_type"],
                }))
              }
            >
              <option value="resume">Resume</option>
              <option value="cover_letter">Cover letter</option>
              <option value="preparation_pack">Preparation pack</option>
              <option value="portfolio">Portfolio</option>
              <option value="certificate">Certificate</option>
              <option value="other">Other</option>
            </select>
          </label>

          <label>
            Status
            <select
              value={form.status}
              onChange={(event) =>
                setForm((value) => ({
                  ...value,
                  status: event.target.value as DocumentRecord["status"],
                }))
              }
            >
              <option value="draft">Draft</option>
              <option value="ready">Ready</option>
              <option value="submitted">Submitted</option>
              <option value="superseded">Superseded</option>
            </select>
          </label>

          <label className="work-item-form-wide">
            Title
            <input
              required
              maxLength={240}
              value={form.title}
              onChange={(event) =>
                setForm((value) => ({ ...value, title: event.target.value }))
              }
            />
          </label>

          <label>
            {editingId ? "Replacement file" : "File"}
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <label>
            Source URL
            <input
              type="url"
              value={form.source_url}
              onChange={(event) =>
                setForm((value) => ({ ...value, source_url: event.target.value }))
              }
            />
          </label>

          <label className="work-item-form-wide">
            Notes
            <textarea
              rows={2}
              value={form.notes}
              onChange={(event) =>
                setForm((value) => ({ ...value, notes: event.target.value }))
              }
            />
          </label>

          <button type="submit" disabled={busy || !form.title.trim()}>
            {busy ? "Saving…" : editingId ? "Save document changes" : "Add document"}
          </button>

          {editingId && (
            <button type="button" className="secondary" disabled={busy} onClick={cancelEdit}>
              Cancel edit
            </button>
          )}
        </form>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {error && !loading && documents.length === 0 && (
        <button type="button" className="secondary" onClick={() => void load()}>
          Retry documents
        </button>
      )}

      {loading ? (
        <p role="status">Loading documents…</p>
      ) : documents.length === 0 ? (
        <p className="work-items-empty">No document records yet.</p>
      ) : (
        <ul className="work-item-list">
          {documents.map((document) => (
            <li key={document.document_id}>
              <div>
                <strong>{document.title}</strong>
                <span>
                  {document.document_type.replaceAll("_", " ")} · {document.status}
                </span>

                {document.has_file && (
                  <p>
                    Stored in JOLT: {document.stored_filename} ·{" "}
                    {fileSizeLabel(document.file_size)}
                  </p>
                )}

                {document.source_url && (
                  <p>
                    <a href={document.source_url} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                  </p>
                )}

                {document.notes && <p>{document.notes}</p>}
              </div>

              <div>
                <span className="work-item-status">{document.status}</span>

                {document.has_file && (
                  <a
                    className="secondary"
                    href={`${apiBase}/api/application-documents/${document.document_id}/file`}
                  >
                    Download file
                  </a>
                )}

                {!readOnly && (
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => edit(document)}
                  >
                    Edit document
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}