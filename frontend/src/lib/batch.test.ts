import { describe, expect, it } from "vitest";

import { parseCsv, parseManifest, rowProblems, SAMPLE_CSV } from "./batch";

describe("parseCsv", () => {
  it("splits simple rows and trims trailing newlines", () => {
    expect(parseCsv("a,b\nc,d\n")).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("handles quoted fields with commas, doubled quotes, and CRLF", () => {
    const text = 'name,address\r\n"Old Tom, LLC","123 ""Main"" St"\r\n';
    expect(parseCsv(text)).toEqual([
      ["name", "address"],
      ["Old Tom, LLC", '123 "Main" St'],
    ]);
  });
});

describe("parseManifest", () => {
  it("round-trips the shipped sample CSV", () => {
    const rows = parseManifest(SAMPLE_CSV);
    expect(rows).toHaveLength(3);
    expect(rows[0].brand_name).toBe("OLD TOM DISTILLERY");
    expect(rows[0].name_and_address).toBe("Old Tom Distillery Co., Bardstown, KY");
    expect(rows[1].vintage).toBe("2023");
    expect(rows[2].product_type).toBe("malt_beverage");
  });

  it("ignores unknown columns and fills missing ones empty", () => {
    const rows = parseManifest("brand_name,mystery\nAcme,42\n");
    expect(rows[0].brand_name).toBe("Acme");
    expect(rows[0].image).toBe("");
  });

  it("rejects a CSV without the brand_name column", () => {
    expect(() => parseManifest("foo,bar\n1,2\n")).toThrow(/brand_name/);
  });

  it("rejects a header-only file", () => {
    expect(() => parseManifest("brand_name\n")).toThrow(/at least one data row/);
  });
});

describe("rowProblems", () => {
  const base = parseManifest(SAMPLE_CSV)[0];

  it("accepts a complete row whose image was uploaded", () => {
    expect(rowProblems(base, new Set(["old_tom.png"]))).toEqual([]);
  });

  it("flags missing brand, missing image file, and bad enums", () => {
    const row = { ...base, brand_name: " ", image: "nope.png", product_type: "cider" };
    const problems = rowProblems(row, new Set(["old_tom.png"]));
    expect(problems.join(" ")).toMatch(/brand_name is required/);
    expect(problems.join(" ")).toMatch(/no uploaded file named "nope.png"/);
    expect(problems.join(" ")).toMatch(/product_type/);
  });
});
