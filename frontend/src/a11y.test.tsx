import { cleanup, render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

import { App } from "./App";
import { ComparisonView } from "./components/comparison/ComparisonView";
import { SAMPLE_RESULT } from "./lib/verification.fixture";
import { BatchPage } from "./pages/BatchPage";
import { VerifyPage } from "./pages/VerifyPage";

// Gate on WCAG 2.0 + 2.1, levels A and AA — the standard for federal sites.
const AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectNoAaViolations(ui: ReactElement) {
  const { container } = render(ui);
  const results = await axe(container, { runOnly: { type: "tag", values: AA_TAGS } });
  expect(results).toHaveNoViolations();
}

afterEach(cleanup);

describe("WCAG 2.1 AA accessibility", () => {
  it("home / app shell", async () => {
    await expectNoAaViolations(<App />);
  });

  it("verify form (empty state)", async () => {
    await expectNoAaViolations(
      <MemoryRouter>
        <VerifyPage />
      </MemoryRouter>,
    );
  });

  it("batch upload page", async () => {
    await expectNoAaViolations(
      <MemoryRouter>
        <BatchPage />
      </MemoryRouter>,
    );
  });

  it("comparison view (verdict, all statuses)", async () => {
    await expectNoAaViolations(
      <MemoryRouter>
        <ComparisonView
          result={SAMPLE_RESULT}
          imageSrc="/sample-label.png"
          imageAlt="Sample label artwork"
        />
      </MemoryRouter>,
    );
  });
});
