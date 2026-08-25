import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  JobPreferences,
} from "./JobPreferences";


const savedPreferences = {
  target_titles: [
    "Application Support Engineer",
    "Technical Support Engineer",
  ],
  preferred_work_modes: [
    "remote",
    "hybrid",
  ],
  base_locality:
    "Vigo, Galicia, Spain",
  max_hybrid_distance_km: 30,
  countries: [
    "Spain",
    "European Union",
  ],
  languages: [
    "Spanish",
    "English",
  ],
  expected_salary_eur_min: 35000,
  expected_salary_eur_target: 45000,
  preferred_shifts: [
    "business_hours",
    "flexible",
  ],
  excluded_shifts: [
    "night",
    "rotating",
    "weekend",
  ],
  preferred_workload: "normal",
  excluded_keywords: [
    "dispatch",
  ],
  preferred_keywords: [
    "application support",
    "sql",
  ],
  notes:
    "Prefer stable support roles.",
};


describe(
  "JobPreferences",
  () => {
    afterEach(() => {
      cleanup();
      vi.unstubAllGlobals();
    });

    it(
      "loads, saves, re-evaluates and reports the active engine",
      async () => {
        const fetchMock = vi.fn()
          .mockResolvedValueOnce(
            new Response(
              JSON.stringify(
                savedPreferences,
              ),
              {
                status: 200,
                headers: {
                  "Content-Type":
                    "application/json",
                },
              },
            ),
          )
          .mockResolvedValueOnce(
            new Response(
              JSON.stringify({
                ...savedPreferences,
                max_hybrid_distance_km: 45,
              }),
              {
                status: 200,
                headers: {
                  "Content-Type":
                    "application/json",
                },
              },
            ),
          )
          .mockResolvedValueOnce(
            new Response(
              JSON.stringify({
                status: "refreshed",
                authoritative_engine:
                  "profile-rules-v10",
                strategy_evaluation_count: 182,
              }),
              {
                status: 200,
                headers: {
                  "Content-Type":
                    "application/json",
                },
              },
            ),
          );

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const onRefreshed =
          vi.fn();

        render(
          <JobPreferences
            apiBase="http://api.test"
            active
            onEvaluationsRefreshed={
              onRefreshed
            }
          />,
        );

        expect(
          await screen.findByRole(
            "heading",
            {
              name:
                "Job Search Preferences",
            },
          ),
        ).toBeInTheDocument();

        const distance =
          await screen.findByDisplayValue(
            "30",
          );

        fireEvent.change(
          distance,
          {
            target: {
              value: "45",
            },
          },
        );

        fireEvent.click(
          screen.getByRole(
            "button",
            {
              name:
                "Save & re-evaluate jobs",
            },
          ),
        );

        await waitFor(() =>
          expect(
            onRefreshed,
          ).toHaveBeenCalledTimes(1),
        );

        expect(
          fetchMock,
        ).toHaveBeenNthCalledWith(
          2,
          "http://api.test/api/job-search-preferences",
          expect.objectContaining({
            method: "POST",
          }),
        );

        const request =
          (fetchMock.mock.calls[1][1] as RequestInit);

        const payload =
          JSON.parse(
            String(request.body),
          );

        expect(
          payload.max_hybrid_distance_km,
        ).toBe(45);

        expect(
          fetchMock,
        ).toHaveBeenNthCalledWith(
          3,
          "http://api.test/api/evaluations/refresh",
          {
            method: "POST",
          },
        );

        expect(
          await screen.findByText(
            /182 jobs re-evaluated with profile-rules-v10/i,
          ),
        ).toBeInTheDocument();
      },
    );

    it(
      "does not fetch preferences until the settings view is active",
      () => {
        const fetchMock =
          vi.fn();

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        render(
          <JobPreferences
            apiBase="http://api.test"
            active={false}
          />,
        );

        expect(
          fetchMock,
        ).not.toHaveBeenCalled();
      },
    );
  },
);
