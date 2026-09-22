import { useEffect, useState } from "react";
import { fetchDemo } from "./api";
import { fallbackDemo } from "./demo";
import { Brand, Icon } from "./components/Icon";
import TrendChart from "./components/TrendChart";
import UploadDialog from "./components/UploadDialog";
import { contractFor, dateLabel, downloadFile, isDemo, isReversed, percent, points, reviewLabel, signedPercent } from "./presentation";
import type { AuditResult, Page, StressTest } from "./types";
import sampleCsv from "../../data/checkout_demo.csv?raw";

type ReviewTab = "summary" | "checks" | "definition";
type ReviewEntry = { key: string; result: AuditResult; name: string };
const navItems: { page: Page; name: string; icon: string }[] = [
  { page: "overview", name: "Review overview", icon: "overview" },
  { page: "audits", name: "All reviews", icon: "audit" },
  { page: "data", name: "Data & definitions", icon: "data" },
  { page: "reports", name: "Decision report", icon: "report" },
];

function Status({ status }: { status: StressTest["status"] }) {
  const labels = { passed: "Passed", failed: "Failed", warning: "Review", not_applicable: "Not assessed" };
  return <span className={`status ${status}`}><span/>{labels[status]}</span>;
}

function PageHeading({ eyebrow, title, subtitle, children }: { eyebrow: string; title: string; subtitle: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p></div>{children && <div className="page-actions">{children}</div>}</div>;
}

function Metrics({ result }: { result: AuditResult }) {
  const head = result.headline;
  const failed = result.stress_tests.filter(test => test.status === "failed").length;
  const passed = result.stress_tests.filter(test => test.status === "passed").length;
  const adjustedAvailable = result.segments.length > 0 && result.stress_tests.find(test => test.name === "Fixed population mix")?.status !== "not_applicable";
  return <div className="metric-strip">
    <div><span className="metric-label">Reported change <span className="metric-index">01</span></span><strong className="metric-number">{signedPercent(head.relative_change)}</strong><p>{percent(head.baseline, 2)} <span>→</span> {percent(head.current, 2)} <span className="metric-unit">{points(head.absolute_change)}</span></p><small>Relative change between periods</small></div>
    <div><span className="metric-label">With a fixed population mix <span className="metric-index">02</span></span><strong className={`metric-number ${isReversed(result) ? "caution-text" : ""}`}>{adjustedAvailable ? signedPercent(head.adjusted_relative_change) : "—"}</strong><p>{adjustedAvailable ? <>{points(head.adjusted_absolute_change)} <span className={isReversed(result) ? "change-flag" : "metric-unit"}>{isReversed(result) ? "Direction reversed" : "Adjusted movement"}</span></> : "No comparable segment breakdown"}</p><small>Current rates, weighted to baseline composition</small></div>
    <div><span className="metric-label">Checks completed <span className="metric-index">03</span></span><strong className="metric-number">{result.methodology.tests_run}<span className="metric-denominator"> / {result.stress_tests.length}</span></strong><p>{failed > 0 ? <span className="caution-text">{failed} failed</span> : <span>{passed} passed</span>}<span> · </span>{result.stress_tests.filter(test => test.status === "warning").length} for review</p><small>Open each check to inspect its assumptions</small></div>
  </div>;
}

function Findings({ result }: { result: AuditResult }) {
  return <section className="findings-section" aria-labelledby="findings-title"><div className="section-heading"><div><span className="eyebrow">Evidence</span><h2 id="findings-title">What needs your attention</h2></div><span className="subtle-count">{result.findings.length} findings</span></div>
    {result.findings.length === 0 ? <div className="empty-inline"><Icon name="check"/><div><strong>No findings from the available checks.</strong><p>This does not establish that the claimed cause produced the change.</p></div></div> : <div className="finding-list">{result.findings.map((finding, index) => <details className="finding" key={finding.id} open={index === 0 ? true : undefined}>
      <summary><span className="finding-number">{String(index + 1).padStart(2, "0")}</span><div><span className="finding-category">{finding.category}</span><h3>{finding.title}</h3></div><span className={`severity ${finding.severity}`}>{finding.severity}</span><Icon name="down" size={16}/></summary>
      <div className="finding-body"><p>{finding.summary}</p><div className="evidence-text"><span>Evidence</span><p>{finding.evidence}</p></div><div className="evidence-text"><span>Next step</span><p>{finding.recommendation}</p></div></div>
    </details>)}</div>}
  </section>;
}

function Checks({ result }: { result: AuditResult }) {
  return <section className="checks-section"><div className="section-heading"><div><span className="eyebrow">Sensitivity analysis</span><h2>Every check, with its evidence.</h2><p>Compare the reported result with the result under a different assumption.</p></div></div><div className="table-scroll"><table className="checks-table"><thead><tr><th>Check</th><th>Reported</th><th>After challenge</th><th>Result</th></tr></thead><tbody>{result.stress_tests.map(test => <tr key={test.name}><td><strong>{test.name}</strong><p>{test.explanation}</p></td><td>{test.reported}</td><td>{test.challenged}</td><td><Status status={test.status}/></td></tr>)}</tbody></table></div><p className="section-note"><Icon name="info" size={15}/> A passed check addresses one assumption. It does not establish a causal effect.</p></section>;
}

function Definition({ result, sourceName }: { result: AuditResult; sourceName: string }) {
  const contract = contractFor(result);
  const filters = Object.entries(contract.filters || {});
  const groupLabel = contract.segment_columns.join(" + ") || "None selected";
  return <section className="definition-section"><div className="section-heading"><div><span className="eyebrow">Metric definition</span><h2>How this result was calculated</h2><p>The fields and comparison periods used in this review.</p></div></div>
    <div className="formula"><span>Rate formula</span><code>SUM({contract.numerator_column}) <i>/</i> SUM({contract.denominator_column})</code></div>
    <dl className="definition-grid"><div><dt>Source</dt><dd>{sourceName}</dd></div><div><dt>Time column</dt><dd><code>{contract.date_column}</code></dd></div><div><dt>Baseline period</dt><dd>{dateLabel(contract.baseline_start)} — {dateLabel(contract.baseline_end, true)}</dd></div><div><dt>Comparison period</dt><dd>{dateLabel(contract.current_start)} — {dateLabel(contract.current_end, true)}</dd></div><div><dt>Grouped by</dt><dd>{groupLabel}</dd></div><div><dt>Filters</dt><dd>{filters.length ? filters.map(([column, selected]) => `${column}: ${selected.map(value => value ?? "(Missing)").join(", ")}`).join(" · ") : "All source rows"}</dd></div><div><dt>Rows included</dt><dd>{result.quality.valid_rows.toLocaleString()} of {(contract.source_rows ?? result.quality.total_rows).toLocaleString()} source rows</dd></div><div><dt>Exact duplicates</dt><dd>{result.quality.duplicate_rows} flagged</dd></div></dl>
    <div className="method-note"><Icon name="info"/><p>{contract.segment_columns.length > 1 ? `Mix adjustment uses the combined ${groupLabel} groups.` : contract.primary_segment ? `Mix adjustment uses ${contract.primary_segment}.` : "No segment mix adjustment was performed."} The comparison is observational; it cannot determine whether an intervention caused the change.</p></div>
  </section>;
}

function SegmentTable({ result }: { result: AuditResult }) {
  return <section className="segment-section"><div className="section-heading"><div><h2>Behind the aggregate</h2><p>Rates and population shares, side by side.</p></div><span className="column-tag">{contractFor(result).primary_segment || "Segments"}</span></div>
    {result.segments.length ? <div className="table-scroll"><table className="segment-table"><thead><tr><th>Segment</th><th>Before</th><th>After</th><th>Change</th><th>Population share</th></tr></thead><tbody>{result.segments.map((segment, index) => <tr key={segment.segment}><td><span className="segment-name"><i style={{ background: ["#b27b3e", "#6b8195", "#8b7294", "#89916e"][index % 4] }}/>{segment.segment}</span></td><td>{percent(segment.baseline_rate, 2)}</td><td>{percent(segment.current_rate, 2)}</td><td>{points(segment.current_rate - segment.baseline_rate)}</td><td><span className="share-values">{percent(segment.baseline_share, 0)} <span>→</span> {percent(segment.current_share, 0)}</span><div className="share-bars"><span style={{ width: `${segment.baseline_share * 100}%` }}/><span style={{ width: `${segment.current_share * 100}%` }}/></div></td></tr>)}</tbody></table></div> : <div className="empty-inline">No comparable segments. Add a segment column to examine population composition.</div>}
  </section>;
}

function ReviewSummary({ result, onReport, onMethod }: { result: AuditResult; onReport: () => void; onMethod: () => void }) {
  const reversal = isReversed(result);
  return <aside className="review-aside">
    <div className="aside-heading"><span className="eyebrow">Review note</span><Icon name="report" size={17}/></div>
    <h2>{reversal ? "The headline changes after adjustment." : result.findings.length ? "Read the findings before deciding." : "The available checks are complete."}</h2>
    <p>{result.verdict.summary}</p>
    <div className="recommendation"><span>Recommended next step</span><p>{result.verdict.action}</p></div>
    <div className="score-block"><div><span>Evidence score</span><strong>{result.confidence_score}<small>/100</small></strong></div><div className="score-track"><span style={{ width: `${result.confidence_score}%` }}/></div><p>A rule-based score of the checks performed. Not a probability that the claim is true.</p><button onClick={onMethod} className="text-link">How scoring works <Icon name="arrow" size={14}/></button></div>
    <button className="button aside-report" onClick={onReport}>Read decision report <Icon name="arrow" size={16}/></button>
    <div className="aside-foot"><Icon name="clock" size={14}/><span>Reviewed {dateLabel(result.generated_at, true)}</span></div>
  </aside>;
}

function Overview({ result, sourceName, onNew, onReport, onMethod }: { result: AuditResult; sourceName: string; onNew: () => void; onReport: () => void; onMethod: () => void }) {
  const [tab, setTab] = useState<ReviewTab>("summary");
  const reversed = isReversed(result);
  const range = result.time_series;
  const reversalFinding = result.findings.find(f => f.id === "segment-reversal");
  return <>
    <PageHeading eyebrow={`Review / ${result.audit_id}`} title={result.headline.metric_name} subtitle={`${dateLabel(range[0]?.date || result.generated_at)} – ${dateLabel(range.at(-1)?.date || result.generated_at, true)} · ${result.quality.total_rows.toLocaleString()} observations`}><button className="button" onClick={onReport}><Icon name="report" size={16}/>View report</button><button className="button primary" onClick={onNew}><Icon name="plus" size={17}/>New review</button></PageHeading>
    <section className="claim-section"><div className="claim-heading"><span className="eyebrow">Claim under review</span><span className={`review-status ${result.findings.length ? "needs-review" : ""}`}><i/>{reviewLabel(result)}</span></div><p>“{result.headline.claim}”</p><div className="claim-meta"><Icon name="file" size={14}/><span>{sourceName}</span>{isDemo(result) && <span className="sample-label">Sample dataset</span>}</div></section>
    <div className="review-tabs" role="tablist" aria-label="Review sections">{([{ id: "summary", name: "Overview" }, { id: "checks", name: "Checks", count: result.stress_tests.length }, { id: "definition", name: "Data definition" }] as const).map(item => <button key={item.id} role="tab" id={`tab-${item.id}`} aria-controls="review-panel" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.name}{"count" in item && <span>{item.count}</span>}</button>)}</div>
    <div id="review-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
      {tab === "summary" && <><Metrics result={result}/><div className="review-layout"><div className="review-main"><section className="chart-panel"><div className="section-heading"><div><span className="eyebrow">Trend comparison</span><h2>{reversalFinding ? "One metric. Two different stories." : "The result, across time and segments."}</h2></div><span className="chart-period">{dateLabel(result.headline.split_date)} split</span></div><TrendChart points={result.time_series} splitDate={result.headline.split_date} segments={result.segments}/><div className={`chart-note ${reversalFinding ? "caution" : ""}`}><Icon name={reversalFinding ? "warning" : "info"} size={17}/><p>{reversalFinding ? <><strong>Segment reversal detected.</strong> {reversalFinding.summary}</> : reversed ? "The adjusted direction differs from the overall result. Inspect the segment composition below." : "Compare the aggregate with each segment before interpreting the change."}</p></div></section><SegmentTable result={result}/><Findings result={result}/></div><ReviewSummary result={result} onReport={onReport} onMethod={onMethod}/></div></>}
      {tab === "checks" && <Checks result={result}/>}
      {tab === "definition" && <Definition result={result} sourceName={sourceName}/>}
    </div>
  </>;
}

