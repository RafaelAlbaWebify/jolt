import { FormEvent, useCallback, useEffect, useState } from "react";

type EvidenceRoot = {
  configured: boolean;
  root_path: string | null;
  exists: boolean;
  writable: boolean;
  verified_at: string | null;
};

type Props = {
  apiBase: string;
  active: boolean;
  onChanged: () => void;
};

export function ProfessionalEvidenceRoot({ apiBase, active, onChanged }: Props) {
  const [settings, setSettings] = useState<EvidenceRoot | null>(null);
  const [rootPath, setRootPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/evidence-root`);
      if (!response.ok) throw new Error("Unable to load the local evidence directory.");
      const payload = (await response.json()) as EvidenceRoot;
      setSettings(payload);
      setRootPath(payload.root_path ?? "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Evidence directory failed.");
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (!active) return;
    void loadSettings();
  }, [active, loadSettings]);

  async function configure(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/professional-intelligence/evidence-root`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root_path: rootPath }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The evidence directory could not be verified.");
      }
      const payload = (await response.json()) as EvidenceRoot;
      setSettings(payload);
      setRootPath(payload.root_path ?? "");
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Evidence directory update failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!active) return null;
  if (!settings && loading && !error) return <p role="status">Preparing local evidence directory…</p>;

  const ready = Boolean(settings?.configured && settings.exists && settings.writable);
  const statusLabel = ready ? "Ready" : settings?.configured ? "Needs attention" : "Not configured";

  return (
    <section className="panel professional-evidence-root" aria-labelledby="professional-evidence-root-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Local evidence storage</p>
          <h2 id="professional-evidence-root-heading">Evidence directory</h2>
          <p>Supervised captures write their evidence files and manifests to a private local directory. JOLT creates a safe default beside its database automatically; enter another path only to move future evidence.</p>
        </div>
        <span className="professional-plan-status">{statusLabel}</span>
      </div>
      <form onSubmit={(event) => void configure(event)}>
        <label htmlFor="professional-evidence-root-path">Local directory path</label>
        <input
          id="professional-evidence-root-path"
          value={rootPath}
          onChange={(event) => setRootPath(event.target.value)}
          placeholder="C:\\Users\\ralba\\Documents\\JOLT Evidence"
          disabled={busy || loading}
        />
        <div className="professional-source-editor-actions">
          <button type="submit" disabled={busy || loading || !rootPath.trim()}>
            {busy ? "Saving…" : "Create or verify this directory"}
          </button>
          <button type="button" className="secondary" disabled={busy || loading} onClick={() => void loadSettings()}>
            {error ? "Retry evidence directory" : "Refresh status"}
          </button>
        </div>
      </form>
      {settings?.configured && (
        <p className="professional-ledger-note">
          Active path: <code>{settings.root_path}</code> · exists: {settings.exists ? "yes" : "no"} · writable: {settings.writable ? "yes" : "no"}
        </p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
