import { useEffect, useState } from "react";

type GitIdentity = {
  repository_root: string;
  branch: string;
  commit_sha: string;
  dirty: boolean | null;
  source: string;
};

type RuntimeIdentity = {
  service: string;
  version: string;
  git: GitIdentity;
  loaded_git: GitIdentity;
  database: {
    database_url: string;
    database_path: string | null;
    alembic_revision: string;
    record_counts: Record<string, number | null>;
  };
  evidence_root: {
    configured: boolean;
    root_path: string | null;
    exists: boolean;
    writable: boolean;
    verified_at: string | null;
  };
  process: {
    process_id: number;
    current_working_directory: string;
    python_executable: string;
    python_version: string;
    platform: string;
  };
};

type Props = {
  apiBase: string;
};

function shortSha(value: string) {
  return value && value !== "unknown" ? value.slice(0, 12) : value || "unknown";
}

function statusLabel(value: boolean | null) {
  if (value === null) return "unknown";
  return value ? "dirty" : "clean";
}

function runtimeIsStale(identity: RuntimeIdentity | null) {
  if (!identity) return false;
  const loaded = identity.loaded_git?.commit_sha;
  const checkout = identity.git?.commit_sha;
  if (!loaded || !checkout || loaded === "unknown" || checkout === "unknown") return false;
  return loaded !== checkout;
}

async function fetchRuntimeIdentity(apiBase: string): Promise<RuntimeIdentity> {
  const response = await fetch(`${apiBase}/api/runtime-identity`);
  if (!response.ok) throw new Error("Unable to load runtime identity.");
  return await response.json() as RuntimeIdentity;
}

export function RuntimeStalenessGuard({ apiBase }: Props) {
  const [identity, setIdentity] = useState<RuntimeIdentity | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchRuntimeIdentity(apiBase)
      .then((value) => {
        if (!cancelled) setIdentity(value);
      })
      .catch(() => {
        // Developer diagnostics retains the detailed fetch error. This guard stays silent
        // unless it has positive evidence that the loaded backend is stale.
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  if (!runtimeIsStale(identity)) return null;

  return (
    <section className="panel error" role="alert" aria-label="JOLT restart required">
      <strong>JOLT restart required — the backend is running old code.</strong>
      <p>
        Loaded backend {shortSha(identity!.loaded_git.commit_sha)} while the repository checkout is{" "}
        {shortSha(identity!.git.commit_sha)}. Stop and restart JOLT before capture, export, review, or import.
      </p>
    </section>
  );
}

export function RuntimeIdentityPanel({ apiBase }: Props) {
  const [identity, setIdentity] = useState<RuntimeIdentity | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadIdentity() {
    setLoading(true);
    setError("");
    try {
      setIdentity(await fetchRuntimeIdentity(apiBase));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Runtime identity failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadIdentity();
  }, [apiBase]);

  const stale = runtimeIsStale(identity);
  const healthySummary = identity
    ? stale
      ? `STALE · loaded ${shortSha(identity.loaded_git.commit_sha)} · checkout ${shortSha(identity.git.commit_sha)}`
      : `${identity.git.branch} · ${shortSha(identity.git.commit_sha)} · ${statusLabel(identity.git.dirty)}`
    : loading
      ? "checking runtime"
      : "runtime details";

  return (
    <details className="runtime-identity-panel">
      <summary>Developer diagnostics <span>{healthySummary}</span></summary>
      {loading && <p role="status">Checking active JOLT runtime…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {error && (
        <button type="button" className="secondary" disabled={loading} onClick={() => void loadIdentity()}>
          Retry runtime identity
        </button>
      )}
      {stale && identity && (
        <p className="error" role="alert">
          Backend restart required: loaded {shortSha(identity.loaded_git.commit_sha)} but checkout is{" "}
          {shortSha(identity.git.commit_sha)}.
        </p>
      )}
      {identity && (
        <div className="runtime-identity-grid">
          <div>
            <span>Loaded backend</span>
            <strong>{identity.loaded_git.branch} · {shortSha(identity.loaded_git.commit_sha)}</strong>
            <small>{statusLabel(identity.loaded_git.dirty)} · {identity.loaded_git.source}</small>
          </div>
          <div>
            <span>Repository checkout</span>
            <strong>{identity.git.branch} · {shortSha(identity.git.commit_sha)}</strong>
            <small>{statusLabel(identity.git.dirty)} · {identity.git.source}</small>
          </div>
          <div>
            <span>Database</span>
            <strong>{identity.database.database_path ?? identity.database.database_url}</strong>
            <small>Alembic {identity.database.alembic_revision}</small>
          </div>
          <div>
            <span>Records</span>
            <strong>
              {identity.database.record_counts.postings ?? "?"} opportunities ·{" "}
              {identity.database.record_counts.applications ?? "?"} applications
            </strong>
            <small>{identity.database.record_counts.professional_capture_runs ?? "?"} professional captures</small>
          </div>
          <div>
            <span>Evidence root</span>
            <strong>{identity.evidence_root.root_path ?? "not configured"}</strong>
            <small>
              {identity.evidence_root.configured
                ? `${identity.evidence_root.exists ? "exists" : "missing"} · ${identity.evidence_root.writable ? "writable" : "not writable"}`
                : "no configured root"}
            </small>
          </div>
          <div>
            <span>Process</span>
            <strong>PID {identity.process.process_id}</strong>
            <small>{identity.process.python_version} · {identity.process.current_working_directory}</small>
          </div>
        </div>
      )}
    </details>
  );
}
