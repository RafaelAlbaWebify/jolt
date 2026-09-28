import {
  useEffect,
  useState,
} from "react";

type WorkMode =
  | "remote"
  | "hybrid"
  | "onsite";

type ShiftPreference =
  | "business_hours"
  | "flexible"
  | "evening"
  | "night"
  | "rotating"
  | "weekend";

type WorkloadPreference =
  | "normal"
  | "high"
  | "unknown";

type JobSearchPreferences = {
  target_titles: string[];
  preferred_work_modes: WorkMode[];
  base_locality: string;
  max_hybrid_distance_km: number;
  countries: string[];
  languages: string[];
  expected_salary_eur_min: number | null;
  expected_salary_eur_target: number | null;
  preferred_shifts: ShiftPreference[];
  excluded_shifts: ShiftPreference[];
  preferred_workload: WorkloadPreference;
  excluded_keywords: string[];
  preferred_keywords: string[];
  notes: string;
};

type PreferenceDraft = {
  targetTitles: string;
  preferredWorkModes: WorkMode[];
  baseLocality: string;
  maxHybridDistanceKm: string;
  countries: string;
  languages: string;
  expectedSalaryEurMin: string;
  expectedSalaryEurTarget: string;
  preferredShifts: ShiftPreference[];
  excludedShifts: ShiftPreference[];
  preferredWorkload: WorkloadPreference;
  excludedKeywords: string;
  preferredKeywords: string;
  notes: string;
};

type EvaluationRefresh = {
  status: string;
  authoritative_engine: string;
  strategy_evaluation_count: number;
};

type Props = {
  apiBase: string;
  active: boolean;
  onEvaluationsRefreshed?: () => void;
};

const WORK_MODES: WorkMode[] = [
  "remote",
  "hybrid",
  "onsite",
];

const SHIFTS: ShiftPreference[] = [
  "business_hours",
  "flexible",
  "evening",
  "night",
  "rotating",
  "weekend",
];

function label(value: string) {
  return value.replaceAll("_", " ");
}

function listText(values: string[]) {
  return values.join("\n");
}

