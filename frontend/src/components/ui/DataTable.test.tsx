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
