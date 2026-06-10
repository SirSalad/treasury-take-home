import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApplicationForm } from "@/components/application/ApplicationForm";

/** Fill the three required fields with a valid distilled-spirits application. */
function fillRequired() {
  fireEvent.change(screen.getByLabelText(/brand name/i), {
    target: { value: "Old Tom Distillery" },
  });
  fireEvent.change(screen.getByLabelText(/^source/i), { target: { value: "domestic" } });
  fireEvent.change(screen.getByLabelText(/product type/i), {
    target: { value: "distilled_spirits" },
  });
}

describe("ApplicationForm", () => {
  it("blocks submit and shows an error summary when required fields are empty", () => {
    const onSubmit = vi.fn();
    render(<ApplicationForm onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /verify label/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/before continuing/i)).toBeInTheDocument();
  });

  it("submits the captured data once required fields are valid", () => {
    const onSubmit = vi.fn();
    render(<ApplicationForm onSubmit={onSubmit} />);

    fillRequired();
    fireEvent.click(screen.getByRole("button", { name: /verify label/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      brandName: "Old Tom Distillery",
      source: "domestic",
      productType: "distilled_spirits",
    });
  });

  it("reveals wine-only fields when the product type is wine", () => {
    render(<ApplicationForm onSubmit={vi.fn()} />);

    expect(screen.queryByLabelText(/vintage/i)).toBeNull();
    fireEvent.change(screen.getByLabelText(/product type/i), { target: { value: "wine" } });
    expect(screen.getByLabelText(/vintage/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/appellation/i)).toBeInTheDocument();
  });

  it("requires country of origin for imported products", () => {
    const onSubmit = vi.fn();
    render(<ApplicationForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/brand name/i), { target: { value: "Glen Example" } });
    fireEvent.change(screen.getByLabelText(/^source/i), { target: { value: "imported" } });
    fireEvent.change(screen.getByLabelText(/product type/i), {
      target: { value: "distilled_spirits" },
    });
    fireEvent.click(screen.getByRole("button", { name: /verify label/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    // Shown both inline and in the error summary.
    expect(
      screen.getAllByText(/imported products require a country of origin/i).length,
    ).toBeGreaterThan(0);
  });
});
