import { useMemo, useState } from "react";
import type { SegmentRow, TimePoint } from "../types";
import { dateLabel } from "../presentation";

const palette = ["#b27b3e", "#6b8195", "#8b7294", "#89916e"];
export default function TrendChart({ points, splitDate, segments }: { points: TimePoint[]; splitDate: string; segments: SegmentRow[] }) {
  const [hidden, setHidden] = useState<string[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const series = useMemo(() => [
    { key: "aggregate", label: "Overall", color: "#3e5947" },
    ...segments.slice(0, 4).map((segment, index) => ({ key: segment.series_key || segment.segment.toLowerCase().replaceAll(" ", "_"), label: segment.segment, color: palette[index] })),
  ].filter(line => points.some(point => typeof point[line.key] === "number")), [points, segments]);
  const shown = series.filter(line => !hidden.includes(line.key));
  const w = 760, h = 280, left = 42, right = 22, top = 32, bottom = 40;
  const values = points.flatMap(point => shown.map(line => point[line.key]).filter((v): v is number => typeof v === "number" && Number.isFinite(v)));
  const high = Math.max(...values, 1);
  const step = high <= 1 ? .25 : high <= 5 ? 1 : high <= 10 ? 2 : Math.ceil(high / 4);
  const max = Math.ceil(high / step) * step;
  const start = new Date(points[0]?.date || splitDate).valueOf();
  const end = new Date(points.at(-1)?.date || splitDate).valueOf();
  const x = (date: string) => left + (new Date(date).valueOf() - start) / Math.max(end - start, 1) * (w - left - right);
  const y = (value: number) => h - bottom - (value / max) * (h - bottom - top);
  const splitX = x(splitDate);
  const selected = active === null ? null : points[active];
  const path = (key: string) => {
    let connected = false;
    return points.map(point => {
      const value = point[key];
      if (typeof value !== "number" || !Number.isFinite(value)) { connected = false; return ""; }
      const command = `${connected ? "L" : "M"}${x(point.date)},${y(value)}`;
      connected = true; return command;
    }).join(" ");
  };
  return <div className="trend-chart">
    <div className="chart-toolbar"><div className="chart-legend">{series.map(line => <button type="button" key={line.key} aria-pressed={!hidden.includes(line.key)} onClick={() => setHidden(current => current.includes(line.key) ? current.filter(key => key !== line.key) : current.length < series.length - 1 ? [...current, line.key] : current)}><i style={{ background: line.color }}/>{line.label}</button>)}</div><span>Weekly rate · %</span></div>
    <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Weekly metric rates for the overall population and comparison segments">
      {Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step).map(tick => <g key={tick}><line x1={left} x2={w - right} y1={y(tick)} y2={y(tick)} className="chart-grid"/><text x={left - 12} y={y(tick) + 4} textAnchor="end" className="chart-axis">{tick}%</text></g>)}
      {splitX >= left && splitX <= w - right && <g><rect x={splitX} y={top} width={w - right - splitX} height={h - top - bottom} fill="#f7f8f4"/><line x1={splitX} x2={splitX} y1={top} y2={h - bottom} stroke="#92998c" strokeDasharray="4 4"/><text x={Math.min(splitX + 8, w - 118)} y={20} className="chart-axis">Comparison starts</text></g>}
      {shown.map(line => <path key={line.key} d={path(line.key)} stroke={line.color} fill="none" strokeWidth={line.key === "aggregate" ? 2.6 : 1.8} strokeLinecap="round" strokeLinejoin="round"/>)}
      {selected && <line x1={x(selected.date)} x2={x(selected.date)} y1={top} y2={h - bottom} stroke="#b8bcb4"/>}
      {points.map((point, index) => <g key={point.date}>
        {selected === point && shown.map(line => typeof point[line.key] === "number" && <circle key={line.key} cx={x(point.date)} cy={y(point[line.key] as number)} r="4" fill="white" stroke={line.color} strokeWidth="2"/>)}
        <rect className="chart-target" x={Math.max(left - 5, x(point.date) - 12)} y={top} width="24" height={h - top - bottom} fill="transparent" tabIndex={0} role="button" aria-label={`${dateLabel(point.date)}, overall ${point.aggregate.toFixed(2)} percent`} onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} onKeyDown={event => { if (event.key === "ArrowRight" || event.key === "ArrowLeft") { event.preventDefault(); const next = Math.max(0, Math.min(points.length - 1, index + (event.key === "ArrowRight" ? 1 : -1))); event.currentTarget.ownerSVGElement?.querySelectorAll<SVGRectElement>(".chart-target")[next]?.focus(); } }}/>
      </g>)}
      {points.filter((_, index) => index === 0 || index === points.length - 1 || index % Math.max(1, Math.ceil(points.length / 4)) === 0).map(point => <text key={point.date} x={x(point.date)} y={h - 12} textAnchor={point === points[0] ? "start" : point === points.at(-1) ? "end" : "middle"} className="chart-axis">{dateLabel(point.date)}</text>)}
    </svg>
    <div className="chart-readout" aria-live="polite">{selected ? <><strong>{dateLabel(selected.date)}</strong>{shown.map(line => <span key={line.key}><i style={{ background: line.color }}/>{line.label} <b>{typeof selected[line.key] === "number" ? `${(selected[line.key] as number).toFixed(2)}%` : "—"}</b></span>)}</> : <span>Hover over a week to inspect values. Select a legend label to show or hide a series.</span>}</div>
  </div>;
}
