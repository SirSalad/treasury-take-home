import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the agency header and landing page", () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: /Label Verification/i })).toBeDefined();
    expect(screen.getByRole("heading", { name: /Verify alcohol labels/i })).toBeDefined();
  });

  it("shows the verification status legend", () => {
    render(<App />);
    expect(screen.getByText(/How results are flagged/i)).toBeDefined();
    expect(screen.getByText("Match")).toBeDefined();
    expect(screen.getByText("Mismatch")).toBeDefined();
  });
});
