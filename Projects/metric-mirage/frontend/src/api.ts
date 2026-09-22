import type { AuditResult } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "/api";

export async function fetchDemo(): Promise<AuditResult> {
  const response = await fetch(`${API_URL}/demo/`);
  if (!response.ok) throw new Error("The live API is unavailable.");
  return response.json();
}

export interface UploadConfig {
  file: File;
  metricName: string;
  claim: string;
  numerator: string;
  denominator: string;
  dateColumn: string;
  segmentColumns: string;
  groupColumns?: string[];
  filters?: Record<string, (string | null)[]>;
  splitDate: string;
}

export async function analyzeUpload(config: UploadConfig): Promise<AuditResult> {
  const body = new FormData();
  body.append("file", config.file);
  body.append("metric_name", config.metricName);
  body.append("claim", config.claim);
  body.append("numerator_column", config.numerator);
  body.append("denominator_column", config.denominator);
  body.append("date_column", config.dateColumn);
  body.append("segment_columns", config.segmentColumns);
  body.append("primary_segment_column", config.segmentColumns);
  if (config.groupColumns) body.append("group_columns", JSON.stringify(config.groupColumns));
  body.append("filters", JSON.stringify(config.filters || {}));
  if (config.splitDate) body.append("split_date", config.splitDate);

  const response = await fetch(`${API_URL}/analyze/`, { method: "POST", body });
  const payload = await response.json().catch(() => {
    throw new Error("The analysis service could not respond. Please check that it is running and try again.");
  });
  if (!response.ok) throw new Error(payload.detail || "The audit could not be completed.");
  return payload;
}
