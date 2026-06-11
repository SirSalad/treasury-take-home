import { useEffect, useMemo, useState, type ReactNode } from "react";

/**
 * A reusable workspace table: a CSS-grid table with optional per-column
 * sorting, a search box, filter dropdowns, a live result count, pagination,
 * and loading / empty / no-match states — all in the federal style. The
 * Review Queue and the Audit Log are both built from it.
 *
 * Columns declare their own grid track width and cell renderer; sorting,
 * filtering, and paging are client-side over the provided rows, so search and
 * filters always cover the whole set, not just the visible page.
 */

export interface DataTableColumn<T> {
  key: string;
  header: string;
  /** CSS grid track size for this column, e.g. "168px" or "1.4fr". */
  width: string;
  cell: (row: T) => ReactNode;
  /** When provided, the header becomes a sort control keyed on this value. */
  sortValue?: (row: T) => string | number;
  /** Direction applied when this column is first activated. */
  defaultDir?: "asc" | "desc";
}

export interface DataTableFilter<T> {
  key: string;
  /** Accessible name for the dropdown (visually hidden). */
  label: string;
  options: { value: string; label: string }[];
  /** Keep a row when the selected value is not "all". */
  predicate: (row: T, value: string) => boolean;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  /** `null` while loading; `[]` when loaded but empty. */
  rows: T[] | null;
  getRowKey: (row: T) => string | number;
  rowAriaLabel?: (row: T) => string;
  onRowClick?: (row: T) => void;
  search?: { ariaLabel: string; placeholder: string; text: (row: T) => string };
  filters?: DataTableFilter<T>[];
  defaultSort?: { key: string; dir: "asc" | "desc" };
  /** Singular / plural noun for the count summary, e.g. ["submission", "submissions"]. */
  countNoun?: [string, string];
  loadingMessage?: string;
  /** Shown when the data loaded but is empty (before any filtering). */
  emptyState?: ReactNode;
  /** Shown when filters/search exclude every row. */
  noMatchMessage?: string;
  /** Rows per page; omit to render everything on one page. */
  pageSize?: number;
}

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  rowAriaLabel,
  onRowClick,
  search,
  filters = [],
  defaultSort,
  countNoun = ["row", "rows"],
  loadingMessage = "Loading…",
  emptyState,
  noMatchMessage = "No rows match your filters.",
  pageSize,
}: DataTableProps<T>) {
  const [query, setQuery] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState<string | null>(defaultSort?.key ?? null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultSort?.dir ?? "asc");
  const [page, setPage] = useState(0);

  // A new search/filter/sort means a new result set: jump back to page one.
  useEffect(() => {
    setPage(0);
  }, [query, filterValues, sortKey, sortDir]);

  const gridStyle = { gridTemplateColumns: columns.map((c) => c.width).join(" ") };
  const filterOf = (key: string) => filterValues[key] ?? "all";
  const filtering = query.trim() !== "" || filters.some((f) => filterOf(f.key) !== "all");

  const visible = useMemo(() => {
    if (!rows) return [];
    const q = query.trim().toLowerCase();
    const filtered = rows.filter((row) => {
      for (const filter of filters) {
        const value = filterValues[filter.key] ?? "all";
        if (value !== "all" && !filter.predicate(row, value)) return false;
      }
      if (q && search && !search.text(row).toLowerCase().includes(q)) return false;
      return true;
    });
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return filtered;
    const getValue = col.sortValue;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => compareValues(getValue(a), getValue(b)) * dir);
  }, [rows, query, filterValues, filters, search, columns, sortKey, sortDir]);

  function toggleSort(col: DataTableColumn<T>) {
    if (!col.sortValue) return;
    if (col.key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col.key);
      setSortDir(col.defaultDir ?? "asc");
    }
  }

  function clearFilters() {
    setQuery("");
    setFilterValues({});
  }

  const showFilterBar = Boolean(search) || filters.length > 0;

  // Page the filtered/sorted rows; clamp so shrinking results never strand the
  // pager past the end.
  const pageCount = pageSize ? Math.max(1, Math.ceil(visible.length / pageSize)) : 1;
  const currentPage = Math.min(page, pageCount - 1);
  const paged = pageSize
    ? visible.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
    : visible;
  const rangeStart = visible.length === 0 ? 0 : currentPage * (pageSize ?? visible.length) + 1;
  const rangeEnd = rangeStart === 0 ? 0 : rangeStart + paged.length - 1;

  return (
    <div>
      {showFilterBar && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          {search && (
            <div className="grow sm:grow-0">
              <label htmlFor="datatable-search" className="sr-only">
                {search.ariaLabel}
              </label>
              <input
                id="datatable-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={search.placeholder}
                className="w-full rounded-md border border-[#c4c8cc] px-3 py-2 text-sm text-fed-ink focus:border-fed-blue focus:outline-none sm:w-[320px]"
              />
            </div>
          )}
          {filters.map((filter) => (
            <div key={filter.key}>
              <label htmlFor={`datatable-filter-${filter.key}`} className="sr-only">
                {filter.label}
              </label>
              <select
                id={`datatable-filter-${filter.key}`}
                value={filterOf(filter.key)}
                onChange={(e) => setFilterValues((v) => ({ ...v, [filter.key]: e.target.value }))}
                className="rounded-md border border-[#c4c8cc] bg-white px-3 py-2 text-sm font-semibold text-fed-ink focus:border-fed-blue focus:outline-none"
              >
                {filter.options.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          ))}
          {filtering && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-sm font-semibold text-fed-blue hover:underline"
            >
              Clear filters
            </button>
          )}
          {rows && (
            <span className="ml-auto text-[13px] text-fed-gray" aria-live="polite">
              {filtering ? `${visible.length} of ${rows.length}` : `${rows.length}`}{" "}
              {rows.length === 1 ? countNoun[0] : countNoun[1]}
            </span>
          )}
        </div>
      )}

      <div className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card">
        <div
          style={gridStyle}
          className="grid items-center gap-0 border-b-2 border-[#d6d7d9] bg-fed-head-bg px-[18px] py-3 text-[11.5px] font-bold uppercase tracking-[.5px] text-fed-gray"
        >
          {columns.map((col) => {
            if (!col.sortValue) {
              return <div key={col.key}>{col.header}</div>;
            }
            const active = col.key === sortKey;
            return (
              <button
                key={col.key}
                type="button"
                onClick={() => toggleSort(col)}
                aria-label={`Sort by ${col.header}${active ? (sortDir === "asc" ? ", ascending" : ", descending") : ""}`}
                className="flex items-center gap-1 text-left uppercase tracking-[.5px] hover:text-fed-blue"
              >
                {col.header}
                <span aria-hidden="true" className={active ? "text-fed-blue" : "text-[#c4c8cc]"}>
                  {active ? (sortDir === "asc" ? "▲" : "▼") : "▾"}
                </span>
              </button>
            );
          })}
        </div>

        {rows === null && <p className="px-[18px] py-6 text-sm text-fed-gray">{loadingMessage}</p>}
        {rows?.length === 0 &&
          (emptyState ?? (
            <p className="px-[18px] py-10 text-center text-[13.5px] text-fed-gray">
              Nothing here yet.
            </p>
          ))}
        {rows && rows.length > 0 && visible.length === 0 && (
          <p className="px-[18px] py-10 text-center text-[13.5px] text-fed-gray">
            {noMatchMessage}
          </p>
        )}
        {paged.map((row, index) => {
          const interactive = Boolean(onRowClick);
          return (
            <div
              key={getRowKey(row)}
              style={gridStyle}
              {...(interactive
                ? {
                    role: "button",
                    tabIndex: 0,
                    "aria-label": rowAriaLabel?.(row),
                    onClick: () => onRowClick?.(row),
                    onKeyDown: (e: React.KeyboardEvent) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onRowClick?.(row);
                      }
                    },
                  }
                : {})}
              className={`grid items-center gap-0 border-b border-fed-line-soft px-[18px] py-3 last:border-b-0 ${
                index % 2 === 1 ? "bg-[#f7f8f9]" : "bg-white"
              } ${
                interactive
                  ? "cursor-pointer transition-colors hover:bg-fed-blue-wash hover:shadow-[inset_3px_0_0_#005ea2] focus-visible:bg-fed-blue-wash focus-visible:shadow-[inset_3px_0_0_#005ea2] focus-visible:outline-none"
                  : ""
              }`}
            >
              {columns.map((col) => (
                <div key={col.key} className="min-w-0">
                  {col.cell(row)}
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {pageSize !== undefined && visible.length > pageSize && (
        <nav
          aria-label="Pagination"
          className="mt-3 flex items-center justify-between gap-3 text-[13px] text-fed-gray"
        >
          <span aria-live="polite">
            Showing {rangeStart}–{rangeEnd} of {visible.length}{" "}
            {visible.length === 1 ? countNoun[0] : countNoun[1]}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setPage(Math.max(0, currentPage - 1))}
              disabled={currentPage === 0}
              className="rounded-md border border-[#c4c8cc] bg-white px-3 py-1.5 text-[13px] font-semibold text-fed-ink hover:bg-fed-blue-wash disabled:pointer-events-none disabled:opacity-45"
            >
              ‹ Previous
            </button>
            <span className="px-1.5 tabular-nums">
              Page {currentPage + 1} of {pageCount}
            </span>
            <button
              type="button"
              onClick={() => setPage(Math.min(pageCount - 1, currentPage + 1))}
              disabled={currentPage >= pageCount - 1}
              className="rounded-md border border-[#c4c8cc] bg-white px-3 py-1.5 text-[13px] font-semibold text-fed-ink hover:bg-fed-blue-wash disabled:pointer-events-none disabled:opacity-45"
            >
              Next ›
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}
