import * as React from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError } from "@/lib/api";
import {
  BATCH_COLUMNS,
  EMPTY_ROW,
  parseManifest,
  rowProblems,
  rowToApplication,
  SAMPLE_CSV,
  type BatchRow,
} from "@/lib/batch";
import type { OverallVerdict } from "@/lib/verification";

/**
 * Batch Verification (claude-design): upload a CSV manifest plus the label
 * images it names, fix anything up in the editable table, and run. Each row
 * goes through the same `POST /api/verify` pipeline as a single check (so
 * every result also lands in the review queue), results stream in as they
 * finish, and the summary surfaces only the labels that need human eyes.
 */

type RowOutcome =
  | { state: "pending" }
  | { state: "running" }
  | { state: "done"; submissionId: number; overall: OverallVerdict; rationale: string }
  | { state: "error"; message: string };

type PagePhase = "edit" | "running" | "done";

const OUTCOME_PILL: Record<string, { label: string; icon: string; color: string; bg: string }> = {
  pass: { label: "Cleared", icon: "✓", color: "#226e2a", bg: "#eaf4ec" },
  warning: { label: "Needs judgment", icon: "⚠", color: "#7a5a00", bg: "#faf3d1" },
  fail: { label: "Failed", icon: "✗", color: "#b50909", bg: "#fdeced" },
  error: { label: "Unreadable", icon: "✗", color: "#b50909", bg: "#fdeced" },
};

const CELL_LABEL: Record<string, string> = {
  image: "Image file",
  brand_name: "Brand name",
  product_type: "Product type",
  source: "Source",
  class_type: "Class / type",
  alcohol_content_pct: "ABV %",
  net_contents: "Net contents",
  name_and_address: "Name & address",
  vintage: "Vintage",
};

