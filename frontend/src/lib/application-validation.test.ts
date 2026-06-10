import { describe, expect, it } from "vitest";

import { EMPTY_APPLICATION_FORM, type ApplicationForm } from "@/lib/application";
import { validateApplication } from "@/lib/application-validation";

/** A minimally-valid application (brand + source + type filled). */
function validForm(overrides: Partial<ApplicationForm> = {}): ApplicationForm {
  return {
    ...EMPTY_APPLICATION_FORM,
    brandName: "Old Tom Distillery",
    source: "domestic",
    productType: "distilled_spirits",
    ...overrides,
  };
}

describe("validateApplication", () => {
  it("passes a minimally complete application", () => {
    expect(validateApplication(validForm())).toEqual({});
  });

  it("requires brand name, source, and product type", () => {
    const errors = validateApplication(EMPTY_APPLICATION_FORM);
    expect(errors.brandName).toBeDefined();
    expect(errors.source).toBeDefined();
    expect(errors.productType).toBeDefined();
  });

  it("treats whitespace-only brand name as missing", () => {
    expect(validateApplication(validForm({ brandName: "   " })).brandName).toBeDefined();
  });

  it("requires country of origin for imported products", () => {
    const errors = validateApplication(validForm({ source: "imported", countryOfOrigin: "" }));
    expect(errors.countryOfOrigin).toBeDefined();
  });

  it("accepts imported products with a country of origin", () => {
    const errors = validateApplication(
      validForm({ source: "imported", countryOfOrigin: "Scotland" }),
    );
    expect(errors.countryOfOrigin).toBeUndefined();
  });

  it("rejects an out-of-range alcohol percentage", () => {
    expect(
      validateApplication(validForm({ alcoholContentPct: "150" })).alcoholContentPct,
    ).toBeDefined();
    expect(
      validateApplication(validForm({ alcoholContentPct: "abc" })).alcoholContentPct,
    ).toBeDefined();
  });

  it("accepts a valid alcohol percentage", () => {
    expect(
      validateApplication(validForm({ alcoholContentPct: "45" })).alcoholContentPct,
    ).toBeUndefined();
  });

  it("rejects a malformed vintage year", () => {
    expect(validateApplication(validForm({ vintage: "21" })).vintage).toBeDefined();
    expect(validateApplication(validForm({ vintage: "3000" })).vintage).toBeDefined();
  });

  it("accepts a plausible vintage year", () => {
    expect(validateApplication(validForm({ vintage: "2021" })).vintage).toBeUndefined();
  });
});
