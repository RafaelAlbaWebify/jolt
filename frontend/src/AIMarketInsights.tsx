import { useEffect, useState } from "react";

type MarketAction = {
  action_type: string;
  title: string;
  rationale: string;
  proposed_action: string;
  priority: "high" | "medium" | "low";
};

type ImportRecord = {
  id: string;
  source: string;
  summary: string;
  imported_at: string;
  action_count: number;
  actions: MarketAction[];
  raw_payload: Record<string, unknown>;
};

type ImportIndex = {
  import_count: number;
  latest_import: ImportRecord | null;
};

type Props = {
  apiBase: string;
  active: boolean;
};

function readable(value: string) {
  return value.replaceAll("_", " ");
}

export function AIMarketInsights({ apiBase, active }: Props) {
  const [latest, setLatest] = useState<ImportRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return;

    const controller = new AbortController();
    setLoading(true);
    setError("");

    void fetch(`${apiBase}/api/market-intelligence/preparation-import`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load AI Market Insights.");
        return (await response.json()) as ImportIndex;
      })
      .then((payload) => setLatest(payload.latest_import))
      .catch((caught) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "AI Market Insights failed.");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [active, apiBase]);

  if (!active) return null;

  return (
    <section className="panel" aria-labelledby="ai-market-insights-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">AI-reviewed market signal</p>
          <h2 id="ai-market-insights-heading">AI Market Insights</h2>
          <p>
            These recommendations come from the same source-first AI round as the
            Review Inbox. Raw JOLT charts below remain supporting evidence only.
          </p>
        </div>
      </div>

      {loading && <p role="status">Loading AI Market Insights…</p>}
      {error && <p className="error" role="alert">{error}</p>}

      {!loading && !error && !latest && (
        <p>
          No unified AI market analysis has been imported yet. Download the single
          ChatGPT package in Settings &amp; Data and import the returned JSON once.
        </p>
      )}

      {latest && (
        <>
          <p>
            <strong>{latest.summary || "Latest AI market review"}</strong>
            {" · "}
            {latest.action_count} action{latest.action_count === 1 ? "" : "s"}
            {" · "}
            {new Date(latest.imported_at).toLocaleString()}
          </p>

          {latest.actions.length > 0 && (
            <div className="market-overview-grid">
              {latest.actions.slice(0, 8).map((action, index) => (
                <article className="market-card" key={`${action.action_type}-${action.title}-${index}`}>
                  <span>{readable(action.action_type)} · {action.priority}</span>
                  <strong>{action.title}</strong>
                  {action.rationale && <p>{action.rationale}</p>}
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