function downloadSample() {
  const blob = new Blob([SAMPLE_CSV], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "batch_manifest_sample.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function BatchPage() {
  const navigate = useNavigate();
  const [rows, setRows] = React.useState<BatchRow[]>([]);
  const [images, setImages] = React.useState<Map<string, File>>(new Map());
  const [csvError, setCsvError] = React.useState<string | null>(null);
  const [phase, setPhase] = React.useState<PagePhase>("edit");
  const [outcomes, setOutcomes] = React.useState<RowOutcome[]>([]);

  const imageNames = React.useMemo(() => new Set(images.keys()), [images]);
  const problems = React.useMemo(
    () => rows.map((row) => rowProblems(row, imageNames)),
    [rows, imageNames],
  );
  const ready = rows.length > 0 && problems.every((p) => p.length === 0);

  function onCsvChosen(file: File) {
    file
      .text()
      .then((text) => {
        setRows(parseManifest(text));
        setCsvError(null);
        setPhase("edit");
        setOutcomes([]);
      })
      .catch((err: unknown) => {
        setCsvError(err instanceof Error ? err.message : "Could not read that CSV file.");
      });
  }

  function onImagesChosen(files: FileList) {
    setImages((current) => {
      const next = new Map(current);
      for (const file of Array.from(files)) next.set(file.name, file);
      return next;
    });
  }

  function setCell(rowIndex: number, column: string, value: string) {
    setRows((current) =>
      current.map((row, i) => (i === rowIndex ? { ...row, [column]: value } : row)),
    );
  }

  async function run() {
    setPhase("running");
    const results: RowOutcome[] = rows.map(() => ({ state: "pending" }));
    setOutcomes([...results]);

    for (let i = 0; i < rows.length; i++) {
      results[i] = { state: "running" };
      setOutcomes([...results]);
      const image = images.get(rows[i].image.trim());
      try {
        if (!image) throw new ApiError(0, `No uploaded file named "${rows[i].image}".`);
        const response = await api.verify(image, rowToApplication(rows[i]));
        results[i] = {
          state: "done",
          submissionId: response.submission_id,
          overall: response.result.overall,
          rationale: response.result.rationale,
        };
      } catch (err) {
        results[i] = {
          state: "error",
          message: err instanceof ApiError ? err.message : "Verification failed.",
        };
      }
      setOutcomes([...results]);
    }
    setPhase("done");
  }

  const doneCount = outcomes.filter((o) => o.state === "done" || o.state === "error").length;
  const cleared = outcomes.filter((o) => o.state === "done" && o.overall === "pass").length;
  const judgment = outcomes.filter((o) => o.state === "done" && o.overall === "warning").length;
  const failed = outcomes.filter(
    (o) => o.state === "error" || (o.state === "done" && o.overall === "fail"),
  ).length;

  return (
    <div className="mx-auto max-w-[1180px] pb-10">
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-fed-blue"
      >
        ← Back to Queue
      </Link>
      <h2 className="mb-1.5 text-[30px] font-extrabold tracking-[-.6px] text-fed-navy">
        Batch Verification
      </h2>
      <p className="mb-6 text-[14.5px] text-fed-gray">
        Built for peak season — drop a whole importer’s submission at once. Upload a CSV manifest
        and the label images it names, fix anything up in the table, and we surface only the labels
        that need your eyes.
      </p>

      {phase !== "running" && (
        <>
          {/* Step 1: files */}
          <div className="mb-5 rounded-xl border-2 border-dashed border-[#9bb4d0] bg-[#f3f7fc] px-6 py-7">
            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <p className="mb-1 text-[15px] font-bold text-fed-ink">1 · Manifest CSV</p>
                <p className="mb-3 text-[13px] text-fed-gray">
                  One row per label.{" "}
                  <button
                    type="button"
                    onClick={downloadSample}
                    className="font-bold text-fed-blue underline"
                  >
                    Download the sample CSV
                  </button>{" "}
                  for the expected columns.
                </p>
                <label className="inline-block cursor-pointer rounded-md bg-fed-blue px-[18px] py-[9px] text-sm font-bold text-white hover:bg-[#0b4778]">
                  Choose CSV file
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    className="sr-only"
                    onChange={(e) => e.target.files?.[0] && onCsvChosen(e.target.files[0])}
                  />
                </label>
              </div>
              <div>
                <p className="mb-1 text-[15px] font-bold text-fed-ink">2 · Label images</p>
                <p className="mb-3 text-[13px] text-fed-gray">
                  Multi-select the JPG/PNG files the manifest names ({images.size} uploaded).
                </p>
                <label className="inline-block cursor-pointer rounded-md border-2 border-fed-blue bg-white px-[18px] py-[7px] text-sm font-bold text-fed-blue hover:bg-fed-blue-wash">
                  Choose images
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    className="sr-only"
                    onChange={(e) => e.target.files && onImagesChosen(e.target.files)}
                  />
                </label>
              </div>
            </div>
            {csvError && (
              <p role="alert" className="mt-4 text-sm font-semibold text-fed-red-deep">
                {csvError}
              </p>
            )}
          </div>

          {/* Step 2: editable manifest */}
          {rows.length > 0 && (
            <div className="mb-5 overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card">
              <div className="flex items-center justify-between border-b border-[#e6e8ea] px-[18px] py-[13px]">
                <h3 className="text-[14.5px] font-extrabold text-fed-navy">
                  3 · Review &amp; edit ({rows.length} {rows.length === 1 ? "label" : "labels"})
                </h3>
                <button
                  type="button"
                  onClick={() => setRows((r) => [...r, { ...EMPTY_ROW }])}
                  className="text-[13px] font-bold text-fed-blue hover:underline"
                >
                  + Add row
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] border-collapse text-[13px]">
                  <thead>
                    <tr className="border-b-2 border-[#d6d7d9] bg-fed-head-bg text-left">
                      {BATCH_COLUMNS.map((column) => (
                        <th
                          key={column}
                          className="px-2.5 py-2 text-[10.5px] font-bold uppercase tracking-[.5px] text-fed-gray-light"
                        >
                          {CELL_LABEL[column]}
                        </th>
                      ))}
                      <th className="w-8 px-1" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, rowIndex) => (
                      <React.Fragment key={rowIndex}>
                        <tr className="border-b border-fed-line-soft">
                          {BATCH_COLUMNS.map((column) => (
                            <td key={column} className="px-1 py-1">
                              <input
                                aria-label={`Row ${rowIndex + 1} ${CELL_LABEL[column]}`}
                                value={row[column]}
                                onChange={(e) => setCell(rowIndex, column, e.target.value)}
                                className="w-full rounded border border-transparent bg-transparent px-1.5 py-1 hover:border-[#c4c8cc] focus:border-fed-blue focus:outline-none"
                              />
                            </td>
                          ))}
                          <td className="px-1 text-center">
                            <button
                              type="button"
                              aria-label={`Remove row ${rowIndex + 1}`}
                              onClick={() => setRows((r) => r.filter((_, i) => i !== rowIndex))}
                              className="rounded px-1.5 text-fed-gray-light hover:bg-fed-red-wash hover:text-fed-red"
                            >
                              ✕
                            </button>
                          </td>
                        </tr>
                        {problems[rowIndex].length > 0 && (
                          <tr className="border-b border-fed-line-soft bg-[#fffaf0]">
                            <td
                              colSpan={BATCH_COLUMNS.length + 1}
                              className="px-3 py-1 text-xs text-fed-amber"
                            >
                              ⚠ {problems[rowIndex].join(" · ")}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-[#e6e8ea] px-[18px] py-3.5">
                <button
                  type="button"
                  disabled={!ready}
                  onClick={run}
                  className="rounded-md bg-fed-blue px-6 py-3 text-[14.5px] font-bold text-white hover:bg-[#0b4778] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Verify {rows.length} {rows.length === 1 ? "label" : "labels"}
                </button>
                {!ready && (
                  <span className="ml-3 text-[12.5px] text-fed-gray">
                    Fix the flagged rows (and upload the named images) to run.
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Running progress */}
      {phase === "running" && (
        <div
          className="rounded-xl border border-[#d6d7d9] bg-white p-[30px]"
          role="status"
          aria-live="polite"
        >
          <div className="mb-[18px] flex items-center gap-3.5">
            <div
              aria-hidden="true"
              className="h-[26px] w-[26px] rounded-full border-[3px] border-[#e0e3e6] border-t-fed-blue"
              style={{ animation: "spin .8s linear infinite" }}
            />
            <p className="text-[17px] font-extrabold text-fed-navy">
              Verifying {rows.length} labels…
            </p>
          </div>
          <div className="mb-2 h-3 overflow-hidden rounded-full bg-[#e6e8ea]">
            <div
              className="h-full rounded-full transition-[width]"
              style={{
                width: `${rows.length ? (doneCount / rows.length) * 100 : 0}%`,
                background: "linear-gradient(90deg, #005ea2, #226e2a)",
              }}
            />
          </div>
          <p className="text-[13px] tabular-nums text-fed-gray">
            {doneCount} of {rows.length} done
          </p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Results */}
      {phase === "done" && (
        <>
          <div className="mb-5 grid gap-3.5 md:grid-cols-3">
            {[
              { value: cleared, label: "Auto-cleared — all checks passed", accent: "#226e2a" },
              { value: judgment, label: "Need your judgment", accent: "#7a5a00" },
              { value: failed, label: "Failed — violations or unreadable", accent: "#cd2026" },
            ].map((card) => (
              <div
                key={card.label}
                className="rounded-lg border border-fed-line bg-white px-5 py-4 shadow-card"
                style={{ borderLeft: `4px solid ${card.accent}` }}
              >
                <div
                  className="text-[32px] font-extrabold leading-none"
                  style={{ color: card.accent }}
                >
                  {card.value}
                </div>
                <div className="mt-[5px] text-[13px] font-semibold text-fed-gray">{card.label}</div>
              </div>
            ))}
          </div>
          {cleared > 0 && (
            <p className="mb-[18px] flex items-center gap-2.5 rounded-lg border border-[#bfe0c6] bg-fed-green-wash px-[18px] py-3 text-[13.5px] text-[#1e5a2d]">
              <span aria-hidden="true">✓</span>
              {rows.length} labels verified.{" "}
              <strong>You only need to look at {rows.length - cleared} of them.</strong>
            </p>
          )}
          <div className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card">
            <div className="grid grid-cols-[70px_1.4fr_1fr_1.4fr_110px] gap-0 border-b-2 border-[#d6d7d9] bg-fed-head-bg px-[18px] py-[11px] text-[10.5px] font-bold uppercase tracking-[.5px] text-fed-gray-light">
              <div>Row</div>
              <div>Brand</div>
              <div>Result</div>
              <div>Notes</div>
              <div />
            </div>
            {outcomes.map((outcome, i) => {
              const pill =
                outcome.state === "done"
                  ? OUTCOME_PILL[outcome.overall]
                  : outcome.state === "error"
                    ? OUTCOME_PILL.error
                    : null;
              const note =
                outcome.state === "done"
                  ? outcome.rationale
                  : outcome.state === "error"
                    ? outcome.message
                    : "";
              const openable = outcome.state === "done";
              return (
                <div
                  key={i}
                  role={openable ? "button" : undefined}
                  tabIndex={openable ? 0 : undefined}
                  aria-label={
                    openable
                      ? `Review ${rows[i]?.brand_name || `row ${i + 1}`}, ${pill?.label ?? ""}`
                      : undefined
                  }
                  onClick={() => openable && navigate(`/review/${outcome.submissionId}`)}
                  onKeyDown={(e) => {
                    if (openable && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      navigate(`/review/${outcome.submissionId}`);
                    }
                  }}
                  className={`grid grid-cols-[70px_1.4fr_1fr_1.4fr_110px] items-center gap-0 border-b border-fed-line-soft px-[18px] py-[13px] last:border-b-0 ${
                    openable
                      ? "cursor-pointer hover:bg-fed-blue-wash hover:shadow-[inset_3px_0_0_#005ea2] focus-visible:bg-fed-blue-wash focus-visible:outline-none"
                      : ""
                  }`}
                >
                  <div className="text-[13px] tabular-nums text-fed-gray-light">{i + 1}</div>
                  <div className="truncate pr-2 text-sm font-bold text-fed-ink">
                    {rows[i]?.brand_name || "—"}
                  </div>
                  <div>
                    {pill && (
                      <span
                        className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold"
                        style={{ color: pill.color, background: pill.bg }}
                      >
                        <span aria-hidden="true">{pill.icon}</span> {pill.label}
                      </span>
                    )}
                  </div>
                  <div className="truncate pr-2 text-[12.5px] text-fed-gray" title={note}>
                    {note}
                  </div>
                  <div className="text-right">
                    {openable && (
                      <span className="text-[12.5px] font-bold text-fed-blue">Review ›</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
