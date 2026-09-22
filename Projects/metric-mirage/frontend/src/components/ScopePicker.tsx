import { useState } from "react";

export type Filters = Record<string, (string | null)[]>;
export default function ScopePicker({ columns, values, groups, filters, onGroups, onFilters }: {
  columns: string[]; values: Filters; groups: string[]; filters: Filters;
  onGroups: (groups: string[]) => void; onFilters: (filters: Filters) => void;
}) {
  const [search, setSearch] = useState<Record<string, string>>({});
  const [nextFilter, setNextFilter] = useState("");
  const availableFilters = Object.keys(values).filter(column => !(column in filters));
  return <section className="scope-picker">
    <div className="field-section"><h3>Group your comparison</h3><p>Select any combination of columns. Category + region compares groups such as Clothing in Berlin. Leave all unchecked for the overall result.</p></div>
    <div className="scope-options">{columns.map(column => <label key={column}><input type="checkbox" checked={groups.includes(column)} onChange={event => onGroups(event.target.checked ? [...groups, column] : groups.filter(value => value !== column))}/>{column}</label>)}</div>
    <div className="field-section"><h3>Filter your data</h3><p>Optional. Values within a column use OR; different columns use AND. Columns without a filter include every value.</p></div>
    <div className="filter-add"><select aria-label="Filter column" value={nextFilter} onChange={event => setNextFilter(event.target.value)}><option value="">Choose a filter column</option>{availableFilters.map(column => <option key={column}>{column}</option>)}</select><button type="button" className="button" disabled={!nextFilter} onClick={() => { onFilters({ ...filters, [nextFilter]: values[nextFilter] }); setNextFilter(""); }}>Add filter</button></div>
    {Object.keys(filters).map(column => {
      const query = (search[column] || "").toLowerCase();
      const matching = values[column].filter(value => (value ?? "(Missing)").toLowerCase().includes(query));
      return <details open key={column} className="scope-filter"><summary>{column} <small>{filters[column].length} of {values[column].length} selected</small></summary>
      <button type="button" className="text-link filter-remove" onClick={() => { const next = { ...filters }; delete next[column]; onFilters(next); }}>Remove filter</button>
        <input className="scope-search" aria-label={`Search ${column} values`} placeholder="Search values…" value={search[column] || ""} onChange={event => setSearch(current => ({ ...current, [column]: event.target.value }))}/>
        <div className="scope-actions"><button type="button" className="text-link" onClick={() => onFilters({ ...filters, [column]: values[column] })}>Select all</button><button type="button" className="text-link" onClick={() => onFilters({ ...filters, [column]: [] })}>Clear selection</button></div>
        <div className="scope-options scope-values">{matching.slice(0, 200).map(value => <label key={JSON.stringify(value)}><input type="checkbox" checked={filters[column].includes(value)} onChange={event => onFilters({ ...filters, [column]: event.target.checked ? [...filters[column], value] : filters[column].filter(item => item !== value) })}/>{value ?? "(Missing)"}</label>)}</div>
        {matching.length > 200 && <p className="form-note">Showing the first 200 matches. Search to narrow the list.</p>}
      </details>;
    })}
  </section>;
}
