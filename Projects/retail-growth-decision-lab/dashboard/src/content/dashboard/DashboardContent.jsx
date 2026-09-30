import React, { useMemo } from "react";
import { Button, DataComponent, DataTable, Dropdown, EvidenceChart, MetricCard, Section, Slider, useDataApp, useDashboardTabs, useSectionFilters } from "../../data-app-public.jsx";
import {defaults, economics, breakEven, campaignCsv} from './campaign.js';

const TABS = [
  { id: "performance", label: "Business performance" },
  { id: "retention", label: "Retention" },
  { id: "model", label: "Model evidence" },
  { id: "campaign", label: "Campaign simulator" },
];
const eur = value => new Intl.NumberFormat("en-GB", { style:"currency", currency:"EUR", maximumFractionDigits:0 }).format(value ?? 0);
const money = value => new Intl.NumberFormat("en-GB", {style:"currency",currency:"EUR",minimumFractionDigits:2}).format(value ?? 0);
const num = value => new Intl.NumberFormat("en-GB", { maximumFractionDigits:0 }).format(value ?? 0);
const pct = (value, digits=1) => value == null ? "—" : `${(value*100).toFixed(digits)}%`;
const columns = definitions => definitions.map(([field,label,presentation,renderCell]) => ({field,label,...(presentation?{presentation}:{}),...(renderCell?{renderCell}:{})}));

export function DashboardContent() {
  const { activeTabId } = useDashboardTabs(TABS);
  const tab = TABS.some(item => item.id === activeTabId) ? activeTabId : "performance";
  return <article className="rgl-page">
    {tab === "performance" && <Performance />}{tab === "retention" && <Retention />}
    {tab === "model" && <ModelEvidence />}{tab === "campaign" && <Campaign />}
  </article>;
}

function Performance() {
  const { queries } = useDataApp();
  const summary = queries.summary.rows[0], monthly = queries.monthly.rows;
  const countries = queries.countries.rows.slice(0,10), quality = queries.quality.rows;
  return <>
    <Context left="Observed merchandise performance · 1 Dec 2010–30 Nov 2011 · EUR" right="Historical ECB rates translate source GBP to EUR. December 2011 is incomplete and excluded." />
    <div className="rgl-metrics">
      <MetricCard id="net-sales" queryId="summary" title="Net merchandise revenue" value={eur(summary.net_sales)} sourceRows={queries.summary.rows} displayRows={queries.summary.rows} comparison="12 complete months" deltaTone="neutral" />
      <MetricCard id="gross-sales" queryId="summary" title="Gross merchandise sales" value={eur(summary.gross_sales)} sourceRows={queries.summary.rows} displayRows={queries.summary.rows} comparison={`${num(summary.orders)} orders`} deltaTone="neutral" />
      <MetricCard id="returns-value" queryId="summary" title="Recorded returns value" value={eur(summary.returns_value)} sourceRows={queries.summary.rows} displayRows={queries.summary.rows} comparison={`${pct(summary.return_rate_of_gross)} of gross`} deltaTone="neutral" />
      <MetricCard id="identified-share" queryId="summary" title="Sales linked to a customer" value={pct(summary.identified_sales_share)} sourceRows={queries.summary.rows} displayRows={queries.summary.rows} comparison={`${num(summary.customers)} customers`} deltaTone="neutral" />
    </div>
    <Section id="performance-trends" title="Performance and customer mix" columns={2} spacing="after-metrics">
      <EvidenceChart variant="card" id="monthly-sales" queryId="monthly" title="Monthly merchandise revenue" description="Gross positive sales and net revenue after recorded returns. The partial final source month is intentionally absent." rows={monthly} sourceRows={monthly} height={300} spec={{type:"line",x:"month",y:"gross_sales",fields:["gross_sales","net_sales"],currency:"EUR",showYAxisLabel:false,legend:{labels:{gross_sales:"Gross sales",net_sales:"Net revenue"}}}} />
      <EvidenceChart variant="card" id="customer-mix" queryId="monthly" title="Known-customer revenue mix" description="First-observed-month and returning-customer revenue include identified customers only." rows={monthly} sourceRows={monthly} height={300} spec={{type:"area",x:"month",y:"first_observed_customer_revenue",fields:["first_observed_customer_revenue","returning_customer_revenue"],currency:"EUR",stackable:true,showYAxisLabel:false,legend:{labels:{first_observed_customer_revenue:"First observed month",returning_customer_revenue:"Returning"}}}} />
    </Section>
    <Section id="performance-geography" title="Where sales came from" columns={2}>
      <EvidenceChart variant="card" id="country-sales" queryId="countries" title="Top 10 countries by gross sales" rows={countries} sourceRows={countries} height={330} spec={{type:"horizontalBar",x:"country",y:"gross_sales",currency:"EUR",showValues:true,showXAxisLabel:false,showYAxisLabel:false}} />
      <DataComponent variant="card" id="quality-audit" queryId="quality" title="Data-quality audit" kind="table" description="Every original row is reconciled to a retained sale, return, or explicit exclusion." displayRows={quality} sourceRows={quality}>
        <DataTable searchable={false} rows={quality} columns={columns([["check","Check"],["value","Rows",null,v=>num(v)],["detail","Treatment"]])} />
      </DataComponent>
    </Section>
  </>;
}

