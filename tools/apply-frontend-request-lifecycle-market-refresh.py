from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected marker not found: {label}")
    return text.replace(old, new, 1)


def patch_workbench(root: Path) -> None:
    path = root / "frontend/src/Workbench.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '<MarketIntelligence apiBase={API_BASE} />',
        '<MarketIntelligence apiBase={API_BASE} active={activeView === "market"} />',
        "market active contract",
    )
    path.write_text(text, encoding="utf-8")


def write_market(root: Path) -> None:
    path = root / "frontend/src/MarketIntelligence.tsx"
    path.write_text(
        '''import { useCallback, useEffect, useRef, useState } from "react";

type Metric = { label: string; count: number };
type SalaryMention = { title: string; company: string; mention: string };
type ScopeData = {
  total_roles: number;
  strong_roles: number;
  viable_roles: number;
  role_families: Metric[];
  work_modes: Metric[];
  seniority: Metric[];
  top_companies: Metric[];
  top_locations: Metric[];
  top_skills: Metric[];
  fit_distribution: Metric[];
  top_gaps: Metric[];
  study_priorities: Metric[];
  salary_mentions: SalaryMention[];
  salary_coverage: number;
};
type MarketData = {
  total_unique_roles: number;
  target_role_count: number;
  outside_target_count: number;
  target: ScopeData;
  all: ScopeData;
  outside_title_examples: Metric[];
  fit_explanation: string;
};

type Props = { apiBase: string; active: boolean };
type Scope = "target" | "all";

function Ranking({ title, items, empty }: { title: string; items: Metric[]; empty?: string }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="market-card">
      <h3>{title}</h3>
      {items.length === 0 ? <p>{empty ?? "No evidence detected in this scope."}</p> : (
        <div className="market-ranking">
          {items.map((item) => (
            <div className="market-ranking-row" key={item.label}>
              <div><strong>{item.label}</strong><span>{item.count}</span></div>
              <div className="market-bar"><span style={{ width: `${(item.count / maximum) * 100}%` }} /></div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function MarketIntelligence({ apiBase, active }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
  const [scope, setScope] = useState<Scope>("target");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const hasActivatedRef = useRef(false);

  const load = useCallback(async () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/market-intelligence`, { signal: controller.signal });
      if (!response.ok) throw new Error("Unable to load market intelligence.");
      const loaded = (await response.json()) as MarketData;
      if (requestRef.current !== controller) return;
      setData(loaded);
      setLastRefreshedAt(new Date().toISOString());
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      if (requestRef.current === controller) {
        setError(caught instanceof Error ? caught.message : "Market intelligence failed.");
      }
    } finally {
      if (requestRef.current === controller) setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (!active || hasActivatedRef.current) return;
    hasActivatedRef.current = true;
    void load();
  }, [active, load]);

  useEffect(() => () => requestRef.current?.abort(), []);

  const selected = data?.[scope] ?? null;

  return (
    <section className="panel market-workspace" aria-labelledby="market-heading">
      <div className="section-heading market-heading">
        <div>
          <p className="eyebrow">Market intelligence</p>
          <h2 id="market-heading">Market</h2>
          <p>Separate your target market from search noise, then focus applications and study effort.</p>
          {lastRefreshedAt && <p className="market-refreshed">Last refreshed {new Date(lastRefreshedAt).toLocaleString()}</p>}
        </div>
        <div className="market-heading-actions">
          <button type="button" className="secondary" disabled={!active || loading} onClick={() => void load()}>
            {loading ? "Refreshing…" : data ? "Refresh market" : "Load market"}
          </button>
          {data && (
            <div className="market-scope" aria-label="Market scope">
              <button type="button" className={scope === "target" ? "filter-active" : "secondary"} onClick={() => setScope("target")}>Target roles ({data.target_role_count})</button>
              <button type="button" className={scope === "all" ? "filter-active" : "secondary"} onClick={() => setScope("all")}>All captured ({data.total_unique_roles})</button>
            </div>
          )}
        </div>
      </div>

      {loading && !data && <p role="status">Loading market intelligence…</p>}
      {error && (
        <div className="market-load-error">
          <p className="error" role="alert">{error}</p>
          <button type="button" className="secondary" disabled={loading || !active} onClick={() => void load()}>Retry market load</button>
        </div>
      )}
      {data && selected && (
        <>
          <div className="market-summary">
            <div><strong>{selected.total_roles}</strong><span>{scope === "target" ? "Target roles" : "Captured roles"}</span></div>
            <div><strong>{selected.strong_roles}</strong><span>Strong matches</span></div>
            <div><strong>{selected.viable_roles}</strong><span>Strong or viable</span></div>
            <div><strong>{selected.salary_coverage}</strong><span>With salary evidence</span></div>
          </div>

          <div className="market-guidance">
            <strong>How to read fit</strong>
            <p>{data.fit_explanation}</p>
            {scope === "target" && <p><strong>{data.outside_target_count}</strong> captured roles are outside your target path and are excluded from this view.</p>}
          </div>

          <div className="market-grid">
            <Ranking title="Target role families" items={selected.role_families} />
            <Ranking title="Work mode" items={selected.work_modes} />
            <Ranking title="Fit distribution" items={selected.fit_distribution} />
            <Ranking title="Most requested skills" items={selected.top_skills} />
            <Ranking title="Most common capability gaps" items={selected.top_gaps} empty="No strategy-profile gaps were found in this scope." />
            <Ranking title="Highest-return study topics" items={selected.study_priorities} empty="No preparation topics were generated for this scope." />
            <Ranking title="Seniority" items={selected.seniority} />
            <Ranking title="Companies hiring repeatedly" items={selected.top_companies.filter((item) => item.count > 1)} empty="No employer appears more than once in this scope." />
            <Ranking title="Top locations" items={selected.top_locations} />
          </div>

          {scope === "target" && (
            <Ranking title="Outside-target titles to remove from future searches" items={data.outside_title_examples} empty="No outside-target captures were detected." />
          )}

          <section className="market-card market-salary">
            <div className="market-card-heading">
              <h3>Salary evidence</h3>
              <span>{selected.salary_coverage} of {selected.total_roles} roles contain detectable salary text</span>
            </div>
            {selected.salary_mentions.length === 0 ? (
              <p>No salary ranges were detected. JOLT does not estimate missing salaries.</p>
            ) : (
              <div className="market-salary-list">
                {selected.salary_mentions.map((item, index) => (
                  <div key={`${item.title}-${item.company}-${index}`}>
                    <strong>{item.mention}</strong>
                    <span>{item.title} · {item.company}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
''',
        encoding="utf-8",
    )


