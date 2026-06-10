import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SAMPLE_RESULT } from "@/lib/verification.fixture";
import type { VerificationResult } from "@/lib/verification";
import { ComparisonView } from "./ComparisonView";

const IMAGE = "/sample-label.png";

function renderView(result: VerificationResult = SAMPLE_RESULT) {
  return render(<ComparisonView result={result} imageSrc={IMAGE} />);
}

/** Fire the image's load event with stubbed natural dimensions (jsdom reports 0). */
function loadImage(width = 600, height = 800) {
  const img = screen.getByRole("img");
  Object.defineProperty(img, "naturalWidth", { value: width, configurable: true });
  Object.defineProperty(img, "naturalHeight", { value: height, configurable: true });
  fireEvent.load(img);
}

describe("ComparisonView", () => {
  it("shows an obvious, accessible overall verdict banner", () => {
    renderView();
    const banner = screen.getByRole("status", { name: /Verification Failed/i });
    expect(within(banner).getByRole("heading", { name: "Failed" })).toBeDefined();
    expect(within(banner).getByText(SAMPLE_RESULT.rationale)).toBeDefined();
  });

  it("renders every field with its expected and extracted values", () => {
    renderView();
    expect(screen.getByText("Brand name")).toBeDefined();
    expect(screen.getAllByText("Stone's Throw")).toHaveLength(2); // expected + found
    expect(screen.getByText("750 mL")).toBeDefined(); // expected
    expect(screen.getByText("375 mL")).toBeDefined(); // found mismatch
  });

  it("labels a not-checked field rather than hiding it", () => {
    renderView();
    expect(screen.getByText("Country of origin")).toBeDefined();
    expect(screen.getByText("Not checked")).toBeDefined();
  });

  it("does not rely on color alone — each status carries a text label", () => {
    renderView();
    // Status words from the badges (Match / Review / Mismatch) are present.
    expect(screen.getAllByText("Match").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Mismatch").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Review").length).toBeGreaterThan(0);
  });

  it("surfaces the Government Health Warning with its own verdict and issues", () => {
    renderView();
    expect(screen.getByRole("heading", { name: /Government Health Warning/i })).toBeDefined();
    expect(screen.getByText("Altered")).toBeDefined();
    expect(screen.getByText(/header is not in all capitals/i)).toBeDefined();
  });

  it("places one overlay button per located region once the image loads", () => {
    renderView();
    loadImage();
    // 4 fields with boxes + the warning = 5 highlightable regions.
    expect(screen.getAllByRole("button", { name: /Highlight .* on the label/i })).toHaveLength(5);
  });

  it("toggles selection when a field row is clicked", () => {
    renderView();
    const brandRow = screen.getByRole("button", { name: /Brand name/i });
    expect(brandRow.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(brandRow);
    expect(brandRow.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(brandRow);
    expect(brandRow.getAttribute("aria-pressed")).toBe("false");
  });

  it("withholds overlays until the image's natural size is known", () => {
    renderView();
    // Before the img fires load, no overlay buttons exist.
    expect(screen.queryByRole("button", { name: /Highlight .* on the label/i })).toBeNull();
  });
});