function Retention() {
  const { queries } = useDataApp(); const rows = queries.cohorts.rows;
  const cohorts = useMemo(() => [...new Set(rows.map(r=>r.cohort))], [rows]);
  const ages = useMemo(() => [...new Set(rows.map(r=>r.age_month))].sort((a,b)=>a-b), [rows]);
  const byKey = useMemo(() => new Map(rows.map(r=>[`${r.cohort}|${r.age_month}`,r])), [rows]);
  const ageOne=rows.filter(r=>r.age_month===1), weighted=ageOne.reduce((s,r)=>s+r.customers,0)/ageOne.reduce((s,r)=>s+r.cohort_size,0);
  const total=rows.filter(r=>r.age_month===0).reduce((s,r)=>s+r.cohort_size,0);
  return <>
    <Context left="First-observed-purchase cohorts · identified customers only" right="Earlier purchases are unavailable. Missing future cells are not zeros." />
    <div className="rgl-metrics rgl-metrics--three">
      <MetricCard id="cohort-count" queryId="cohorts" title="Observed cohorts" value={num(cohorts.length)} sourceRows={rows} displayRows={rows}/>
      <MetricCard id="month-one-retention" queryId="cohorts" title="Weighted month-1 retention" value={pct(weighted)} sourceRows={ageOne} displayRows={ageOne}/>
      <MetricCard id="cohort-customers" queryId="cohorts" title="Customers in cohorts" value={num(total)} sourceRows={rows} displayRows={rows}/>
    </div>
    <Section id="retention-cohorts" title="Customer retention by cohort" spacing="after-metrics">
      <DataComponent variant="card" id="cohort-retention" queryId="cohorts" title="Monthly retention heatmap" kind="table" description="Each cell is customers purchasing in that calendar age month divided by cohort size. Darker cells indicate higher retention." displayRows={rows} sourceRows={rows}>
        <div className="rgl-cohort-wrap" data-reviewed-rows><table className="rgl-cohort"><caption>Monthly retention by first observed purchase cohort</caption><thead><tr><th>Cohort</th><th>Customers</th>{ages.map(a=><th key={a}>M{a}</th>)}</tr></thead><tbody>{cohorts.map(c=>{const first=byKey.get(`${c}|0`);return <tr key={c}><th>{c}</th><td>{num(first?.cohort_size)}</td>{ages.map(a=>{const cell=byKey.get(`${c}|${a}`);return <td key={a}>{cell?<span style={{"--heat":Math.max(.08,cell.retention)}} title={`${c}, month ${a}: ${pct(cell.retention)} (${cell.customers}/${cell.cohort_size})`}>{pct(cell.retention,0)}</span>:<span className="rgl-gap">—</span>}</td>})}</tr>})}</tbody></table></div>
      </DataComponent>
    </Section>
  </>;
}

