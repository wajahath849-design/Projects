import type { ReactNode } from "react";

const paths: Record<string, ReactNode> = {
  audit: <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6M9 11h6m-6 5 2 2 4-4"/></>,
  overview: <><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"/></>,
  data: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/></>,
  report: <><path d="M14 3H6v18h12V7zM14 3v5h4M9 12h6M9 16h6"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5"/>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  down: <path d="m6 9 6 6 6-6"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  warning: <><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/></>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5"/></>,
  upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/></>,
  book: <><path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15"/></>,
  search: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
  file: <><path d="M14 3H5v18h14V8ZM14 3v5h5"/><path d="M8 12h8M8 16h8"/></>,
  print: <><path d="M7 8V3h10v5M7 17H4V9h16v8h-3M7 14h10v7H7zM17 11h.01"/></>,
};

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="icon">{paths[name] || paths.audit}</svg>;
}

export function Brand() {
  return <span className="brand"><svg viewBox="0 0 30 30" fill="none" aria-hidden="true"><path d="M4 22V8l7 7 7-7v14M23 8v14" stroke="currentColor" strokeWidth="2.3"/><path d="M3 26h22" stroke="currentColor" opacity=".35"/></svg><span>metric<span className="brand-light">mirage</span><small>ANALYTICS REVIEW</small></span></span>;
}
