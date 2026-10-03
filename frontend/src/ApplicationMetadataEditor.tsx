import { useEffect, useState } from "react";
import type { FormEvent } from "react";

type EditableApplication = {
  application_id: string;
  title: string;
  company: string;
  location: string;
  job_url?: string;
  source_url: string;
};

type SavedMetadata = {
  application_id: string;
  posting_id: string;
  status: string;
  title: string;
  company: string;
  location: string;
  job_url: string;
  application_url: string;
  notes: string;
  changed_fields: string[];
};

type Props = {
  apiBase: string;
  application: EditableApplication;
  onCancel: () => void;
  onSaved: (updated: SavedMetadata) => Promise<void>;
};

type FormState = {
  title: string;
  company: string;
  location: string;
  job_url: string;
  application_url: string;
  notes: string;
};

export function ApplicationMetadataEditor({
  apiBase,
  application,
  onCancel,
  onSaved,
}: Props) {
  const [form, setForm] = useState<FormState>({
    title: application.title,
    company: application.company,
    location: application.location,
    job_url: application.job_url ?? "",
    application_url: "",
    notes: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");

    fetch(`${apiBase}/api/applications/${application.application_id}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load application metadata.");
        return response.json() as Promise<{ application_url: string; notes: string }>;
      })
      .then((detail) => {
        setForm({
          title: application.title,
          company: application.company,
          location: application.location,
          job_url: application.job_url ?? "",
          application_url: detail.application_url,
          notes: detail.notes,
        });
      })
      .catch((caught) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "Unable to load application metadata.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [apiBase, application]);

  function setField(field: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || saving) return;

    setSaving(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/applications/${application.application_id}/metadata`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(payload?.detail || "The application metadata could not be saved.");
      }
      const updated = (await response.json()) as SavedMetadata;
      await onSaved(updated);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The application metadata could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="application-edit-overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target && !saving) onCancel();
      }}
    >
      <section
        className="application-edit-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="application-edit-title"
      >
        <div>
          <p className="eyebrow">Application metadata</p>
          <h3 id="application-edit-title">Edit {application.title || "application"}</h3>
          <p>Correct the active opportunity without replacing its application record or captured evidence.</p>
        </div>

        {loading && <p role="status">Loading current application details…</p>}
        {error && <p className="error application-edit-error" role="alert">{error}</p>}

        <form className="application-edit-form" onSubmit={save}>
          <label>
            Job title
            <input
              value={form.title}
              disabled={loading || saving}
              onChange={(event) => setField("title", event.target.value)}
            />
          </label>
          <label>
            Company
            <input
              value={form.company}
              disabled={loading || saving}
              onChange={(event) => setField("company", event.target.value)}
            />
          </label>
          <label>
            Location
            <input
              value={form.location}
              disabled={loading || saving}
              onChange={(event) => setField("location", event.target.value)}
            />
          </label>
          <label className="application-edit-wide">
            Job posting URL
            <input
              aria-label="Job posting URL"
              type="url"
              value={form.job_url}
              disabled={loading || saving}
              onChange={(event) => setField("job_url", event.target.value)}
              placeholder="https://employer.example/jobs/..."
            />
            <small>The current vacancy identity. Captured source evidence remains unchanged.</small>
          </label>
          <label className="application-edit-wide">
            Application/Apply URL
            <input
              aria-label="Application/Apply URL"
              type="url"
              value={form.application_url}
              disabled={loading || saving}
              onChange={(event) => setField("application_url", event.target.value)}
              placeholder="https://employer.example/apply/..."
            />
            <small>Use this only when the page used to submit the application differs from the job posting.</small>
          </label>
          <label className="application-edit-wide">
            Notes
            <textarea
              rows={3}
              value={form.notes}
              disabled={loading || saving}
              onChange={(event) => setField("notes", event.target.value)}
            />
          </label>

          <div className="application-edit-actions application-edit-wide">
            <button type="submit" disabled={loading || saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={saving}
              onClick={onCancel}
            >
              Cancel
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
