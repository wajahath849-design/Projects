import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { analyzeUpload, fetchDemo } from "./api";
import { fallbackDemo } from "./demo";
import type { AuditResult } from "./types";

vi.mock("./api", () => ({ fetchDemo: vi.fn(), analyzeUpload: vi.fn() }));

function uploadedResult(): AuditResult {
  return {
    ...structuredClone(fallbackDemo),
    audit_id: "MM-TEST-001",
    confidence_score: 100,
    headline: {
      ...fallbackDemo.headline,
      metric_name: "Trial activation",
      claim: "Activation improved after the onboarding update.",
      absolute_change: .01,
      relative_change: .1,
      adjusted_absolute_change: .008,
      adjusted_relative_change: .08,
    },
    verdict: { label: "No issues detected", summary: "The assessed checks found no issues.", action: "Review the assumptions." },
    findings: [],
    segments: [
      { segment: "Organic", baseline_rate: .1, current_rate: .11, baseline_share: .5, current_share: .5 },
      { segment: "Referral", baseline_rate: .08, current_rate: .09, baseline_share: .5, current_share: .5 },
    ],
    time_series: [
      { date: "2026-01-05", aggregate: 9, organic: 10, referral: 8 },
      { date: "2026-03-02", aggregate: 10, organic: 11, referral: 9 },
    ],
    stress_tests: fallbackDemo.stress_tests.map(test => ({ ...test, status: "passed" as const })),
    contract: { ...fallbackDemo.contract!, numerator_column: "activated", denominator_column: "trials", segment_columns: ["channel"], primary_segment: "channel", source_name: "activation.csv" },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchDemo).mockResolvedValue(structuredClone(fallbackDemo));
  vi.stubGlobal("scrollTo", vi.fn());
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  }
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(function () { this.setAttribute("open", ""); });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Metric Mirage reviews", () => {
  it("clears a valid file when its replacement is invalid", async () => {
    render(<App />);
    await screen.findByText("Analysis service available");
    fireEvent.click(screen.getByRole("button", { name: "New review" }));
    const dialog = screen.getByRole("dialog");
    const input = within(dialog).getByLabelText("Upload CSV file");
    fireEvent.change(input, { target: { files: [new File(["date,conversions,sessions,category\n"], "shop.csv")] } });
    await waitFor(() => expect(within(dialog).getByRole("checkbox", { name: "category" })).toBeInTheDocument());
    fireEvent.change(input, { target: { files: [new File(["invalid"], "bad.txt")] } });
    expect(within(dialog).queryByRole("checkbox", { name: "category" })).not.toBeInTheDocument();
    fireEvent.submit(dialog.querySelector("form")!);
    expect(analyzeUpload).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a CSV file");
  });

  it("moves chart keyboard focus repeatedly across dates", async () => {
    render(<App />);
    await screen.findByText("Analysis service available");
    const targets = screen.getAllByRole("button", { name: /overall .* percent/ });
    targets[0].focus();
    fireEvent.keyDown(targets[0], { key: "ArrowRight" });
    expect(targets[1]).toHaveFocus();
    fireEvent.keyDown(targets[1], { key: "ArrowRight" });
    expect(targets[2]).toHaveFocus();
  });
  it("renders real sample findings and transparent score language", async () => {
    render(<App />);
    expect(await screen.findByText("Analysis service available")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Checkout conversion" })).toBeInTheDocument();
    expect(screen.getByText("+34.1%")).toBeInTheDocument();
    expect(screen.getByText("-12.3%")).toBeInTheDocument();
    expect(screen.getByText(/Not a probability that the claim is true/)).toBeInTheDocument();
  });

  it("shows an honest saved-sample state when the service is offline", async () => {
    vi.mocked(fetchDemo).mockRejectedValue(new Error("offline"));
    render(<App />);
    expect(await screen.findByText(/You're viewing a saved sample/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Checkout conversion" })).toBeInTheDocument();
  });

  it("opens check evidence and the actual metric definition", async () => {
    render(<App />);
    await screen.findByText("Analysis service available");
    fireEvent.click(screen.getByRole("tab", { name: /Checks\s*5/ }));
    expect(screen.getAllByText("Failed")).toHaveLength(2);
    fireEvent.click(screen.getByRole("tab", { name: "Data definition" }));
    expect(screen.getByText(/SUM\(conversions\)/)).toBeInTheDocument();
    expect(screen.getByText("5 Jan — 23 Feb 2026")).toBeInTheDocument();
    expect(screen.getByText("2 Mar — 20 Apr 2026")).toBeInTheDocument();
  });

  it("navigates to a usable report before invoking print", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<App />);
    await screen.findByText("Analysis service available");
    fireEvent.click(screen.getByRole("button", { name: "View report", exact: true }));
    expect(screen.getByRole("heading", { name: "A record worth keeping." })).toBeInTheDocument();
    expect(screen.getByText("Evidence & interpretation")).toBeInTheDocument();
    expect(print).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Print / save PDF" }));
    expect(print).toHaveBeenCalledOnce();
  });

  it("shows only real session reviews and supports search", async () => {
    render(<App />);
    await screen.findByText("Analysis service available");
    fireEvent.click(screen.getByRole("button", { name: /All reviews\s*1/ }));
    expect(screen.getByText("1 review")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Search reviews" }), { target: { value: "nonexistent" } });
    expect(screen.getByText("No reviews match “nonexistent”.")).toBeInTheDocument();
  });

  it("validates uploads, updates every page, and retains the new session review", async () => {
    vi.mocked(analyzeUpload).mockResolvedValue(uploadedResult());
    render(<App />);
    await screen.findByText("Analysis service available");
    fireEvent.click(screen.getByRole("button", { name: "New review" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Metric name"), { target: { value: "Trial activation" } });
    fireEvent.change(within(dialog).getByLabelText("Claim to review"), { target: { value: "Activation improved after the onboarding update." } });
    fireEvent.submit(dialog.querySelector("form")!);
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a CSV file");
    expect(analyzeUpload).not.toHaveBeenCalled();
    fireEvent.change(within(dialog).getByLabelText("Upload CSV file"), { target: { files: [new File(["date,activated,trials,channel\n2026-01-05,10,100,Organic"], "activation.csv", { type: "text/csv" })] } });
    await waitFor(() => expect(within(dialog).getByLabelText(/^Numerator/)).not.toBeDisabled());
    expect(within(dialog).getByRole("checkbox", { name: "channel" })).not.toBeChecked();
    fireEvent.change(within(dialog).getByLabelText(/^Numerator/), { target: { value: "activated" } });
    fireEvent.change(within(dialog).getByLabelText(/^Denominator/), { target: { value: "trials" } });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "channel" }));
    fireEvent.submit(dialog.querySelector("form")!);
    await screen.findByRole("heading", { level: 1, name: "Trial activation" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("Segment reversal detected.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Organic", exact: true })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Desktop", exact: true })).not.toBeInTheDocument();
    expect(analyzeUpload).toHaveBeenCalledWith(expect.objectContaining({ numerator: "activated", denominator: "trials", groupColumns: ["channel"] }));
    fireEvent.click(screen.getByRole("tab", { name: "Data definition" }));
    expect(screen.getByText(/SUM\(activated\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /All reviews\s*2/ }));
    expect(screen.getByText("2 reviews")).toBeInTheDocument();
    expect(screen.getByText("Trial activation")).toBeInTheDocument();
    expect(screen.getByText("Checkout conversion")).toBeInTheDocument();
  });

  it("shows unassessed checks without implying a successful adjusted result", async () => {
    const limited = uploadedResult();
    limited.segments = [];
    limited.stress_tests[0].status = "not_applicable";
    limited.methodology.tests_run = 4;
    vi.mocked(fetchDemo).mockResolvedValue(limited);
    render(<App />);
    await screen.findByText("Analysis service available");
    expect(screen.getByText("Limited coverage")).toBeInTheDocument();
    expect(screen.getByText("No comparable segment breakdown")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /Checks\s*5/ }));
    expect(screen.getByText("Not assessed")).toBeInTheDocument();
  });

  it("supports series toggles while keeping at least one line visible", async () => {
    render(<App />);
    await screen.findByText("Analysis service available");
    fireEvent.click(screen.getByRole("button", { name: "Desktop", exact: true }));
    expect(screen.getByRole("button", { name: "Desktop", exact: true })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "Mobile", exact: true }));
    fireEvent.click(screen.getByRole("button", { name: "Overall", exact: true }));
    expect(screen.getByRole("button", { name: "Overall", exact: true })).toHaveAttribute("aria-pressed", "true");
  });

  it("reports upload failures without losing the form", async () => {
    vi.mocked(analyzeUpload).mockRejectedValue(new Error("Missing required column: conversions"));
    render(<App />);
    await screen.findByText("Analysis service available");
    fireEvent.click(screen.getByRole("button", { name: "New review" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Upload CSV file"), { target: { files: [new File(["date,sessions"], "invalid.csv", { type: "text/csv" })] } });
    await waitFor(() => expect(within(dialog).getByLabelText(/^Numerator/)).not.toBeDisabled());
    fireEvent.submit(dialog.querySelector("form")!);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Missing required column"));
    expect(screen.getByRole("button", { name: "Run review" })).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
  });
});