function parseList(value: string) {
  return Array.from(
    new Set(
      value
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function optionalNumber(
  value: string,
) {
  const trimmed = value.trim();

  if (!trimmed) {
    return null;
  }

  return Number(trimmed);
}

function toDraft(
  preferences: JobSearchPreferences,
): PreferenceDraft {
  return {
    targetTitles:
      listText(preferences.target_titles),
    preferredWorkModes:
      [...preferences.preferred_work_modes],
    baseLocality:
      preferences.base_locality,
    maxHybridDistanceKm:
      String(preferences.max_hybrid_distance_km),
    countries:
      listText(preferences.countries),
    languages:
      listText(preferences.languages),
    expectedSalaryEurMin:
      preferences.expected_salary_eur_min === null
        ? ""
        : String(
            preferences.expected_salary_eur_min,
          ),
    expectedSalaryEurTarget:
      preferences.expected_salary_eur_target === null
        ? ""
        : String(
            preferences.expected_salary_eur_target,
          ),
    preferredShifts:
      [...preferences.preferred_shifts],
    excludedShifts:
      [...preferences.excluded_shifts],
    preferredWorkload:
      preferences.preferred_workload,
    excludedKeywords:
      listText(preferences.excluded_keywords),
    preferredKeywords:
      listText(preferences.preferred_keywords),
    notes:
      preferences.notes,
  };
}

function toPayload(
  draft: PreferenceDraft,
): JobSearchPreferences {
  return {
    target_titles:
      parseList(draft.targetTitles),
    preferred_work_modes:
      draft.preferredWorkModes,
    base_locality:
      draft.baseLocality.trim(),
    max_hybrid_distance_km:
      Number(draft.maxHybridDistanceKm),
    countries:
      parseList(draft.countries),
    languages:
      parseList(draft.languages),
    expected_salary_eur_min:
      optionalNumber(
        draft.expectedSalaryEurMin,
      ),
    expected_salary_eur_target:
      optionalNumber(
        draft.expectedSalaryEurTarget,
      ),
    preferred_shifts:
      draft.preferredShifts,
    excluded_shifts:
      draft.excludedShifts,
    preferred_workload:
      draft.preferredWorkload,
    excluded_keywords:
      parseList(draft.excludedKeywords),
    preferred_keywords:
      parseList(draft.preferredKeywords),
    notes:
      draft.notes.trim(),
  };
}

async function responseError(
  response: Response,
  fallback: string,
) {
  const payload = await response
    .json()
    .catch(() => null) as
      | { detail?: unknown }
      | null;

  if (
    payload
    && typeof payload.detail === "string"
  ) {
    return new Error(payload.detail);
  }

  return new Error(fallback);
}

function toggleValue<T extends string>(
  values: T[],
  value: T,
) {
  return values.includes(value)
    ? values.filter(
        (item) => item !== value,
      )
    : [...values, value];
}

export function JobPreferences({
  apiBase,
  active,
  onEvaluationsRefreshed,
}: Props) {
  const [draft, setDraft] =
    useState<PreferenceDraft | null>(null);
  const [loading, setLoading] =
    useState(false);
  const [saving, setSaving] =
    useState(false);
  const [error, setError] =
    useState("");
  const [notice, setNotice] =
    useState("");

  async function loadPreferences() {
    setLoading(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch(
        `${apiBase}/api/job-search-preferences`,
      );

      if (!response.ok) {
        throw await responseError(
          response,
          "Unable to load job-search preferences.",
        );
      }

      const loaded =
        (await response.json()) as JobSearchPreferences;

      setDraft(
        toDraft(loaded),
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load job-search preferences.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (
      active
      && !draft
      && !loading
      && !error
    ) {
      void loadPreferences();
    }
  }, [
    active,
    draft,
    error,
    loading,
  ]);

  function validate(
    payload: JobSearchPreferences,
  ) {
    if (!payload.target_titles.length) {
      return "Keep at least one target job title.";
    }

    if (!payload.preferred_work_modes.length) {
      return "Select at least one preferred work mode.";
    }

    if (!payload.base_locality) {
      return "Base location is required.";
    }

    if (
      !Number.isInteger(
        payload.max_hybrid_distance_km,
      )
      || payload.max_hybrid_distance_km < 0
      || payload.max_hybrid_distance_km > 500
    ) {
      return (
        "Hybrid distance must be a whole number "
        + "between 0 and 500 km."
      );
    }

    if (!payload.countries.length) {
      return "Keep at least one allowed country or region.";
    }

    if (!payload.languages.length) {
      return "Keep at least one supported human language.";
    }

    const salaryValues = [
      payload.expected_salary_eur_min,
      payload.expected_salary_eur_target,
    ].filter(
      (value): value is number =>
        value !== null,
    );

    if (
      salaryValues.some(
        (value) =>
          !Number.isInteger(value)
          || value < 0
          || value > 250000,
      )
    ) {
      return (
        "Salary values must be whole euro amounts "
        + "between 0 and 250000."
      );
    }

    if (
      payload.expected_salary_eur_min !== null
      && payload.expected_salary_eur_target !== null
      && payload.expected_salary_eur_target
        < payload.expected_salary_eur_min
    ) {
      return (
        "Target salary expectation cannot be lower "
        + "than minimum salary."
      );
    }

    const shiftConflict =
      payload.preferred_shifts.find(
        (shift) =>
          payload.excluded_shifts.includes(
            shift,
          ),
      );

    if (shiftConflict) {
      return (
        `${label(shiftConflict)} cannot be both `
        + "preferred and excluded."
      );
    }

    return "";
  }

  async function saveAndReevaluate() {
    if (!draft || saving) {
      return;
    }

    const payload =
      toPayload(draft);
    const validationError =
      validate(payload);

    if (validationError) {
      setError(validationError);
      setNotice("");
      return;
    }

    setSaving(true);
    setError("");
    setNotice("");

    try {
      const saveResponse = await fetch(
        `${apiBase}/api/job-search-preferences`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify(
            payload,
          ),
        },
      );

      if (!saveResponse.ok) {
        throw await responseError(
          saveResponse,
          "Preferences could not be saved.",
        );
      }

      const saved =
        (await saveResponse.json()) as JobSearchPreferences;

      setDraft(
        toDraft(saved),
      );

      const refreshResponse = await fetch(
        `${apiBase}/api/evaluations/refresh`,
        {
          method: "POST",
        },
      );

      if (!refreshResponse.ok) {
        setNotice(
          "Preferences were saved, but job matching could not refresh. "
          + "Your saved preferences are still preserved.",
        );
        return;
      }

      const refresh =
        (await refreshResponse.json()) as EvaluationRefresh;

      onEvaluationsRefreshed?.();

      setNotice(
        `Preferences saved. `
        + `${refresh.strategy_evaluation_count} jobs `
        + `refreshed.`,
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Preferences could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      className="job-preferences"
      aria-labelledby="job-preferences-heading"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            Matching preferences
          </p>
          <h3 id="job-preferences-heading">
            Job Search Preferences
          </h3>
          <p>
            These settings tell JOLT what kinds of jobs fit your search. Saving them refreshes job matching while preserving your decisions and applications.
          </p>
        </div>

        <button
          type="button"
          className="secondary"
          disabled={loading || saving}
          onClick={() =>
            void loadPreferences()
          }
        >
          {loading
            ? "Loading..."
            : "Reload saved"}
        </button>
      </div>

      {error && (
        <p
          className="error"
          role="alert"
        >
          {error}
        </p>
      )}

      {notice && (
        <p
          className="application-move-notice"
          role="status"
        >
          {notice}
        </p>
      )}

      {!draft && loading && (
        <p role="status">
          Loading job-search preferences...
        </p>
      )}

      {draft && (
        <form
          className="job-preferences-form"
          onSubmit={(event) => {
            event.preventDefault();
            void saveAndReevaluate();
          }}
        >
          <fieldset>
            <legend>
              Search scope
            </legend>

            <div className="job-preferences-grid">
              <label className="job-preferences-wide">
                <span>
                  Target job titles
                </span>
                <small>
                  One title per line.
                </small>
                <textarea
                  rows={7}
                  value={draft.targetTitles}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      targetTitles:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <span>
                  Countries / regions
                </span>
                <small>
                  One entry per line.
                </small>
                <textarea
                  rows={7}
                  value={draft.countries}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      countries:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <span>
                  Supported languages
                </span>
                <small>
                  Human languages you can
                  work in.
                </small>
                <textarea
                  rows={7}
                  value={draft.languages}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      languages:
                        event.target.value,
                    })
                  }
                />
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>
              Location and work pattern
            </legend>

            <div className="job-preferences-grid">
              <div>
                <span className="job-preferences-label">
                  Preferred work modes
                </span>

                <div className="job-preferences-checks">
                  {WORK_MODES.map(
                    (mode) => (
                      <label key={mode}>
                        <input
                          type="checkbox"
                          checked={
                            draft
                              .preferredWorkModes
                              .includes(mode)
                          }
                          onChange={() =>
                            setDraft({
                              ...draft,
                              preferredWorkModes:
                                toggleValue(
                                  draft
                                    .preferredWorkModes,
                                  mode,
                                ),
                            })
                          }
                        />
                        {label(mode)}
                      </label>
                    ),
                  )}
                </div>
              </div>

              <label>
                <span>
                  Base location
                </span>
                <input
                  value={draft.baseLocality}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      baseLocality:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <span>
                  Maximum hybrid distance
                </span>
                <div className="job-preferences-inline">
                  <input
                    type="number"
                    min="0"
                    max="500"
                    step="1"
                    value={
                      draft
                        .maxHybridDistanceKm
                    }
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        maxHybridDistanceKm:
                          event.target.value,
                      })
                    }
                  />
                  <span>km</span>
                </div>
              </label>

              <div>
                <span className="job-preferences-label">
                  Preferred schedules
                </span>

                <div className="job-preferences-checks">
                  {SHIFTS.map(
                    (shift) => (
                      <label key={shift}>
                        <input
                          type="checkbox"
                          checked={
                            draft
                              .preferredShifts
                              .includes(shift)
                          }
                          onChange={() =>
                            setDraft({
                              ...draft,
                              preferredShifts:
                                toggleValue(
                                  draft
                                    .preferredShifts,
                                  shift,
                                ),
                            })
                          }
                        />
                        {label(shift)}
                      </label>
                    ),
                  )}
                </div>
              </div>

              <div>
                <span className="job-preferences-label">
                  Unavailable schedules
                </span>

                <div className="job-preferences-checks">
                  {SHIFTS.map(
                    (shift) => (
                      <label key={shift}>
                        <input
                          type="checkbox"
                          checked={
                            draft
                              .excludedShifts
                              .includes(shift)
                          }
                          onChange={() =>
                            setDraft({
                              ...draft,
                              excludedShifts:
                                toggleValue(
                                  draft
                                    .excludedShifts,
                                  shift,
                                ),
                            })
                          }
                        />
                        {label(shift)}
                      </label>
                    ),
                  )}
                </div>
              </div>

              <label>
                <span>
                  Workload preference
                </span>
                <select
                  value={
                    draft.preferredWorkload
                  }
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      preferredWorkload:
                        (event.target.value as WorkloadPreference),
                    })
                  }
                >
                  <option value="normal">
                    Standard workload
                  </option>
                  <option value="high">
                    High-intensity roles are okay
                  </option>
                  <option value="unknown">
                    No preference
                  </option>
                </select>
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>
              Compensation and role signals
            </legend>
            <p className="job-preferences-help">
              Salary values are stored in EUR. Use the same basis consistently for minimum and target.
            </p>

            <div className="job-preferences-grid">
              <label>
                <span>
                  Minimum salary expectation
                </span>
                <div className="job-preferences-inline">
                  <span>EUR</span>
                  <input
                    type="number"
                    min="0"
                    max="250000"
                    step="1000"
                    value={
                      draft
                        .expectedSalaryEurMin
                    }
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        expectedSalaryEurMin:
                          event.target.value,
                      })
                    }
                  />
                </div>
              </label>

              <label>
                <span>
                  Target salary expectation
                </span>
                <div className="job-preferences-inline">
                  <span>EUR</span>
                  <input
                    type="number"
                    min="0"
                    max="250000"
                    step="1000"
                    value={
                      draft
                        .expectedSalaryEurTarget
                    }
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        expectedSalaryEurTarget:
                          event.target.value,
                      })
                    }
                  />
                </div>
              </label>

              <label>
                <span>
                  Preferred keywords
                </span>
                <small>
                  One keyword or phrase per line.
                </small>
                <textarea
                  rows={7}
                  value={
                    draft.preferredKeywords
                  }
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      preferredKeywords:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <span>
                  Excluded keywords
                </span>
                <small>
                  One keyword or phrase per line.
                </small>
                <textarea
                  rows={7}
                  value={
                    draft.excludedKeywords
                  }
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      excludedKeywords:
                        event.target.value,
                    })
                  }
                />
              </label>

              <label className="job-preferences-wide">
                <span>
                  Search notes
                </span>
                <textarea
                  rows={4}
                  value={draft.notes}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      notes:
                        event.target.value,
                    })
                  }
                />
              </label>
            </div>
          </fieldset>

          <div className="job-preferences-actions">
            <button
              type="submit"
              disabled={saving}
            >
              {saving
                ? "Saving preferences..."
                : "Save preferences"}
            </button>

            <span>
              JOLT refreshes job matching after save. Your review decisions and applications are preserved.
            </span>
          </div>
        </form>
      )}
    </section>
  );
}
