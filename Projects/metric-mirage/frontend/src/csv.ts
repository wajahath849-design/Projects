// Read the first CSV record, including quoted commas, escaped quotes and a BOM.
export function csvHeaders(text: string): string[] {
  const columns: string[] = [];
  let value = "", quoted = false;
  const source = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (char === '"') {
      if (quoted && source[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (char === "," || char === "\n" || char === "\r")) {
      columns.push(value);
      value = "";
      if (char !== ",") break;
    } else value += char;
    if (i === source.length - 1) columns.push(value);
  }
  if (quoted || !columns.length || columns.some(column => !column.trim()) || new Set(columns).size !== columns.length)
    throw new Error("Use a CSV with unique, non-empty column headers.");
  return columns;
}

export function csvValues(text: string): Record<string, (string | null)[]> {
  const headers = csvHeaders(text);
  const values = headers.map(() => new Set<string | null>());
  let row: string[] = [], value = "", quoted = false, first = true;
  const source = text.replace(/^\uFEFF/, "");
  const finish = () => {
    row.push(value); value = "";
    if (first) first = false;
    else if (row.some(cell => cell !== "")) {
      if (row.length !== headers.length) throw new Error("Every CSV row must have the same number of columns as the header.");
      row.forEach((cell, index) => values[index].add(cell === "" ? null : cell));
    }
    row = [];
  };
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (char === '"') {
      if (quoted && source[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && char === ",") { row.push(value); value = ""; }
    else if (!quoted && (char === "\n" || char === "\r")) {
      finish(); if (char === "\r" && source[i + 1] === "\n") i++;
    } else value += char;
  }
  if (quoted) throw new Error("The CSV contains an unclosed quoted value.");
  if (row.length || value) finish();
  return Object.fromEntries(headers.map((header, index) => [header, [...values[index]].sort((a, b) => String(a).localeCompare(String(b)))]));
}
