import { useEffect, useMemo, useState } from "react";

type LinkedInCapture = {
  captured_at: string;
};

type LinkedInProfileData = {
  capture_count: number;
  captures: LinkedInCapture[];
};

type FeedbackRecord = {
  reviewed_at: string;
  imported_at: string;
  review_version: string;
};

type FeedbackIndex = {
  total_import_count: number;
  records: FeedbackRecord[];
};

type Props = {
  apiBase: string;
  active: boolean;
  importRevision?: number;
};

type AnalysisState = "no_evidence" | "not_analyzed" | "stale" | "current";

function formatDate(value?: string) {
  if (!value) return "Never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function LinkedInAIAnalysisStatus({ apiBase, active, importRevision = 0 }: Props) {
  const [profile, setProfile] = useState<LinkedInProfileData | null>(null);
  const [feedback, setFeedback] = useState<FeedbackIndex | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return;

    let cancelled = false;
    setError("");

    void Promise.all([
      fetch(`${apiBase}/api/linkedin-command-center`).then(async (response) => {
        if (!response.ok) throw new Error("Unable to read LinkedIn profile evidence status.");
        return await response.json() as LinkedInProfileData;
      }),
      fetch(`${apiBase}/api/ai-linkedin/feedback`).then(async (response) => {
        if (!response.ok) throw new Error("Unable to read LinkedIn AI analysis status.");
        return await response.json() as FeedbackIndex;
      }),
    ])
      .then(([profileResult, feedbackResult]) => {
        if (cancelled) return;
        setProfile(profileResult);
        setFeedback(feedbackResult);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : "Unable to read LinkedIn AI status.");
      });

    return () => {
      cancelled = true;
    };
  }, [active, apiBase, importRevision]);

  const latestCaptureAt = useMemo(() => {
    const values = (profile?.captures ?? [])
      .map((capture) => new Date(capture.captured_at))
      .filter((date) => !Number.isNaN(date.getTime()))
      .sort((a, b) => b.getTime() - a.getTime());
    return values[0]?.toISOString();
  }, [profile]);

  const latestFeedback = feedback?.records?.[0];

  const analysisState: AnalysisState = useMemo(() => {
    if (!profile || profile.capture_count === 0 || !latestCaptureAt) return "no_evidence";
    if (!latestFeedback) return "not_analyzed";
    const captureTime = new Date(latestCaptureAt).getTime();
    const reviewedTime = new Date(latestFeedback.reviewed_at).getTime();
    if (Number.isNaN(reviewedTime) || captureTime > reviewedTime) return "stale";
    return "current";
  }, [latestCaptureAt, latestFeedback, profile]);

  const statusLabel = {
    no_evidence: "No profile evidence yet",
    not_analyzed: "Needs ChatGPT analysis",
    stale: "Analysis outdated",
    current: "Current",
  }[analysisState];

  const nextStep = {
    no_evidence: "Capture your enabled LinkedIn profile sections first.",
    not_analyzed: "Export the AI Work Package from Settings & Data, analyze it in ChatGPT, then import the returned update.",
    stale: "Your LinkedIn evidence is newer than the latest ChatGPT review. Export a fresh AI Work Package and run the round trip again.",
    current: "Your latest captured profile evidence has a ChatGPT review that is at least as recent.",
  }[analysisState];

  return (
    <section className="panel" aria-labelledby="linkedin-ai-analysis-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">AI round trip</p>
          <h3 id="linkedin-ai-analysis-heading">LinkedIn profile analysis</h3>
          <p>{nextStep}</p>
        </div>
        <strong>{statusLabel}</strong>
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      <div className="market-summary-grid">
        <article className="market-card">
          <span>Profile snapshots</span>
          <strong>{profile?.capture_count ?? 0}</strong>
        </article>
        <article className="market-card">
          <span>Latest profile capture</span>
          <strong>{formatDate(latestCaptureAt)}</strong>
        </article>
        <article className="market-card">
          <span>Latest ChatGPT review</span>
          <strong>{formatDate(latestFeedback?.reviewed_at)}</strong>
        </article>
        <article className="market-card">
          <span>Imported into JOLT</span>
          <strong>{formatDate(latestFeedback?.imported_at)}</strong>
        </article>
      </div>
    </section>
  );
}
