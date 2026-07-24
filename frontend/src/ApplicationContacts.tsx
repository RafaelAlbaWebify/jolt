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

export function ApplicationContacts({ apiBase, applicationId, onChanged, onError }: Props) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!applicationId) { setContacts([]); return; }
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/contacts`);
      if (!response.ok) throw new Error("Unable to load application contacts.");
      setContacts((await response.json()) as Contact[]);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application contact loading failed.");
    } finally { setLoading(false); }
  }, [apiBase, applicationId, onError]);

  useEffect(() => { void load(); }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId || !name.trim()) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiBase}/api/applications/${applicationId}/contacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(), role: role.trim(), company: company.trim(), email: email.trim(),
          phone: phone.trim(), linkedin_url: linkedinUrl.trim(), notes: notes.trim(),
        }),
      });
      if (!response.ok) throw new Error("The contact could not be created.");
      setName(""); setRole(""); setCompany(""); setEmail(""); setPhone(""); setLinkedinUrl(""); setNotes("");
      await load();
      await onChanged();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Application contact creation failed.");
    } finally { setBusy(false); }
  }

  if (!applicationId) return <section className="application-tab-placeholder"><h4>Create the preparation record first</h4><p>Contacts attach to a persisted application and its Timeline.</p></section>;

  return <section className="work-items-panel" aria-labelledby="application-contacts-heading">
    <div className="application-tab-heading"><div><p className="eyebrow">People involved</p><h4 id="application-contacts-heading">Contacts</h4></div><span>{contacts.length} recorded</span></div>
    <form className="work-item-form" onSubmit={submit}>
      <label>Name<input required maxLength={240} value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label>Role<input value={role} onChange={(event) => setRole(event.target.value)} /></label>
      <label>Company<input value={company} onChange={(event) => setCompany(event.target.value)} /></label>
      <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>Phone<input value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
      <label>LinkedIn URL<input type="url" value={linkedinUrl} onChange={(event) => setLinkedinUrl(event.target.value)} /></label>
      <label className="work-item-form-wide">Notes<textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <button type="submit" disabled={busy || !name.trim()}>{busy ? "Saving…" : "Add contact"}</button>
    </form>
    {loading ? <p role="status">Loading contacts…</p> : contacts.length === 0 ? <p className="work-items-empty">No contacts recorded yet.</p> : <ul className="work-item-list">{contacts.map((contact) => <li key={contact.contact_id}><div><strong>{contact.name}</strong><span>{[contact.role, contact.company].filter(Boolean).join(" · ") || "Role not recorded"}</span>{contact.email && <p><a href={`mailto:${contact.email}`}>{contact.email}</a></p>}{contact.phone && <p>{contact.phone}</p>}{contact.linkedin_url && <p><a href={contact.linkedin_url} target="_blank" rel="noreferrer">LinkedIn profile</a></p>}{contact.notes && <p>{contact.notes}</p>}</div></li>)}</ul>}
  </section>;
}
