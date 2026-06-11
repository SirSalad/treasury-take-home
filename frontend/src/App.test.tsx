import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the agency header and the review queue", async () => {
    render(<App />);
    expect(
      screen.getByRole("heading", { level: 1, name: /COLA Label Verification/i }),
    ).toBeDefined();
    expect(await screen.findByRole("heading", { name: /My Review Queue/i })).toBeDefined();
  });

  it("offers the primary navigation", () => {
    render(<App />);
    const nav = screen.getAllByRole("navigation", { name: /Primary/i })[0];
    expect(nav.textContent).toContain("Review Queue");
    expect(nav.textContent).toContain("New Verification");
    expect(nav.textContent).toContain("Batch Upload");
  });
});
