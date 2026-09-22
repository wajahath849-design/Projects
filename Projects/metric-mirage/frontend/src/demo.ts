import type { AuditResult } from "./types";

// Generated from the same deterministic fixture as the Django demo endpoint.
export const fallbackDemo: AuditResult = {
  "audit_id": "MM-DEMO-042",
  "generated_at": "2026-09-17T10:24:18.617620+00:00",
  "confidence_score": 56,
  "headline": {
    "metric_name": "Checkout conversion",
    "claim": "The new checkout increased conversion by more than 20%.",
    "baseline": 0.04816910262454817,
    "current": 0.06457434287956061,
    "absolute_change": 0.016405240255012443,
    "relative_change": 0.34057599916033987,
    "adjusted_baseline": 0.04816910262454817,
    "adjusted_current": 0.04222141050378837,
    "adjusted_absolute_change": -0.0059476921207597955,
    "adjusted_relative_change": -0.12347525273864463,
    "split_date": "2026-03-02",
    "baseline_label": "Before 2026-03-02",
    "current_label": "From 2026-03-02"
  },
  "verdict": {
    "label": "High decision risk",
    "summary": "The headline is directionally misleading after controlling for population composition.",
    "action": "Pause attribution. Present the segment-level and mix-adjusted result before making a rollout decision."
  },
  "contract": {
    "numerator_column": "conversions",
    "denominator_column": "sessions",
    "date_column": "date",
    "segment_columns": [
      "device",
      "region"
    ],
    "primary_segment": "device",
    "split_date": "2026-03-02",
    "baseline_start": "2026-01-05",
    "baseline_end": "2026-02-23",
    "current_start": "2026-03-02",
    "current_end": "2026-04-20",
    "column_count": 7,
    "source_name": null
  },
  "limitations": [
    "This before-and-after comparison does not establish causation or control for seasonality.",
    "The score summarizes detected issues with fixed severity penalties; it is not a calibrated probability that the claim is correct.",
    "Exact duplicate records are flagged but retained; this audit cannot determine whether they represent repeated observations.",
    "Segment analysis uses device only. Mix adjustment includes groups observed in both periods and renormalizes their weights.",
    "The reliability test assumes independent observations; repeated users and clustered events can violate this assumption."
  ],
  "findings": [
    {
      "id": "segment-reversal",
      "category": "Aggregation risk",
      "severity": "high",
      "title": "The aggregate trend reverses inside every major segment",
      "summary": "The overall metric moved +1.64 pp, while each device segment moved in the opposite direction.",
      "evidence": "This is a Simpson's-paradox pattern: the headline is being driven by who is in the dataset, not consistent improvement inside the groups.",
      "recommendation": "Do not present the aggregate change alone. Report device-level results and a mix-adjusted estimate.",
      "details": {
        "segment": "device",
        "rows": [
          {
            "segment": "Desktop",
            "baseline_rate": 0.07888631090487239,
            "current_rate": 0.07266573760700776,
            "baseline_share": 0.20320603488920322,
            "current_share": 0.7882306786975285
          },
          {
            "segment": "Mobile",
            "baseline_rate": 0.040335305719921104,
            "current_rate": 0.03445720637273064,
            "baseline_share": 0.7967939651107968,
            "current_share": 0.21176932130247156
          }
        ]
      }
    },
    {
      "id": "mix-shift",
      "category": "Composition drift",
      "severity": "high",
      "title": "The device mix changed materially",
      "summary": "Population composition shifted by 58.5% between periods.",
      "evidence": "Desktop moved from 20.3% to 78.8% of the denominator.",
      "recommendation": "Normalize both periods to a fixed segment mix before attributing the change to a product or policy.",
      "details": {
        "total_variation_distance": 0.5850246438083253,
        "rows": [
          {
            "segment": "Desktop",
            "baseline_rate": 0.07888631090487239,
            "current_rate": 0.07266573760700776,
            "baseline_share": 0.20320603488920322,
            "current_share": 0.7882306786975285
          },
          {
            "segment": "Mobile",
            "baseline_rate": 0.040335305719921104,
            "current_rate": 0.03445720637273064,
            "baseline_share": 0.7967939651107968,
            "current_share": 0.21176932130247156
          }
        ]
      }
    }
  ],
  "stress_tests": [
    {
      "name": "Fixed population mix",
      "status": "failed",
      "reported": "+1.64 pp",
      "challenged": "-0.59 pp",
      "explanation": "Reweights current device performance using the baseline composition."
    },
    {
      "name": "Segment consistency",
      "status": "failed",
      "reported": "Aggregate direction",
      "challenged": "Opposite inside segments",
      "explanation": "Checks whether the headline direction survives disaggregation."
    },
    {
      "name": "Outlier resistance",
      "status": "passed",
      "reported": "+1.64 pp",
      "challenged": "+1.59 pp",
      "explanation": "Removes denominator weights below the 1st or above the 99th percentile and recalculates the comparison."
    },
    {
      "name": "Sample reliability",
      "status": "passed",
      "reported": "Significant",
      "challenged": "p=0.0000",
      "explanation": "Uses a two-proportion normal approximation, assuming independent binary outcomes and at least five expected successes and failures in each period."
    },
    {
      "name": "Input completeness",
      "status": "passed",
      "reported": "65 rows",
      "challenged": "65 valid rows",
      "explanation": "Checks parsing, missing values, denominator validity and exact duplicates."
    }
  ],
  "segments": [
    {
      "segment": "Desktop",
      "baseline_rate": 0.07888631090487239,
      "current_rate": 0.07266573760700776,
      "baseline_share": 0.20320603488920322,
      "current_share": 0.7882306786975285
    },
    {
      "segment": "Mobile",
      "baseline_rate": 0.040335305719921104,
      "current_rate": 0.03445720637273064,
      "baseline_share": 0.7967939651107968,
      "current_share": 0.21176932130247156
    }
  ],
  "time_series": [
    {
      "date": "2026-01-05",
      "aggregate": 4.779874213836479,
      "desktop": 7.878787878787878,
      "mobile": 3.968253968253968
    },
    {
      "date": "2026-01-12",
      "aggregate": 4.919053549190536,
      "desktop": 8.09968847352025,
      "mobile": 4.124513618677042
    },
    {
      "date": "2026-01-19",
      "aggregate": 4.753199268738574,
      "desktop": 7.763975155279502,
      "mobile": 4.01819560272934
    },
    {
      "date": "2026-01-26",
      "aggregate": 4.789272030651341,
      "desktop": 7.668711656441718,
      "mobile": 4.032258064516129
    },
    {
      "date": "2026-02-02",
      "aggregate": 4.841833440929632,
      "desktop": 7.854984894259818,
      "mobile": 4.022988505747127
    },
    {
      "date": "2026-02-09",
      "aggregate": 4.878048780487805,
      "desktop": 8.227848101265822,
      "mobile": 4.053000779423227
    },
    {
      "date": "2026-02-16",
      "aggregate": 4.777070063694268,
      "desktop": 7.886435331230284,
      "mobile": 3.9904229848363926
    },
    {
      "date": "2026-02-23",
      "aggregate": 4.797507788161994,
      "desktop": 7.739938080495357,
      "mobile": 4.05616224648986
    },
    {
      "date": "2026-03-02",
      "aggregate": 6.405228758169934,
      "desktop": 7.131011608623548,
      "mobile": 3.7037037037037033
    },
    {
      "date": "2026-03-09",
      "aggregate": 6.462140992167102,
      "desktop": 7.242798353909465,
      "mobile": 3.4700315457413247
    },
    {
      "date": "2026-03-16",
      "aggregate": 6.5085158150851585,
      "desktop": 7.283763277693475,
      "mobile": 3.374233128834356
    },
    {
      "date": "2026-03-23",
      "aggregate": 6.340238543628374,
      "desktop": 7.091633466135458,
      "mobile": 3.5502958579881656
    },
    {
      "date": "2026-03-30",
      "aggregate": 6.409417920209287,
      "desktop": 7.23793677204659,
      "mobile": 3.3639143730886847
    },
    {
      "date": "2026-04-06",
      "aggregate": 6.70006261740764,
      "desktop": 7.476635514018691,
      "mobile": 3.5143769968051117
    },
    {
      "date": "2026-04-13",
      "aggregate": 6.55534941249227,
      "desktop": 7.330246913580248,
      "mobile": 3.4267912772585665
    },
    {
      "date": "2026-04-20",
      "aggregate": 6.283029947152084,
      "desktop": 7.322834645669292,
      "mobile": 3.233256351039261
    }
  ],
  "quality": {
    "total_rows": 65,
    "valid_rows": 65,
    "duplicate_rows": 0,
    "invalid_dates": 0,
    "invalid_values": 0,
    "invalid_denominators": 0
  },
  "methodology": {
    "tests_run": 5,
    "tests_available": 5,
    "engine": "Metric Mirage deterministic audit engine v1",
    "ai_used_for_calculation": false,
    "score_interpretation": "Heuristic issue score, not a calibrated probability. Skipped checks do not improve the score or establish confidence."
  }
};
