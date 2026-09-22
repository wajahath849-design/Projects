import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { analyzeUpload } from "../api";
import type { AuditResult } from "../types";
import { Icon } from "./Icon";
import { csvHeaders, csvValues } from "../csv";
import ScopePicker from "./ScopePicker";
import type { Filters } from "./ScopePicker";

export default function UploadDialog({ onClose, onComplete }: { onClose: () => void; onComplete: (result: AuditResult, fileName: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [columns, setColumns] = useState<string[]>([]);
  const [values, setValues] = useState<Filters>({});
  const [groups, setGroups] = useState<string[]>([]);
  const [filters, setFilters] = useState<Filters>({});
  const reader = useRef<FileReader | null>(null);
  const [form, setForm] = useState({ metricName: "", claim: "", numerator: "", denominator: "", dateColumn: "", segmentColumns: "", splitDate: "" });
  useEffect(() => () => reader.current?.abort(), []);
  useEffect(() => { dialog.current?.showModal(); const previous = document.body.style.overflow; document.body.style.overflow = "hidden"; return () => { document.body.style.overflow = previous; }; }, []);
  const choose = (candidate?: File) => {
    if (busy) return;
    setError("");
    if (!candidate) return;
    reader.current?.abort();
    setFile(null); setColumns([]);
    setValues({}); setGroups([]); setFilters({});
    setForm(current => ({ ...current, numerator: "", denominator: "", dateColumn: "", segmentColumns: "", splitDate: "" }));
    if (!candidate.name.toLowerCase().endsWith(".csv")) { setError("Choose a .csv file to continue."); return; }
    if (candidate.size > 10 * 1024 * 1024) { setError("This file exceeds the 10 MB limit."); return; }
    const next = new FileReader();
    reader.current = next;
    next.onload = () => {
      try {
        const headers = csvHeaders(String(next.result));
        setValues(csvValues(String(next.result)));
        setColumns(headers); setFile(candidate);
        const match = (names: string[]) => headers.find(header => names.includes(header.toLowerCase())) || "";
        setForm(current => ({ ...current, numerator: match(["conversions", "successes", "purchases", "activated"]), denominator: match(["sessions", "trials", "visitors"]), dateColumn: match(["date", "timestamp"]), segmentColumns: "" }));
      } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to read CSV headers."); }
    };
    next.onerror = () => setError("Unable to read this file. Please select it again.");
    next.readAsText(candidate);
  };
  const update = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) { setError("Choose a CSV file before starting the review."); return; }
    if (Object.values(filters).some(selected => !selected.length)) { setError("Select at least one value for each enabled filter, or turn the filter off."); return; }
    setBusy(true); setError("");
    try { const result = await analyzeUpload({ file, ...form, groupColumns: groups, filters }); onComplete(result, file.name); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The review could not be completed."); }
    finally { setBusy(false); }
  };
  return <dialog ref={dialog} className="audit-dialog" aria-labelledby="upload-title" onCancel={event => { if (busy) event.preventDefault(); else onClose(); }}>
    <form onSubmit={submit}>
      <div className="dialog-head"><div><span className="eyebrow">New review</span><h2 id="upload-title">Start with a question.</h2><p>Choose your data, define the metric, and state the claim you want to review.</p></div><button type="button" className="icon-button" aria-label="Close review dialog" onClick={onClose} disabled={busy}><Icon name="close"/></button></div>
      <fieldset disabled={busy}>
        <label className={`upload-zone ${dragging ? "dragging" : ""}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files[0]); }}>
          <input aria-label="Upload CSV file" type="file" accept=".csv,text/csv" onChange={event => choose(event.target.files?.[0])}/>
          <Icon name={file ? "file" : "upload"} size={26}/><strong>{file ? file.name : "Choose a CSV, or drop it here"}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB · Select to replace` : "Up to 10 MB. Your file is sent to this application's server for analysis."}</span>
        </label>
        <div className="form-grid"><label><span>Metric name</span><input autoComplete="off" value={form.metricName} onChange={event => update("metricName", event.target.value)} placeholder="e.g. Checkout conversion" required maxLength={120}/></label><label><span>Comparison starts <em>Optional</em></span><input type="date" value={form.splitDate} onChange={event => update("splitDate", event.target.value)}/></label><label className="full"><span>Claim to review</span><textarea value={form.claim} onChange={event => update("claim", event.target.value)} placeholder="e.g. The new checkout increased conversion by 20%." required maxLength={1000} rows={2}/></label></div>
        <div className="field-section"><h3>Map your columns</h3><p>{columns.length ? `${columns.length} columns found. Confirm the metric fields and choose how to group your data.` : "Choose a CSV to see its available columns."}</p></div>
        <div className="form-grid">{([{ key: "numerator", label: "Numerator", help: "Events or successes" }, { key: "denominator", label: "Denominator", help: "Eligible population" }, { key: "dateColumn", label: "Date", help: "Observation date" }] as const).map(field => <label key={field.key}><span>{field.label}</span><select value={form[field.key]} onChange={event => { update(field.key, event.target.value); setGroups(current => current.filter(column => column !== event.target.value)); }} required disabled={!file}><option value="">Select a column</option>{columns.map(column => <option key={column} value={column}>{column}</option>)}</select><small>{field.help}</small></label>)}</div>
        {file && <ScopePicker key={file.name} columns={columns.filter(column => ![form.numerator, form.denominator, form.dateColumn].includes(column))} values={values} groups={groups} filters={filters} onGroups={setGroups} onFilters={setFilters}/>}
        <p className="form-note">If no comparison date is set, the dataset is split at its middle unique date. Reviews remain available for this session.</p>
      </fieldset>
      {error && <div className="form-error" role="alert"><Icon name="warning"/>{error}</div>}
      <div className="dialog-footer"><button type="button" className="button" onClick={onClose} disabled={busy}>Cancel</button><button type="submit" className="button primary" disabled={busy}>{busy ? <><span className="spinner"/>Running checks…</> : <>Run review <Icon name="arrow" size={16}/></>}</button></div>
    </form>
  </dialog>;
}