function Reviews({ entries, onSelect, onNew }: { entries: ReviewEntry[]; onSelect: (entry: ReviewEntry) => void; onNew: () => void }) {
  const [query, setQuery] = useState("");
  const filtered = entries.filter(entry => `${entry.result.headline.metric_name} ${entry.result.headline.claim}`.toLowerCase().includes(query.toLowerCase()));
  return <><PageHeading eyebrow="Workspace" title="Your reviews" subtitle="An evidence trail for each question you investigate."><button className="button primary" onClick={onNew}><Icon name="plus"/>New review</button></PageHeading><div className="list-toolbar"><label className="search-field"><Icon name="search"/><input aria-label="Search reviews" placeholder="Search reviews…" value={query} onChange={event => setQuery(event.target.value)}/></label><span>{filtered.length} {filtered.length === 1 ? "review" : "reviews"}</span></div><div className="review-list">{filtered.map(entry => <button className="review-list-row" onClick={() => onSelect(entry)} key={entry.key}><span className="list-file-icon"><Icon name="audit" size={21}/></span><div><strong>{entry.result.headline.metric_name}</strong><p>{entry.result.headline.claim}</p><small>{isDemo(entry.result) ? "Sample" : "Uploaded CSV"} · {dateLabel(entry.result.generated_at, true)}</small></div><span className={`review-status ${entry.result.findings.length ? "needs-review" : ""}`}><i/>{reviewLabel(entry.result)}</span><Icon name="arrow"/></button>)}{!filtered.length && <div className="empty-inline">No reviews match “{query}”.</div>}</div><p className="section-note"><Icon name="info" size={15}/> Uploaded reviews are kept in this session. Download a report to keep a copy before refreshing.</p></>;
}

