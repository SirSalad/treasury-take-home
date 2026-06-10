/**
 * The "expected" label data an agent enters from a TTB COLA application
 * (Form 5100.31, OMB Control No. 1513-0020). These are the fields the physical
 * label artwork is verified against. Shapes mirror the backend `Application`
 * model so this object can later be POSTed as-is when the flow is wired up.
 */

export type ProductSource = "domestic" | "imported";

export type ProductType = "wine" | "distilled_spirits" | "malt_beverage";

export interface ApplicationForm {
  // --- Identification ---
  serialNumber: string;
  plantRegistryNumber: string;
  source: ProductSource | "";
  productType: ProductType | "";

  // --- Label content the agent verifies ---
  brandName: string;
  fancifulName: string;
  classType: string;
  /** Alcohol by volume, percent. Kept as a string for controlled inputs. */
  alcoholContentPct: string;
  /** Alcohol statement exactly as printed, e.g. "45% Alc./Vol. (90 Proof)". */
  alcoholContentText: string;
  netContents: string;

  // --- Responsible party / origin ---
  nameAndAddress: string;
  countryOfOrigin: string;

  // --- Wine-specific ---
  appellation: string;
  vintage: string;
}

/** Human-readable choices for the product-source select. */
export const PRODUCT_SOURCE_OPTIONS: ReadonlyArray<{ value: ProductSource; label: string }> = [
  { value: "domestic", label: "Domestic (made in the U.S.)" },
  { value: "imported", label: "Imported" },
];

/** Human-readable choices for the product-type select. */
export const PRODUCT_TYPE_OPTIONS: ReadonlyArray<{ value: ProductType; label: string }> = [
  { value: "distilled_spirits", label: "Distilled spirits" },
  { value: "wine", label: "Wine" },
  { value: "malt_beverage", label: "Malt beverage (beer)" },
];

/** An empty form, used as the initial state. */
export const EMPTY_APPLICATION_FORM: ApplicationForm = {
  serialNumber: "",
  plantRegistryNumber: "",
  source: "",
  productType: "",
  brandName: "",
  fancifulName: "",
  classType: "",
  alcoholContentPct: "",
  alcoholContentText: "",
  netContents: "",
  nameAndAddress: "",
  countryOfOrigin: "",
  appellation: "",
  vintage: "",
};
