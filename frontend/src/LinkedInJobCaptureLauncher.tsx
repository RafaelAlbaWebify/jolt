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
const MIN_JOBS = 1;
const MAX_JOBS = 100;

function clampJobs(value: number) {
  if (!Number.isFinite(value)) return MIN_JOBS;
  return Math.min(MAX_JOBS, Math.max(MIN_JOBS, Math.trunc(value)));
}

function validationDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);

        const entry = item as {
          loc?: unknown;
          msg?: unknown;
        };

        const location = Array.isArray(entry.loc)
          ? entry.loc
              .map((part) => String(part))
              .filter((part) => part !== "body")
              .join(".")
          : "";

        const message = typeof entry.msg === "string"
          ? entry.msg
          : "Invalid value.";

        return location ? `${location}: ${message}` : message;
      })
      .join("; ");
  }

  if (detail && typeof detail === "object") {
    const entry = detail as { msg?: unknown };
    if (typeof entry.msg === "string") return entry.msg;
  }

  return "";
}

async function responseError(response: Response, fallback: string) {
  const payload = (await response.json().catch(() => null)) as
    | { detail?: unknown }
    | null;

  const detail = validationDetail(payload?.detail);
  return new Error(detail || fallback);
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
    try {
      const boundedMaxJobs = clampJobs(maxJobs);
      if (boundedMaxJobs !== maxJobs) setMaxJobs(boundedMaxJobs);

      const response = await fetch(`${apiBase}/api/captures/linkedin/local`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_url: searchUrl,
          max_jobs: boundedMaxJobs,
          max_pages: maxPages,
        }),
      });
      if (!response.ok) {
        throw await responseError(
          response,
          "The LinkedIn capture could not start.",
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
              min={MIN_JOBS}
              max={MAX_JOBS}
              value={maxJobs}
              onChange={(event) => setMaxJobs(clampJobs(Number(event.target.value)))}
            />
          </label>
          <label>
            Maximum pages
            <input
              type="number"
              min="1"
              max="10"
              value={maxPages}
              onChange={(event) => setMaxPages(Number(event.target.value))}
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
