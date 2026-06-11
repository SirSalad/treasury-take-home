import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type DataTableColumn } from "./DataTable";

interface Row {
  id: number;
  name: string;
  kind: string;
}

const ROWS: Row[] = [
  { id: 1, name: "Cedar", kind: "wine" },
  { id: 2, name: "Apple", kind: "beer" },
  { id: 3, name: "Birch", kind: "wine" },
];

const COLUMNS: DataTableColumn<Row>[] = [
  { key: "name", header: "Name", width: "1fr", sortValue: (r) => r.name, cell: (r) => r.name },
  { key: "kind", header: "Kind", width: "1fr", cell: (r) => r.kind },
];

function names(): string[] {
  // Each cell is rendered; read the Name column by row order via the rows' text.
  return screen.getAllByText(/Cedar|Apple|Birch/).map((el) => el.textContent ?? "");
}

describe("DataTable", () => {
  it("renders headers and rows", () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(r) => r.id} />);
    expect(screen.getByText("Name")).toBeDefined();
    expect(screen.getByText("Kind")).toBeDefined();
    expect(names()).toHaveLength(3);
  });

  it("shows the loading message when rows is null", () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={null}
        getRowKey={(r) => r.id}
        loadingMessage="Loading things…"
      />,
    );
    expect(screen.getByText("Loading things…")).toBeDefined();
  });

  it("renders the empty state when there are no rows", () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={[]}
        getRowKey={(r) => r.id}
        emptyState={<p>Nothing here</p>}
      />,
    );
    expect(screen.getByText("Nothing here")).toBeDefined();
  });

  it("sorts ascending then descending on header click", () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(r) => r.id} />);
    fireEvent.click(screen.getByRole("button", { name: /Sort by Name/i }));
    expect(names()).toEqual(["Apple", "Birch", "Cedar"]);
    fireEvent.click(screen.getByRole("button", { name: /Sort by Name.*ascending/i }));
    expect(names()).toEqual(["Cedar", "Birch", "Apple"]);
  });

  it("does not make rows interactive without onRowClick", () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(r) => r.id} />);
    // Sort header buttons exist, but no row buttons.
    expect(screen.queryByRole("button", { name: /row|open/i })).toBeNull();
  });

  it("fires onRowClick and exposes a row aria-label when interactive", () => {
    const onRowClick = vi.fn();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        getRowKey={(r) => r.id}
        onRowClick={onRowClick}
        rowAriaLabel={(r) => `Open ${r.name}`}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open Apple" }));
    expect(onRowClick).toHaveBeenCalledWith(ROWS[1]);
  });

  it("filters via search and shows the no-match message", () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        getRowKey={(r) => r.id}
        search={{ ariaLabel: "Search rows", placeholder: "Search…", text: (r) => r.name }}
        noMatchMessage="Nothing matches"
      />,
    );
    fireEvent.change(screen.getByLabelText("Search rows"), { target: { value: "ced" } });
    expect(names()).toEqual(["Cedar"]);
    fireEvent.change(screen.getByLabelText("Search rows"), { target: { value: "zzz" } });
    expect(screen.getByText("Nothing matches")).toBeDefined();
  });

  it("applies a dropdown filter and a clear-filters reset", () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        getRowKey={(r) => r.id}
        filters={[
          {
            key: "kind",
            label: "Filter by kind",
            options: [
              { value: "all", label: "All" },
              { value: "wine", label: "Wine" },
              { value: "beer", label: "Beer" },
            ],
            predicate: (r, v) => r.kind === v,
          },
        ]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Filter by kind"), { target: { value: "beer" } });
    expect(names()).toEqual(["Apple"]);
    fireEvent.click(screen.getByRole("button", { name: /Clear filters/i }));
    expect(names()).toHaveLength(3);
  });
});

describe("DataTable pagination", () => {
  const MANY: Row[] = Array.from({ length: 7 }, (_, i) => ({
    id: i + 1,
    name: `Row${String(i + 1).padStart(2, "0")}`,
    kind: i % 2 ? "beer" : "wine",
  }));

  it("pages the rows and walks with Previous/Next", () => {
    render(<DataTable columns={COLUMNS} rows={MANY} getRowKey={(r) => r.id} pageSize={3} />);

    expect(screen.getAllByText(/Row\d\d/)).toHaveLength(3);
    expect(screen.getByText(/Showing 1–3 of 7/)).toBeDefined();
    expect(screen.getByRole("button", { name: /previous/i })).toHaveProperty("disabled", true);

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText("Row07")).toBeDefined();
    expect(screen.getByText(/Showing 7–7 of 7/)).toBeDefined();
    expect(screen.getByRole("button", { name: /next/i })).toHaveProperty("disabled", true);
  });

  it("returns to the first page when a search narrows the results", () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={MANY}
        getRowKey={(r) => r.id}
        pageSize={3}
        search={{ ariaLabel: "Search", placeholder: "Search", text: (r) => r.name }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/Showing 4–6 of 7/)).toBeDefined();

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Row01" } });
    expect(screen.getByText("Row01")).toBeDefined();
    expect(screen.queryByText(/Showing/)).toBeNull(); // one page: pager hidden
  });

  it("renders everything on one page when pageSize is omitted", () => {
    render(<DataTable columns={COLUMNS} rows={MANY} getRowKey={(r) => r.id} />);
    expect(screen.getAllByText(/Row\d\d/)).toHaveLength(7);
    expect(screen.queryByRole("navigation", { name: /pagination/i })).toBeNull();
  });
});