function ModelEvidence() {
  const { queries } = useDataApp(); const test=queries.model_metrics.rows.filter(r=>r.split==="test");
  const selected=test.find(r=>r.model.includes("calibrated")), baseline=test.find(r=>r.model==="RFM baseline");
  const gains=queries.model_gains.rows, intervals=queries.intervals.rows;
  const calibration=queries.calibration.rows.filter(r=>r.model!=="Prevalence baseline");
  return <>
    <Context left={`30-day repeat-purchase prediction · ${num(selected.n)} customers · November 2011 holdout`} right="September selected the model; October calibrated it; November evaluated it." />
    <div className="rgl-metrics">
      <MetricCard id="model-ap" queryId="model_metrics" title="Average precision" value={selected.average_precision.toFixed(3)} comparison={`+${(selected.average_precision-baseline.average_precision).toFixed(3)} vs RFM`} deltaTone="positive" sourceRows={test} displayRows={test}/>
      <MetricCard id="model-lift" queryId="model_metrics" title="Lift in top 20%" value={`${selected.lift_at_20.toFixed(2)}×`} comparison={`${pct(selected.precision_at_20)} precision`} deltaTone="positive" sourceRows={test} displayRows={test}/>
      <MetricCard id="model-capture" queryId="model_metrics" title="Purchasers captured in top 20%" value={pct(selected.recall_at_20)} comparison={`${pct(baseline.recall_at_20)} RFM`} deltaTone="positive" sourceRows={test} displayRows={test}/>
      <MetricCard id="model-brier" queryId="model_metrics" title="Brier score" value={selected.brier.toFixed(3)} comparison={`${baseline.brier.toFixed(3)} RFM`} deltaTone="positive" sourceRows={test} displayRows={test}/>
    </div>
    <Section id="model-evaluation" title="Does machine learning improve targeting?" columns={2} spacing="after-metrics">
      <EvidenceChart variant="card" id="gains-chart" queryId="model_gains" title="Cumulative targeting gains" description="Share of all future purchasers captured as the contacted share increases. Higher is better." rows={gains} sourceRows={gains} height={320} spec={{type:"line",x:"fraction",y:"capture_rate",series:"model",showXAxisLabel:true,xLabel:"Share of customers contacted",showYAxisLabel:true,yLabel:"Share of future purchasers captured",startAtZero:true}} />
      <EvidenceChart variant="card" id="calibration-chart" queryId="calibration" title="Predicted versus observed purchase rate" description="Points near the diagonal are well calibrated. Empty probability bins are omitted." rows={calibration} sourceRows={calibration} height={320} spec={{type:"scatter",x:"mean_prediction",y:"observed_rate",series:"model",showXAxisLabel:true,xLabel:"Mean predicted probability",showYAxisLabel:true,yLabel:"Observed purchase rate",startAtZero:true}} />
    </Section>
    <Section id="model-segment-diagnostics" title="Where probability estimates differ" columns={2}>
      <DataComponent variant="card" id="segment-diagnostics" queryId="segments" title="Calibration by recency segment" kind="table" sourceRows={queries.segments.rows} displayRows={queries.segments.rows} description="Active: last purchase within 30 days. Cooling: 31–90 days. Dormant: more than 90 days. Differences show subgroup calibration, not causal drivers.">
        <DataTable searchable={false} rows={queries.segments.rows} columns={columns([["segment","Segment"],["n","Customers"],["mean_prediction","Predicted rate",null,v=>pct(v)],["observed_rate","Observed rate",null,v=>pct(v)],["brier","Brier",null,v=>v.toFixed(3)]])}/>
      </DataComponent>
      <DataComponent variant="card" id="selection-evidence" queryId="model_metrics" title="September model selection" kind="table" sourceRows={queries.model_metrics.rows.filter(r=>r.split==='validation')} displayRows={queries.model_metrics.rows.filter(r=>r.split==='validation')} description="Model selected by September average precision before evaluating November outcomes.">
        <DataTable searchable={false} rows={queries.model_metrics.rows.filter(r=>r.split==='validation')} columns={columns([["model","Candidate"],["n","Customers"],["average_precision","Avg precision",null,v=>v.toFixed(3)]])}/>
      </DataComponent>
    </Section>
    <Section id="model-details" title="Evaluation details" columns={2}>
      <DataComponent variant="card" id="model-scorecard" queryId="model_metrics" title="Test scorecard" kind="table" displayRows={test} sourceRows={test}><DataTable rows={test} columns={columns([["model","Model"],["roc_auc","ROC AUC",null,v=>v.toFixed(3)],["average_precision","Avg precision",null,v=>v.toFixed(3)],["precision_at_20","Precision @20%",null,v=>pct(v)],["lift_at_20","Lift @20%",null,v=>`${v.toFixed(2)}×`],["brier","Brier",null,v=>v.toFixed(3)]])}/></DataComponent>
      <DataComponent variant="card" id="uncertainty" queryId="intervals" title="95% bootstrap intervals" kind="table" description="Customer-sampling uncertainty within November; seasonal and causal uncertainty are outside these intervals." displayRows={intervals} sourceRows={intervals}><DataTable rows={intervals} columns={columns([["metric","Metric"],["low","Low",null,v=>v.toFixed(3)],["high","High",null,v=>v.toFixed(3)],["resamples","Resamples"]])}/></DataComponent>
    </Section>
    <Boundary>Purchase probability describes natural behavior. It does not estimate whether an offer changes behavior. One historical retailer and one November test period limit generalization.</Boundary>
  </>;
}

