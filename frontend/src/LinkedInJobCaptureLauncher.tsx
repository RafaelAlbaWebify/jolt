import { useCallback, useEffect, useState } from "react";

type CaptureStatus = {
  status: "idle" | "queued" | "running" | "completed" | "failed";
  search_url: string;
  max_jobs: number;
  max_pages: number;
  output_zip: string;
  started_at: string;
  completed_at: string;
  error: string;
};

type Props = {
  apiBase: string;
  active: boolean;
};

const DEFAULT_URL = "https://www.linkedin.com/jobs/search/";
const MAX_JOBS = 50;
const MAX_PAGES = 10;

function clampInteger(value: number, minimum: number, maximum: number) {
  if (!Number.isFinite(value)) return minimum;
  return Math.min(maximum, Math.max(minimum, Math.trunc(value)));
}

function readableApiError(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== "object") return fallback;

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((issue) => {
        if (!issue || typeof issue !== "object") return "";
        const record = issue as { loc?: unknown; msg?: unknown };
        const location = Array.isArray(record.loc)
          ? record.loc
              .filter((part) => part !== "body")
              .map(String)
              .join(" → ")
          : "";
        const message = typeof record.msg === "string" ? record.msg : "";
        if (!message) return "";
        return location ? `${location}: ${message}` : message;
      })
      .filter(Boolean);

    if (messages.length) return messages.join(" ");
  }

  return fallback;
}

function isBusy(status: CaptureStatus["status"]) {
  return status === "queued" || status === "running";
}

export function LinkedInJobCaptureLauncher({ apiBase, active }: Props) {
  const [searchUrl, setSearchUrl] = useState(DEFAULT_URL);
  const [maxJobs, setMaxJobs] = useState(10);
  const [maxPages, setMaxPages] = useState(3);
  const [status, setStatus] = useState<CaptureStatus>({
    status: "idle",
    search_url: "",
    max_jobs: 0,
    max_pages: 0,
    output_zip: "",
    started_at: "",
    completed_at: "",
    error: "",
  });
  const [error, setError] = useState("");

  const loadStatus = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/captures/linkedin/local/status`);
    if (!response.ok) throw new Error("Unable to load LinkedIn capture status.");
    setStatus((await response.json()) as CaptureStatus);
  }, [apiBase]);

  useEffect(() => {
    if (!active) return;
    void loadStatus().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Capture status failed.");
    });
  }, [active, loadStatus]);

  useEffect(() => {
    if (!active || !isBusy(status.status)) return;
    const interval = window.setInterval(() => {
      void loadStatus().catch((caught) => {
        setError(caught instanceof Error ? caught.message : "Capture status failed.");
      });
    }, 2_000);
    return () => window.clearInterval(interval);
  }, [active, loadStatus, status.status]);

  async function startCapture() {
    setError("");

    const safeMaxJobs = clampInteger(maxJobs, 1, MAX_JOBS);
    const safeMaxPages = clampInteger(maxPages, 1, MAX_PAGES);
    setMaxJobs(safeMaxJobs);
    setMaxPages(safeMaxPages);

    try {
      const response = await fetch(`${apiBase}/api/captures/linkedin/local`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_url: searchUrl,
          max_jobs: safeMaxJobs,
          max_pages: safeMaxPages,
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as unknown;
        throw new Error(
          readableApiError(payload, "The LinkedIn capture could not start."),
        );
      }
      setStatus((await response.json()) as CaptureStatus);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The LinkedIn capture could not start.");
    }
  }

  return (
    <section className="panel" aria-labelledby="linkedin-job-capture-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Primary job discovery</p>
          <h2 id="linkedin-job-capture-heading">Capture a LinkedIn job search</h2>
          <p>
            Paste the exact LinkedIn search URL after choosing your keywords, location, and filters.
            JOLT follows LinkedIn’s enabled Next control, deduplicates jobs across pages, verifies each
            detail panel, and sends verified listings directly to Review Inbox and Market Insights.
          </p>
        </div>
      </div>

      <div className="professional-capture-controls" aria-label="LinkedIn job capture settings">
        <label>
          LinkedIn search URL
          <input
            type="url"
            value={searchUrl}
            onChange={(event) => setSearchUrl(event.target.value)}
            placeholder={DEFAULT_URL}
          />
        </label>
        <div className="professional-capture-settings-grid">
          <label>
            Maximum jobs
            <input
              type="number"
              min="1"
              max={MAX_JOBS}
              value={maxJobs}
              onChange={(event) =>
                setMaxJobs(clampInteger(Number(event.target.value), 1, MAX_JOBS))
              }
            />
          </label>
          <label>
            Maximum pages
            <input
              type="number"
              min="1"
              max={MAX_PAGES}
              value={maxPages}
              onChange={(event) =>
                setMaxPages(clampInteger(Number(event.target.value), 1, MAX_PAGES))
              }
            />
          </label>
        </div>
        <button
          type="button"
          disabled={!active || isBusy(status.status) || !searchUrl.trim()}
          onClick={() => void startCapture()}
        >
          {isBusy(status.status) ? "Capture running…" : "Start LinkedIn job capture"}
        </button>
        <span>Use the visible local Chromium window. JOLT never requests or stores LinkedIn credentials.</span>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {status.status !== "idle" && (
        <div role="status">
          <strong>Status: {status.status}</strong>
          <p>{status.max_jobs} jobs maximum across {status.max_pages} page(s).</p>
          {status.status === "completed" && <p>Capture completed and the evidence ZIP was saved to Downloads.</p>}
          {status.status === "failed" && <p>{status.error || "Capture failed. Review the generated evidence package and backend logs."}</p>}
        </div>
      )}
    </section>
  );
}
