/**
 * Batch-verification helpers: the CSV manifest format, a small dependency-free
 * CSV parser/serializer, and the mapping from a manifest row onto the
 * {@link ApplicationForm} the verify endpoint accepts.
 *
 * Manifest format (one row per label):
 *   image          — filename of the label image uploaded alongside the CSV
 *   brand_name     — required; everything else optional
 *   product_type   — wine | distilled_spirits | malt_beverage
 *   source         — domestic | imported
 *   class_type, alcohol_content_pct, net_contents, name_and_address, vintage
 */

import {
  EMPTY_APPLICATION_FORM,
  type ApplicationForm,
  type ProductSource,
  type ProductType,
} from "@/lib/application";

/** Columns of the batch CSV manifest, in file order. */
export const BATCH_COLUMNS = [
  "image",
  "brand_name",
  "product_type",
  "source",
  "class_type",
  "alcohol_content_pct",
  "net_contents",
  "name_and_address",
  "vintage",
] as const;

export type BatchColumn = (typeof BATCH_COLUMNS)[number];

/** One editable manifest row. All values are strings (controlled inputs). */
export type BatchRow = Record<BatchColumn, string>;

export const EMPTY_ROW: BatchRow = {
  image: "",
  brand_name: "",
  product_type: "",
  source: "",
  class_type: "",
  alcohol_content_pct: "",
  net_contents: "",
  name_and_address: "",
  vintage: "",
};

/** The downloadable sample manifest: a header plus three illustrative rows. */
export const SAMPLE_CSV = [
  BATCH_COLUMNS.join(","),
  `old_tom.png,OLD TOM DISTILLERY,distilled_spirits,domestic,Kentucky Straight Bourbon Whiskey,45,750 mL,"Old Tom Distillery Co., Bardstown, KY",`,
  `coastal_vines.png,Coastal Vines,wine,imported,Sparkling Wine,12,750ml,"Coastal Vines Cellars, Napa, CA",2023`,
  `harbor_light.png,Harbor Light Lager,malt_beverage,domestic,Lager,4.8,12 FL OZ,"Harbor Light Brewing, Portland, ME",`,
].join("\n");

/**
 * Parse CSV text into rows of cells. Handles quoted fields (embedded commas,
 * doubled quotes, newlines) — the subset Excel and Sheets emit. Returns rows
 * of raw strings; header mapping happens in {@link parseManifest}.
 */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      cell = "";
      rows.push(row);
      row = [];
    } else {
      cell += ch;
    }
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  // Drop fully-empty trailing rows (a final newline is common).
  return rows.filter((r) => r.some((c) => c.trim() !== ""));
}

/**
 * Map parsed CSV onto manifest rows using the header line. Unknown columns are
 * ignored; missing ones come back empty. Throws with a friendly message when
 * the header is unusable.
 */
export function parseManifest(text: string): BatchRow[] {
  const rows = parseCsv(text);
  if (rows.length < 2) {
    throw new Error("The CSV needs a header row plus at least one data row.");
  }
  const header = rows[0].map((h) => h.trim().toLowerCase());
  if (!header.includes("brand_name")) {
    throw new Error(
      `The CSV header must include "brand_name" (found: ${header.join(", ") || "nothing"}). Download the sample CSV for the expected format.`,
    );
  }
  return rows.slice(1).map((cells) => {
    const row: BatchRow = { ...EMPTY_ROW };
    header.forEach((name, i) => {
      if ((BATCH_COLUMNS as readonly string[]).includes(name)) {
        row[name as BatchColumn] = (cells[i] ?? "").trim();
      }
    });
    return row;
  });
}

const PRODUCT_TYPES: ReadonlyArray<ProductType> = ["wine", "distilled_spirits", "malt_beverage"];
const SOURCES: ReadonlyArray<ProductSource> = ["domestic", "imported"];

/** Convert one manifest row into the form object `POST /api/verify` accepts. */
export function rowToApplication(row: BatchRow): ApplicationForm {
  const productType = PRODUCT_TYPES.find((t) => t === row.product_type) ?? "";
  const source = SOURCES.find((s) => s === row.source) ?? "";
  return {
    ...EMPTY_APPLICATION_FORM,
    brandName: row.brand_name,
    productType,
    source,
    classType: row.class_type,
    alcoholContentPct: row.alcohol_content_pct,
    netContents: row.net_contents,
    nameAndAddress: row.name_and_address,
    vintage: row.vintage,
  };
}

/** Pre-flight problems for one row, shown inline before the run is allowed. */
export function rowProblems(row: BatchRow, imageNames: ReadonlySet<string>): string[] {
  const problems: string[] = [];
  if (!row.brand_name.trim()) problems.push("brand_name is required");
  if (!row.image.trim()) {
    problems.push("image filename is required");
  } else if (!imageNames.has(row.image.trim())) {
    problems.push(`no uploaded file named "${row.image.trim()}"`);
  }
  if (row.product_type && !PRODUCT_TYPES.some((t) => t === row.product_type)) {
    problems.push(`product_type must be one of: ${PRODUCT_TYPES.join(", ")}`);
  }
  if (row.source && !SOURCES.some((s) => s === row.source)) {
    problems.push(`source must be one of: ${SOURCES.join(", ")}`);
  }
  return problems;
}
