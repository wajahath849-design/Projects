import type { AuditResult } from "./types";

export const percent = (value: number, digits = 1) => Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : "—";
export const signedPercent = (value: number | null) => value === null ? "Not defined" : `${value > 0 ? "+" : ""}${percent(value)}`;
export const points = (value: number) => Number.isFinite(value) ? `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)} pp` : "—";
export const dateLabel = (value: string, year = false) => {
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(year ? { year: "numeric" } : {}) });
};
export const isReversed = (result: AuditResult) => result.stress_tests.find(test => test.name === "Fixed population mix")?.status !== "not_applicable" && result.headline.absolute_change * result.headline.adjusted_absolute_change < 0;
export const isDemo = (result: AuditResult) => result.audit_id === "MM-DEMO-042";
export function contractFor(result: AuditResult) {
  if (result.contract) return result.contract;
  const demo = isDemo(result);
  return {
    numerator_column: demo ? "conversions" : "numerator",
    denominator_column: demo ? "sessions" : "denominator",
    date_column: "date",
    segment_columns: demo ? ["device", "region"] : [],
    primary_segment: demo ? "device" : null,
    split_date: result.headline.split_date,
    baseline_start: result.time_series[0]?.date || "",
    baseline_end: result.time_series.filter(p => p.date < result.headline.split_date).at(-1)?.date || "",
    current_start: result.time_series.find(p => p.date >= result.headline.split_date)?.date || "",
    current_end: result.time_series.at(-1)?.date || "",
    column_count: demo ? 7 : 0,
  };
}
export function reviewLabel(result: AuditResult) {
  if (isReversed(result)) return "Direction reversed";
  if (result.findings.length || result.stress_tests.some(test => test.status === "warning" || test.status === "failed")) return "Review needed";
  if (result.stress_tests.some(test => test.status === "not_applicable")) return "Limited coverage";
  return "Checks passed";
}
export function downloadFile(name: string, content: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url; link.download = name; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
