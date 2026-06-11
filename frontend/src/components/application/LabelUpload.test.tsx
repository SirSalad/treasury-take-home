import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { LabelUpload } from "./LabelUpload";

// jsdom has no object-URL support; the thumbnails only need a stable string.
beforeAll(() => {
  URL.createObjectURL ??= vi.fn(() => "blob:preview");
  URL.revokeObjectURL ??= vi.fn();
});

/** Drive the hidden file input with the given Files. */
function pick(...files: File[]) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files } });
}

function image(name: string): File {
  return new File(["x"], name, { type: "image/png" });
}

describe("LabelUpload validation", () => {
  it("rejects a non-image file with an explanatory, announced error", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={[]} onChange={onChange} />);

    pick(new File(["%PDF"], "application.pdf", { type: "application/pdf" }));

    expect(onChange).not.toHaveBeenCalled();
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/isn’t an image/i);
  });

  it("rejects an image over the 20 MB limit", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={[]} onChange={onChange} />);

    const big = new File(["x"], "huge.png", { type: "image/png" });
    Object.defineProperty(big, "size", { value: 21 * 1024 * 1024 });
    pick(big);

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toMatch(/over the 20 MB limit/i);
  });

  it("accepts a valid image and reports no error", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={[]} onChange={onChange} />);

    pick(image("label.png"));

    expect(onChange).toHaveBeenCalledWith([expect.any(File)]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("appends to the existing set — a filing carries several labels", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={[image("front.png")]} onChange={onChange} />);

    pick(image("back.png"), image("neck.png"));

    const next = onChange.mock.calls[0][0] as File[];
    expect(next.map((f) => f.name)).toEqual(["front.png", "back.png", "neck.png"]);
  });

  it("caps the set at six images, mirroring the backend", () => {
    const onChange = vi.fn();
    const six = Array.from({ length: 6 }, (_, i) => image(`l${i}.png`));
    render(<LabelUpload value={six} onChange={onChange} />);

    // At the cap the dropzone disappears; there is no input to add a seventh.
    expect(document.querySelector('input[type="file"]')).not.toBeNull();
    expect(screen.queryByText(/Add another label image/i)).toBeNull();
  });

  it("removes one image from the set without touching the rest", () => {
    const onChange = vi.fn();
    render(<LabelUpload value={[image("front.png"), image("back.png")]} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: /remove label image 1/i }));

    const next = onChange.mock.calls[0][0] as File[];
    expect(next.map((f) => f.name)).toEqual(["back.png"]);
  });

  it("shows the parent-supplied error (e.g. missing image on submit)", () => {
    render(
      <LabelUpload
        value={[]}
        onChange={() => {}}
        error="Add at least one label image to verify against the application."
      />,
    );
    expect(screen.getByRole("alert").textContent).toMatch(/Add at least one label image/i);
  });
});
