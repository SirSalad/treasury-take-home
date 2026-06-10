import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LabelUpload } from "./LabelUpload";

/** Drive the hidden file input with a given File. */
function pick(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
}

describe("LabelUpload validation", () => {
  it("rejects a non-image file with an explanatory, announced error", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={null} onChange={onChange} previewUrl={null} />);

    pick(new File(["%PDF"], "application.pdf", { type: "application/pdf" }));

    expect(onChange).toHaveBeenCalledWith(null);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/isn’t an image/i);
  });

  it("rejects an image over the 20 MB limit", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={null} onChange={onChange} previewUrl={null} />);

    const big = new File(["x"], "huge.png", { type: "image/png" });
    Object.defineProperty(big, "size", { value: 21 * 1024 * 1024 });
    pick(big);

    expect(onChange).toHaveBeenCalledWith(null);
    expect(screen.getByRole("alert").textContent).toMatch(/over the 20 MB limit/i);
  });

  it("accepts a valid image and reports no error", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={null} onChange={onChange} previewUrl={null} />);

    pick(new File(["x"], "label.png", { type: "image/png" }));

    expect(onChange).toHaveBeenCalledWith(expect.any(File));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows the parent-supplied error (e.g. missing image on submit)", () => {
    render(
      <LabelUpload
        value={null}
        onChange={() => {}}
        previewUrl={null}
        error="Add the label image to verify against the application."
      />,
    );
    expect(screen.getByRole("alert").textContent).toMatch(/Add the label image/i);
  });
});
