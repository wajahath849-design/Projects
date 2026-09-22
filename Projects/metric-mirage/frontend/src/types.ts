export type Severity = "critical" | "high" | "medium" | "low";
export type TestStatus = "passed" | "failed" | "warning" | "not_applicable";

export interface SegmentRow {
  segment: string;
  series_key?: string;
  baseline_rate: number;
  current_rate: number;
  baseline_share: number;
  current_share: number;
}

export interface Finding {
  id: string;
  category: string;
  severity: Severity;
  title: string;
  summary: string;
  evidence: string;
  recommendation: string;
  details: { rows?: SegmentRow[]; [key: string]: unknown };
}

export interface StressTest {
  name: string;
  status: TestStatus;
  reported: string;
  challenged: string;
  explanation: string;
}

export interface TimePoint {
  date: string;
  aggregate: number;
  desktop?: number;
  mobile?: number;
  [key: string]: string | number | undefined;
}

export interface AuditResult {
  audit_id: string;
  generated_at: string;
  confidence_score: number;
  headline: {
    metric_name: string;
    claim: string;
    baseline: number;
    current: number;
    absolute_change: number;
    relative_change: number | null;
    adjusted_baseline: number;
    adjusted_current: number;
    adjusted_absolute_change: number;
    adjusted_relative_change: number | null;
    split_date: string;
    baseline_label: string;
    current_label: string;
  };
  verdict: { label: string; summary: string; action: string };
  findings: Finding[];
  stress_tests: StressTest[];
  segments: SegmentRow[];
  time_series: TimePoint[];
  quality: {
    total_rows: number;
    valid_rows: number;
    duplicate_rows: number;
    invalid_dates: number;
    invalid_values: number;
    invalid_denominators: number;
  };
  contract?: {
    grouping_mode?: string;
    filters?: Record<string, (string | null)[]>;
    source_rows?: number;
    filtered_rows?: number;
    numerator_column: string;
    denominator_column: string;
    date_column: string;
    segment_columns: string[];
    primary_segment: string | null;
    split_date: string;
    baseline_start: string;
    baseline_end: string;
    current_start: string;
    current_end: string;
    column_count: number;
    source_name?: string | null;
  };
  limitations?: string[];
  methodology: { tests_run: number; engine: string; ai_used_for_calculation: boolean; score_interpretation?: string; tests_available?: number };
}

export type Page = "overview" | "audits" | "data" | "reports" | "method";
