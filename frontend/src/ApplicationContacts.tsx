import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

type Contact = {
  contact_id: string;
  name: string;
  role: string;
  company: string;
  email: string;
  phone: string;
  linkedin_url: string;
  notes: string;
};

type Props = {
  apiBase: string;
  applicationId?: string | null;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

type ContactDraft = Omit<Contact, "contact_id">;

const EMPTY_DRAFT: ContactDraft = {
  name: "",
  role: "",
  company: "",
  email: "",
  phone: "",
  linkedin_url: "",
  notes: "",
};

export function ApplicationContacts({ apiBase, applicationId, onChanged, onError }: Props) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [draft, setDraft] = useState<ContactDraft>(EMPTY_DRAFT);
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!applicationId) {
      setContacts([]);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/contacts`);
      if (!response.ok) throw new Error("Unable to load application contacts.");
      setContacts((await response.json()) as Contact[]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Application contact loading failed.";
      setError(message);
      onError(message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, applicationId, onError]);

  useEffect(() => {
    setDraft(EMPTY_DRAFT);
    setEditingContactId(null);
    void load();
  }, [load]);

  function setField(field: keyof ContactDraft, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function beginEdit(contact: Contact) {
    setEditingContactId(contact.contact_id);
    setDraft({
      name: contact.name,
      role: contact.role,
      company: contact.company,
      email: contact.email,
      phone: contact.phone,
      linkedin_url: contact.linkedin_url,
      notes: contact.notes,
    });
    setError("");
  }

  function cancelEdit() {
    setEditingContactId(null);
    setDraft(EMPTY_DRAFT);
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId || !draft.name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const endpoint = editingContactId
        ? `${apiBase}/api/application-contacts/${editingContactId}/update`
        : `${apiBase}/api/applications/${applicationId}/contacts`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string | Array<{ msg?: string }> } | null;
        const detail = Array.isArray(payload?.detail)
          ? payload?.detail.map((item) => item.msg).filter(Boolean).join(" ")
          : payload?.detail;
        throw new Error(detail || (editingContactId ? "The contact could not be updated." : "The contact could not be created."));
      }
      setEditingContactId(null);
      setDraft(EMPTY_DRAFT);
      await load();
      await onChanged();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Application contact save failed.";
      setError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  }

  if (!applicationId) {
    return (
      <section className="application-tab-placeholder">
        <h4>Create the preparation record first</h4>
        <p>Contacts attach to a persisted application and its Timeline.</p>
      </section>
    );
  }

  return (
    <section className="work-items-panel" aria-labelledby="application-contacts-heading">
      <div className="application-tab-heading">
        <div>
          <p className="eyebrow">People involved</p>
          <h4 id="application-contacts-heading">Contacts</h4>
        </div>
        <span>{contacts.length} recorded</span>
      </div>
      <form className="work-item-form" onSubmit={submit}>
        <label>
          Name
          <input required maxLength={240} value={draft.name} onChange={(event) => setField("name", event.target.value)} />
        </label>
        <label>
          Role
          <input maxLength={240} value={draft.role} onChange={(event) => setField("role", event.target.value)} />
        </label>
        <label>
          Company
          <input maxLength={240} value={draft.company} onChange={(event) => setField("company", event.target.value)} />
        </label>
        <label>
          Email
          <input type="email" maxLength={320} value={draft.email} onChange={(event) => setField("email", event.target.value)} />
        </label>
        <label>
          Phone
          <input maxLength={80} value={draft.phone} onChange={(event) => setField("phone", event.target.value)} />
        </label>
        <label>
          LinkedIn URL
          <input type="url" maxLength={2048} value={draft.linkedin_url} onChange={(event) => setField("linkedin_url", event.target.value)} />
        </label>
        <label className="work-item-form-wide">
          Notes
          <textarea rows={2} maxLength={4000} value={draft.notes} onChange={(event) => setField("notes", event.target.value)} />
        </label>
        <div className="work-item-form-actions">
          <button type="submit" disabled={busy || !draft.name.trim()}>
            {busy ? "Saving…" : editingContactId ? "Save contact changes" : "Add contact"}
          </button>
          {editingContactId && (
            <button type="button" className="secondary" disabled={busy} onClick={cancelEdit}>
              Cancel edit
            </button>
          )}
        </div>
      </form>
      {error && (
        <div className="work-item-error">
          <p className="error" role="alert">{error}</p>
          <button type="button" className="secondary" disabled={loading || busy} onClick={() => void load()}>
            Retry contacts
          </button>
        </div>
      )}
      {loading ? (
        <p role="status">Loading contacts…</p>
      ) : contacts.length === 0 ? (
        <p className="work-items-empty">No contacts recorded yet.</p>
      ) : (
        <ul className="work-item-list">
          {contacts.map((contact) => (
            <li key={contact.contact_id}>
              <div>
                <strong>{contact.name}</strong>
                <span>{[contact.role, contact.company].filter(Boolean).join(" · ") || "Role not recorded"}</span>
                {contact.email && <p><a href={`mailto:${contact.email}`}>{contact.email}</a></p>}
                {contact.phone && <p>{contact.phone}</p>}
                {contact.linkedin_url && <p><a href={contact.linkedin_url} target="_blank" rel="noreferrer">LinkedIn profile</a></p>}
                {contact.notes && <p>{contact.notes}</p>}
              </div>
              <button type="button" className="secondary" disabled={busy} onClick={() => beginEdit(contact)}>
                Edit contact
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