function DataPage({ result, sourceName, onNew }: { result: AuditResult; sourceName: string; onNew: () => void }) {
  return <><PageHeading eyebrow="Data & definitions" title="From source to conclusion." subtitle="Inspect the data and calculation behind the current review."><button className="button" onClick={() => downloadFile("checkout_demo.csv", sampleCsv, "text/csv")}><Icon name="download" size={16}/>Sample CSV</button><button className="button primary" onClick={onNew}><Icon name="upload" size={16}/>Review a CSV</button></PageHeading><section className="source-summary"><span className="list-file-icon"><Icon name="file" size={26}/></span><div><h2>{sourceName}</h2><p>{isDemo(result) ? "Synthetic checkout data with a deliberate shift in population composition." : "Uploaded for the current metric review."}</p></div><div className="source-count"><strong>{result.quality.total_rows}</strong><span>observations</span></div></section><Definition result={result} sourceName={sourceName}/></>;
}

function Report({ result, sourceName }: { result: AuditResult; sourceName: string }) {
  return <><PageHeading eyebrow="Decision report" title="A record worth keeping." subtitle="The claim, the evidence, and the reasoning behind the review."><button className="button" onClick={() => downloadFile(`${result.audit_id}.json`, JSON.stringify(result, null, 2))}><Icon name="download" size={16}/>Download evidence</button><button className="button primary" onClick={() => window.print()}><Icon name="print" size={16}/>Print / save PDF</button></PageHeading><article className="report-paper"><header className="report-masthead"><Brand/><div>{result.audit_id}<br/>{dateLabel(result.generated_at, true)}</div></header><div className="report-title"><span className="eyebrow">Metric review</span><h2>{result.headline.metric_name}</h2><p>“{result.headline.claim}”</p></div><div className="report-verdict"><span className={`review-status ${result.findings.length ? "needs-review" : ""}`}><i/>{reviewLabel(result)}</span><p>{result.verdict.summary}</p></div><Metrics result={result}/><div className="report-section"><h3>Evidence & interpretation</h3>{result.findings.length ? result.findings.map((finding, index) => <div className="report-finding" key={finding.id}><span>{String(index + 1).padStart(2, "0")}</span><div><h4>{finding.title}</h4><p>{finding.evidence}</p><p><strong>Next step:</strong> {finding.recommendation}</p></div></div>) : <p>No findings from the checks performed.</p>}</div><div className="report-recommendation"><span className="eyebrow">Recommended next step</span><p>{result.verdict.action}</p></div><div className="report-section"><h3>Scope & limitations</h3><p>Source: {sourceName}. {result.quality.valid_rows} observations included. Comparison begins {dateLabel(result.headline.split_date, true)}.</p><p>The evidence score is a transparent heuristic, not a probability. These observational checks do not establish causality. {result.stress_tests.filter(test => test.status === "not_applicable").length} checks were not assessed.</p></div><footer className="report-colophon"><span>Metric Mirage · Analytics review</span><span>Evidence score {result.confidence_score}/100</span></footer></article></>;
}