function Campaign() {
  const { queries, assumptions, setAssumptions }=useDataApp(), all=queries.candidates.rows;
  const scope=useSectionFilters([{id:'country',label:'Country',field:'country',defaultValue:'all',queryIds:['candidates']}],{}, {id:'campaign-country'});
  const country=scope.values.country??'all',setCountry=value=>scope.setFilter('country',value);
  const countries=["all",...[...new Set(all.map(r=>r.country))].sort()];
  const value=(key,min,max)=>Math.min(max,Math.max(min,Number.isFinite(assumptions[`campaign_eur_${key}`])?assumptions[`campaign_eur_${key}`]:defaults[key]));
  const budget=value('budget',0,5000),cost=value('cost',.5,5),margin=value('margin',0,.7),uplift=value('uplift',0,.1);
  const set=(key,v)=>setAssumptions(previous=>({...previous,[`campaign_eur_${key}`]:v}));
  const reset=()=>{setCountry('all');setAssumptions(previous=>({...previous,...Object.fromEntries(Object.entries(defaults).map(([k,v])=>[`campaign_eur_${k}`,v]))}));};
  const candidates=country==="all"?all:all.filter(r=>r.country===country);
  const selected=useMemo(()=>candidates.slice(0,Math.min(candidates.length,Math.floor(budget/cost))),[candidates,budget,cost]);
  const options={budget,cost,margin,uplift};
  const outcome=economics(selected,options);
  const threshold=breakEven(selected,options);
  const scenarioRows=[{customers:selected.length,budget,contact_cost:cost,assumed_margin:margin,assumed_absolute_uplift:uplift,
    assumed_incremental_orders:outcome.orders,contact_spend:outcome.spend,assumed_incremental_contribution:outcome.contribution,break_even_uplift:threshold}];
  const sensitivity=[0,.005,.01,.02,.03,.05,.1].map(u=>({assumed_uplift:u,incremental_contribution:economics(selected,{...options,uplift:u}).contribution}));
  const spend=selected.length*cost, contribution=outcome.gross-spend;
  const exportRows=()=>{const url=URL.createObjectURL(new Blob([campaignCsv(selected,options)],{type:"text/csv;charset=utf-8"}));const a=document.createElement("a");a.href=url;a.download="campaign-priority-list.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  return <>
    <Context left="Budget-constrained outreach scenario · scores at 1 Nov 2011" right="All amounts in EUR. Historical order values use transaction-date ECB rates. Uplift and margin are assumptions." />
    <Section id="campaign-assumptions" title="Scenario assumptions" filters={<Button onClick={reset}>Reset scenario</Button>}><div className="rgl-controls">
      <Dropdown label="Country" showLabel value={country} choices={countries} onChange={setCountry} allLabel="All countries"/>
      <Slider label="Budget" min={0} max={5000} step={100} value={budget} onChange={v=>set('budget',v)} showBounds formatValue={eur}/>
      <Slider label="Cost per contact" min={.5} max={5} step={.5} value={cost} onChange={v=>set('cost',v)} showBounds formatValue={money}/>
      <Slider label="Gross-margin assumption" min={0} max={.7} step={.05} value={margin} onChange={v=>set('margin',v)} showBounds formatValue={v=>pct(v,0)}/>
      <Slider label="Assumed absolute uplift" min={0} max={.1} step={.005} value={uplift} onChange={v=>set('uplift',v)} showBounds formatValue={v=>`${(v*100).toFixed(1)} pp`}/>
    </div></Section>
    <div className="rgl-metrics rgl-metrics--three rgl-campaign-metrics">
      <MetricCard id="scenario-contacts" queryId="candidates" title="Customers contacted" value={num(selected.length)} comparison={`${eur(spend)} spend`} deltaTone="neutral" sourceRows={selected} displayRows={scenarioRows}/>
      <MetricCard id="scenario-orders" queryId="candidates" title="Assumed incremental orders" value={outcome.orders.toFixed(1)} comparison={`${(uplift*100).toFixed(1)} pp uplift`} deltaTone="neutral" sourceRows={selected} displayRows={scenarioRows}/>
      <MetricCard id="scenario-economics" queryId="candidates" title="Assumed incremental contribution" value={eur(contribution)} comparison={`${eur(outcome.gross)} before contact cost`} deltaTone={contribution>=0?"positive":"negative"} sourceRows={selected} displayRows={scenarioRows}/>
    </div>
    <Section id="campaign-sensitivity" title="What uplift would make contact worthwhile?" columns={2}>
      <MetricCard id="break-even" queryId="candidates" title="Break-even absolute uplift" value={threshold==null?'Unavailable':`${(threshold*100).toFixed(2)} pp`} comparison={!selected.length?'No customers selected':threshold==null?'Cannot break even at this margin':'For this customer list and cost assumptions'} deltaTone="neutral" sourceRows={selected} displayRows={scenarioRows}/>
      <DataComponent variant="card" id="uplift-sensitivity" queryId="candidates" title="Contribution under alternative assumptions" kind="table" sourceRows={selected} displayRows={sensitivity}><DataTable searchable={false} rows={sensitivity} columns={columns([["assumed_uplift","Assumed uplift",null,v=>`${(v*100).toFixed(1)} pp`],["incremental_contribution","Scenario contribution",null,v=>eur(v)]])}/></DataComponent>
    </Section>
    <Section id="campaign-priority" title="Who would be contacted" spacing="after-metrics"><DataComponent variant="card" id="priority-table" queryId="candidates" title="Priority list" kind="table" description="Ranked by capped historical order value × (1 − purchase probability). This heuristic is transparent but not experimentally validated." displayRows={selected} sourceRows={selected} headerControls={<Button onClick={exportRows} disabled={!selected.length}>Export selected CSV</Button>}><DataTable searchable rows={selected} columns={columns([["customer_id","Customer"],["country","Country"],["segment","Recency segment","status"],["purchase_probability","Purchase probability",null,v=>pct(v)],["order_value","Capped order value",null,v=>eur(v)],["priority_score","Priority score",null,v=>eur(v)]])}/></DataComponent></Section>
    <Boundary>The list uses a value × non-purchase heuristic, while model evaluation ranks purchase probability. The heuristic has not been validated by the model's gains curve. Randomize treatment and control within eligibility and score bands before estimating campaign impact.</Boundary>
  </>;
}

function Context({left,right}) { return <div className="rgl-context"><p>{left}</p><p>{right}</p></div>; }
function Boundary({children}) { return <div className="rgl-limitations"><strong>Interpretation boundary. </strong>{children}</div>; }
