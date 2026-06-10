import "@testing-library/jest-dom/vitest";

import { expect } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";

// Register the accessibility matcher (`toHaveNoViolations`) used by the
// WCAG 2.1 AA a11y test suite (src/a11y.test.tsx).
expect.extend(axeMatchers);