function MethodPage({ result }: { result: AuditResult }) {
  return <><PageHeading eyebrow="Methodology" title="Show your working." subtitle="A review should be as explainable as the conclusion it challenges."/><div className="method-layout"><div><section className="method-section"><span className="eyebrow">01 / Scope</span><h2>What the checks can tell you</h2><p>Metric Mirage compares a ratio across two time periods and tests whether its direction holds under a different population mix, segment breakdown, and treatment of large observations. It uses the columns you specify; it does not interpret or prove the causal meaning of a free-text claim.</p></section><section className="method-section"><span className="eyebrow">02 / Scoring</span><h2>One score, with visible assumptions</h2><p>The evidence score starts at 100. Findings subtract points according to severity: critical 28, high 22, medium 12, and low 6. The result is bounded at zero. Related findings can overlap, so this is a review heuristic, not a statistical confidence level.</p><div className="penalty-table">{[{ name: "Critical", points: 28 }, { name: "High", points: 22 }, { name: "Medium", points: 12 }, { name: "Low", points: 6 }].map(row => <div key={row.name}><span>{row.name}</span><strong>−{row.points}</strong></div>)}</div><p>Checks marked “Not assessed” do not validate that assumption. Always consider coverage alongside the score.</p></section><section className="method-section"><span className="eyebrow">03 / Interpretation</span><h2>Composition is not causation</h2><p>Mix adjustment asks what the current rate would be if the segment shares stayed at their baseline values. It does not remove every possible confounder. A randomized experiment or a justified causal design is needed to attribute a change to an intervention.</p></section></div><aside className="method-reference"><h3>Current review</h3><p>{result.headline.metric_name}</p><dl><div><dt>Evidence score</dt><dd>{result.confidence_score}/100</dd></div><div><dt>Checks assessed</dt><dd>{result.methodology.tests_run}/{result.stress_tests.length}</dd></div><div><dt>Findings</dt><dd>{result.findings.length}</dd></div></dl><button className="text-link" onClick={() => downloadFile(`${result.audit_id}.json`, JSON.stringify(result, null, 2))}>Download calculation evidence <Icon name="download" size={15}/></button></aside></div></>;
}

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [current, setCurrent] = useState<ReviewEntry>({ key: "sample", result: fallbackDemo, name: "checkout_demo.csv" });
  const [entries, setEntries] = useState<ReviewEntry[]>([current]);
  const [connection, setConnection] = useState<"loading" | "live" | "offline">("loading");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let mounted = true;
    fetchDemo().then(result => {
      if (!mounted) return;
      const entry = { key: "sample", result, name: "checkout_demo.csv" };
      setEntries(existing => existing.map(item => item.key === "sample" ? entry : item));
      setCurrent(existing => existing.key === "sample" ? entry : existing);
      setConnection("live");
    }).catch(() => { if (mounted) setConnection("offline"); });
    return () => { mounted = false; };
  }, []);
  useEffect(() => { document.title = `${page === "overview" ? current.result.headline.metric_name : page === "method" ? "Methodology" : navItems.find(item => item.page === page)?.name} · Metric Mirage`; }, [page, current]);
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(""), 5000); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => { if (!sidebarOpen) return; const close = (event: KeyboardEvent) => { if (event.key === "Escape") setSidebarOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, [sidebarOpen]);
  const navigate = (target: Page) => { setPage(target); setSidebarOpen(false); window.scrollTo({ top: 0, behavior: "instant" }); };
  const openReview = (entry: ReviewEntry) => { setCurrent(entry); navigate("overview"); };
  const onComplete = (result: AuditResult, name: string) => { const entry = { key: `${result.audit_id}-${Date.now()}`, result, name }; setEntries(old => [entry, ...old]); setCurrent(entry); setConnection("live"); setUploadOpen(false); navigate("overview"); setNotice("Review complete. Your evidence is ready."); };
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to review</a>
    <aside className={`sidebar ${sidebarOpen ? "open" : ""}`} aria-label="Main navigation"><a className="brand-link" href="#" onClick={event => { event.preventDefault(); navigate("overview"); }} aria-label="Metric Mirage home"><Brand/></a><button className="mobile-close icon-button" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><Icon name="close"/></button>
      <div className="workspace-label"><span className="workspace-symbol">M</span><div><strong>Personal workspace</strong><span>Analytics & evidence</span></div></div>
      <div className="nav-group-label">Workspace</div><nav>{navItems.map(item => <button key={item.page} aria-current={page === item.page ? "page" : undefined} className={page === item.page ? "active" : ""} onClick={() => navigate(item.page)}><Icon name={item.icon} size={18}/><span>{item.name}</span>{item.page === "audits" && <span className="nav-count">{entries.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><button className={`method-nav ${page === "method" ? "active" : ""}`} onClick={() => navigate("method")} aria-current={page === "method" ? "page" : undefined}><Icon name="book" size={18}/>Methodology <Icon name="arrow" size={14}/></button><div className="sidebar-note"><span>Made for considered decisions.</span><p>Keep the question close.<br/>Keep the evidence closer.</p></div><div className="workspace-state"><i className={connection}/><span>{connection === "live" ? "Analysis service available" : connection === "loading" ? "Connecting to analysis service" : "Offline sample · uploads unavailable"}</span></div></div>
    </aside>
    {sidebarOpen && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}/>}
    <div className="workspace-main"><header className="topbar"><button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation" aria-expanded={sidebarOpen}><Icon name="menu"/></button><div className="breadcrumbs"><span>Workspace</span><Icon name="chevron" size={13}/><strong>{page === "method" ? "Methodology" : navItems.find(item => item.page === page)?.name}</strong></div><div className="header-meta"><span>{isDemo(current.result) ? "Sample review" : "Session review"}</span><span className="workspace-monogram" aria-label="Personal workspace">M</span></div></header>
      <main id="main-content" className="page-content" tabIndex={-1}>
        {connection === "offline" && <div className="offline-banner" role="status"><Icon name="info" size={16}/>You're viewing a saved sample. Start the analysis service to review your own data.</div>}
        {page === "overview" && <Overview key={current.key} result={current.result} sourceName={current.name} onNew={() => setUploadOpen(true)} onReport={() => navigate("reports")} onMethod={() => navigate("method")}/>}
        {page === "audits" && <Reviews entries={entries} onSelect={openReview} onNew={() => setUploadOpen(true)}/>}
        {page === "data" && <DataPage result={current.result} sourceName={current.name} onNew={() => setUploadOpen(true)}/>}
        {page === "reports" && <Report result={current.result} sourceName={current.name}/>}
        {page === "method" && <MethodPage result={current.result}/>}
        <footer className="page-footer"><span>Metric Mirage</span><span>Clear questions. Traceable conclusions.</span><button onClick={() => navigate("method")}>Methodology <Icon name="arrow" size={12}/></button></footer>
      </main>
    </div>
    {uploadOpen && <UploadDialog onClose={() => setUploadOpen(false)} onComplete={onComplete}/>}
    {notice && <div role="status" className="toast"><Icon name="check"/>{notice}<button onClick={() => setNotice("")} aria-label="Dismiss notification"><Icon name="close" size={16}/></button></div>}
  </div>;
}
