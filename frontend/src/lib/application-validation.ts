/**
 * Client-side validation for the {@link ApplicationForm}.
 *
 * Rules are intentionally lenient: this form is filled in by busy agents of
 * varying tech comfort, so we only hard-block on the few fields that are
 * genuinely required to run a verification, and we give plain-language,
 * specific error messages. Everything else is optional and free-form.
 */

import type { ApplicationForm, ProductType } from "@/lib/application";

/** Map of field name → error message for every field that failed validation. */
export type ApplicationErrors = Partial<Record<keyof ApplicationForm, string>>;

const CURRENT_YEAR = new Date().getFullYear();

export function validateApplication(form: ApplicationForm): ApplicationErrors {
  const errors: ApplicationErrors = {};

  // Brand name is the single most important field to compare against the label.
  if (!form.brandName.trim()) {
    errors.brandName = "Enter the brand name as it appears on the label.";
  }

  if (!form.source) {
    errors.source = "Select whether the product is domestic or imported.";
  }

  if (!form.productType) {
    errors.productType = "Select the product type.";
  }

  // Country of origin is required by TTB for imported products.
  if (form.source === "imported" && !form.countryOfOrigin.trim()) {
    errors.countryOfOrigin = "Imported products require a country of origin.";
  }

  // Alcohol content, when given as a percent, must be a sane number.
  if (form.alcoholContentPct.trim()) {
    const pct = Number(form.alcoholContentPct);
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) {
      errors.alcoholContentPct = "Enter alcohol content as a percent between 0 and 100.";
    }
  }

  // Vintage, when given, must look like a 4-digit year that isn't in the future.
  if (form.vintage.trim()) {
    const year = Number(form.vintage);
    if (!/^\d{4}$/.test(form.vintage.trim()) || year < 1800 || year > CURRENT_YEAR + 1) {
      errors.vintage = `Enter a 4-digit year between 1800 and ${CURRENT_YEAR + 1}.`;
    }
  }

  return errors;
}

/** Product types for which wine-only fields (appellation, vintage) apply. */
export function isWine(productType: ProductType | ""): boolean {
  return productType === "wine";
}
