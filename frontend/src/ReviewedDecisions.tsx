import { useCallback, useEffect, useMemo, useState } from "react";

const REVIEW_CHOICES = ["pursue", "consider", "defer", "reject", "needs_more_information"] as const;
type ReviewChoice = typeof REVIEW_CHOICES[number];

type ReviewedOpportunity = {
  posting_id: string;
  evaluation_id: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  ranking_score: number;
  confidence: string;
  review_decision: ReviewChoice | null;
  application_id?: string | null;
};

type Props = {
  apiBase: string;
  onError: (message: string) => void;
};

function label(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "pending review";
}

export function ReviewedDecisions({ apiBase, onError }: Props) {
  const [items, setItems] = useState<ReviewedOpportunity[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const reviewedItems = useMemo(
    () => items.filter((item) => item.review_decision && !item.application_id),
    [items],
  );

  const refresh = useCallback(async () => {
    const response = await fetch(`${apiBase}/api/opportunity-index?include_reviewed=true`);
    if (!response.ok) throw new Error("Unable to load reviewed decisions.");
    setItems((await response.json()) as ReviewedOpportunity[]);
    setLoaded(true);
  }, [apiBase]);

  useEffect(() => {
    if (!loaded) return;
    refresh().catch((caught) => onError(caught instanceof Error ? caught.message : "Unable to refresh reviewed decisions."));
  }, [loaded, onError, refresh]);

  async function loadWhenOpened(open: boolean) {
    if (!open || loaded || busy) return;
    setBusy(true);
    try {
      await refresh();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unable to load reviewed decisions.");
    } finally {
      setBusy(false);
    }
  }

  async function correctDecision(item: ReviewedOpportunity, decision: ReviewChoice) {
    if (busy || decision === item.review_decision) return;
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/opportunities/${item.posting_id}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ evaluation_id: item.evaluation_id, decision }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The review decision could not be updated.");
      }
      await refresh();
      setNotice(`${item.title || "Opportunity"} decision updated to ${label(decision)}.`);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unable to update review decision.");
    } finally {
      setBusy(false);
    }
  }

  async function startApplication(item: ReviewedOpportunity) {
    if (busy || item.review_decision !== "pursue") return;
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/opportunities/${item.posting_id}/applications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: "Started from reviewed decisions." }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail || "The application could not be started.");
      }
      await refresh();
      setNotice(`${item.title || "Opportunity"} moved to Application Pipeline.`);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Unable to start application.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="reviewed-decisions-heading">
      <details onToggle={(event) => void loadWhenOpened(event.currentTarget.open)}>
        <summary>Reviewed decisions</summary>
        <div className="section-heading">
          <div>
            <h2 id="reviewed-decisions-heading">Reviewed decisions</h2>
            <p>Correct reviewed opportunities and start applications without deleting review history.</p>
          </div>
          <button type="button" disabled={busy || !loaded} onClick={() => refresh().catch(() => onError("Unable to refresh reviewed decisions."))}>
            Refresh reviewed
          </button>
        </div>
        {notice && <p className="application-move-notice" role="status">{notice}</p>}
        {!loaded || (busy && items.length === 0) ? <p>Loading reviewed decisions…</p> : reviewedItems.length === 0 ? <p>No reviewed decisions outside the application pipeline.</p> : (
          <div className="queue reviewed-decisions">
            {reviewedItems.map((item) => (
              <article key={item.posting_id}>
                <div>
                  <h3>{item.title || "Untitled opportunity"}</h3>
                  <p>{[item.company, item.location].filter(Boolean).join(" · ")}</p>
                  <p>{item.ranking_score} score · {item.confidence} confidence</p>
                  {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Open source job</a>}
                </div>
                <div className="professional-source-editor-actions">
                  <label className="decision-control">
                    <span>Decision</span>
                    <select
                      aria-label={`Correct decision for ${item.title || "untitled opportunity"}`}
                      value={item.review_decision ?? ""}
                      disabled={busy}
                      onChange={(event) => void correctDecision(item, event.target.value as ReviewChoice)}
                    >
                      {REVIEW_CHOICES.map((choice) => (
                        <option value={choice} key={choice}>{label(choice)}</option>
                      ))}
                    </select>
                  </label>
                  {item.review_decision === "pursue" && (
                    <button type="button" disabled={busy} onClick={() => void startApplication(item)}>
                      Start application
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </details>
    </section>
  );
}