def patch_app(root: Path) -> None:
    path = root / "frontend/src/App.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, '  const [loading, setLoading] = useState(false);\n', '  const [loading, setLoading] = useState(false);\n  const [error, setError] = useState("");\n', "source error state")
    text = replace_once(
        text,
        '''    setLoading(true);\n    try {\n      const response = await fetch(`${API_BASE}/api/opportunities/${postingId}/identity-evidence`);\n      if (response.ok) setData((await response.json()) as SourceEvidence);\n    } finally {\n      setLoading(false);\n    }\n''',
        '''    setLoading(true);\n    setError("");\n    try {\n      const response = await fetch(`${API_BASE}/api/opportunities/${postingId}/identity-evidence`);\n      if (!response.ok) throw new Error("Unable to load source evidence.");\n      setData((await response.json()) as SourceEvidence);\n    } catch (caught) {\n      setError(caught instanceof Error ? caught.message : "Source evidence failed.");\n    } finally {\n      setLoading(false);\n    }\n''',
        "source error handling",
    )
    text = replace_once(text, '      {loading && <p>Loading sources…</p>}\n', '      {loading && <p>Loading sources…</p>}\n      {error && <p className="error" role="alert">{error}</p>}\n      {error && <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>Retry sources</button>}\n', "source retry UI")
    text = replace_once(text, '  const inspectorTriggerRef = useRef<HTMLButtonElement | null>(null);\n', '  const inspectorTriggerRef = useRef<HTMLButtonElement | null>(null);\n  const detailRequestRef = useRef<AbortController | null>(null);\n', "detail request ref")
    text = replace_once(text, '      setError(message);\n      throw caught;\n', '      setError(message);\n', "safe refresh rejection")
    old_detail = '''  const loadDetail = useCallback(async (postingId: string) => {\n    setDetailLoading(true);\n    setSelectedDetail(null);\n    try {\n      const response = await fetch(`${API_BASE}/api/opportunity-detail/${postingId}`);\n      if (!response.ok) throw new Error("Unable to load opportunity details.");\n      setSelectedDetail((await response.json()) as OpportunityDetail);\n    } catch (caught) {\n      setError(caught instanceof Error ? caught.message : "Opportunity detail failed.");\n    } finally {\n      setDetailLoading(false);\n    }\n  }, []);\n'''
    new_detail = '''  const loadDetail = useCallback(async (postingId: string) => {\n    detailRequestRef.current?.abort();\n    const controller = new AbortController();\n    detailRequestRef.current = controller;\n    setDetailLoading(true);\n    setSelectedDetail(null);\n    setError("");\n    try {\n      const response = await fetch(`${API_BASE}/api/opportunity-detail/${postingId}`, { signal: controller.signal });\n      if (!response.ok) throw new Error("Unable to load opportunity details.");\n      const detail = (await response.json()) as OpportunityDetail;\n      if (detailRequestRef.current === controller) setSelectedDetail(detail);\n    } catch (caught) {\n      if (caught instanceof DOMException && caught.name === "AbortError") return;\n      if (detailRequestRef.current === controller) {\n        setError(caught instanceof Error ? caught.message : "Opportunity detail failed.");\n      }\n    } finally {\n      if (detailRequestRef.current === controller) setDetailLoading(false);\n    }\n  }, []);\n'''
    text = replace_once(text, old_detail, new_detail, "abortable opportunity detail")
    text = replace_once(text, '    if (!hasLoaded) refreshOpportunities().catch(() => setError("The JOLT API is not available."));\n', '    if (!hasLoaded) void refreshOpportunities();\n', "safe initial refresh")
    text = replace_once(text, '    if (!selectedOpportunityId) return;\n', '    if (!selectedOpportunityId) {\n      detailRequestRef.current?.abort();\n      setDetailLoading(false);\n      setSelectedDetail(null);\n      return;\n    }\n', "abort on inspector close")
    path.write_text(text, encoding="utf-8")


def patch_application_dashboard(root: Path) -> None:
    path = root / "frontend/src/ApplicationDashboard.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, '  const movingApplicationIds = useRef(new Set<string>());\n', '  const movingApplicationIds = useRef(new Set<string>());\n  const detailRequestRef = useRef<AbortController | null>(null);\n', "application detail request ref")
    old = '''      setDetailLoading(true);\n      try {\n        const response = await fetch(`${apiBase}/api/applications/${applicationId}`);\n        if (!response.ok) throw new Error("Unable to load application history.");\n        setApplicationDetail((await response.json()) as ApplicationDetail);\n      } catch (caught) {\n        setError(caught instanceof Error ? caught.message : "Application history failed.");\n      } finally {\n        setDetailLoading(false);\n      }\n'''
    new = '''      detailRequestRef.current?.abort();\n      const controller = new AbortController();\n      detailRequestRef.current = controller;\n      setDetailLoading(true);\n      setError("");\n      try {\n        const response = await fetch(`${apiBase}/api/applications/${applicationId}`, { signal: controller.signal });\n        if (!response.ok) throw new Error("Unable to load application history.");\n        const detail = (await response.json()) as ApplicationDetail;\n        if (detailRequestRef.current === controller) setApplicationDetail(detail);\n      } catch (caught) {\n        if (caught instanceof DOMException && caught.name === "AbortError") return;\n        if (detailRequestRef.current === controller) {\n          setError(caught instanceof Error ? caught.message : "Application history failed.");\n        }\n      } finally {\n        if (detailRequestRef.current === controller) setDetailLoading(false);\n      }\n'''
    text = replace_once(text, old, new, "abortable application detail")
    text = replace_once(text, '      if (!applicationId) {\n        setApplicationDetail(null);\n        return;\n      }\n', '      if (!applicationId) {\n        detailRequestRef.current?.abort();\n        setApplicationDetail(null);\n        setDetailLoading(false);\n        return;\n      }\n', "abort absent application")
    path.write_text(text, encoding="utf-8")


def patch_professional(root: Path) -> None:
    path = root / "frontend/src/ProfessionalIntelligence.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'import { useEffect, useMemo, useState } from "react";\n', 'import { useCallback, useEffect, useMemo, useState } from "react";\n', "professional callback import")
    old_effect = '''  useEffect(() => {\n    if (!active || loaded || loading) return;\n    setLoading(true);\n    setError("");\n    fetch(`${apiBase}/api/professional-intelligence/sources`)\n      .then((response) => {\n        if (!response.ok) throw new Error("Unable to load Professional Intelligence sources.");\n        return response.json() as Promise<ProfessionalIntelligenceSource[]>;\n      })\n      .then((items) => {\n        setSources(items);\n        setLoaded(true);\n      })\n      .catch((caught) => setError(caught instanceof Error ? caught.message : "Source registry failed."))\n      .finally(() => setLoading(false));\n  }, [active, apiBase, loaded, loading]);\n'''
    new_effect = '''  const loadSources = useCallback(async () => {\n    setLoading(true);\n    setError("");\n    try {\n      const response = await fetch(`${apiBase}/api/professional-intelligence/sources`);\n      if (!response.ok) throw new Error("Unable to load Professional Intelligence sources.");\n      setSources((await response.json()) as ProfessionalIntelligenceSource[]);\n      setLoaded(true);\n    } catch (caught) {\n      setError(caught instanceof Error ? caught.message : "Source registry failed.");\n    } finally {\n      setLoading(false);\n    }\n  }, [apiBase]);\n\n  useEffect(() => {\n    if (!active || loaded) return;\n    void loadSources();\n  }, [active, loadSources, loaded]);\n'''
    text = replace_once(text, old_effect, new_effect, "professional stable loader")
    text = replace_once(text, '      {error && <p className="error" role="alert">{error}</p>}\n', '      {error && <p className="error" role="alert">{error}</p>}\n      {error && !loaded && <button type="button" className="secondary" disabled={loading} onClick={() => void loadSources()}>Retry source registry</button>}\n', "professional retry")
    path.write_text(text, encoding="utf-8")


def patch_runs(root: Path) -> None:
    path = root / "frontend/src/ProfessionalCaptureRuns.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, '  const [loaded, setLoaded] = useState(false);\n', '  const [loaded, setLoaded] = useState(false);\n  const [loading, setLoading] = useState(false);\n', "run loading state")
    text = replace_once(
        text,
        '''  const loadRuns = useCallback(async () => {\n    const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`);\n    if (!response.ok) throw new Error("Unable to load the Professional Intelligence run ledger.");\n    setRuns((await response.json()) as ProfessionalCaptureRun[]);\n    setLoaded(true);\n  }, [apiBase]);\n''',
        '''  const loadRuns = useCallback(async () => {\n    setLoading(true);\n    setError("");\n    try {\n      const response = await fetch(`${apiBase}/api/professional-intelligence/capture-runs`);\n      if (!response.ok) throw new Error("Unable to load the Professional Intelligence run ledger.");\n      setRuns((await response.json()) as ProfessionalCaptureRun[]);\n      setLoaded(true);\n    } catch (caught) {\n      setError(caught instanceof Error ? caught.message : "Run ledger failed.");\n    } finally {\n      setLoading(false);\n    }\n  }, [apiBase]);\n''',
        "run stable loader",
    )
    text = replace_once(
        text,
        '''  useEffect(() => {\n    if (!active || loaded) return;\n    void loadRuns().catch((caught) => {\n      setError(caught instanceof Error ? caught.message : "Run ledger failed.");\n    });\n  }, [active, loadRuns, loaded]);\n''',
        '''  useEffect(() => {\n    if (!active || loaded) return;\n    void loadRuns();\n  }, [active, loadRuns, loaded]);\n''',
        "run effect no retry storm",
    )
    text = replace_once(text, '      {!loaded && active && <p role="status">Loading supervised run history…</p>}\n', '      {loading && active && <p role="status">Loading supervised run history…</p>}\n      {error && !loaded && <button type="button" className="secondary" disabled={loading} onClick={() => void loadRuns()}>Retry run history</button>}\n', "run retry UI")
    path.write_text(text, encoding="utf-8")


def add_tests(root: Path) -> None:
    path = root / "frontend/src/MarketIntelligence.test.tsx"
    path.write_text(
        '''import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarketIntelligence } from "./MarketIntelligence";

const EMPTY_SCOPE = {
  total_roles: 0,
  strong_roles: 0,
  viable_roles: 0,
  role_families: [],
  work_modes: [],
  seniority: [],
  top_companies: [],
  top_locations: [],
  top_skills: [],
  fit_distribution: [],
  top_gaps: [],
  study_priorities: [],
  salary_mentions: [],
  salary_coverage: 0,
};

const MARKET = {
  total_unique_roles: 1,
  target_role_count: 1,
  outside_target_count: 0,
  target: { ...EMPTY_SCOPE, total_roles: 1 },
  all: { ...EMPTY_SCOPE, total_roles: 1 },
  outside_title_examples: [],
  fit_explanation: "Stable fit explanation.",
};

describe("MarketIntelligence", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not fetch while hidden and loads on first activation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => MARKET });
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(<MarketIntelligence apiBase="http://api" active={false} />);
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<MarketIntelligence apiBase="http://api" active />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
  });

  it("shows a stable failure and retries only when requested", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, json: async () => MARKET });
    vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load market intelligence.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry market load" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
  });

  it("refreshes explicitly after initial data is loaded", async () => {
    const updated = { ...MARKET, fit_explanation: "Updated fit explanation." };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => MARKET })
      .mockResolvedValueOnce({ ok: true, json: async () => updated });
    vi.stubGlobal("fetch", fetchMock);
    render(<MarketIntelligence apiBase="http://api" active />);

    expect(await screen.findByText("Stable fit explanation.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh market" }));
    expect(await screen.findByText("Updated fit explanation.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
''',
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    patch_workbench(root)
    write_market(root)
    patch_app(root)
    patch_application_dashboard(root)
    patch_professional(root)
    patch_runs(root)
    add_tests(root)
    print("Frontend request lifecycle and Market refresh patch applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
