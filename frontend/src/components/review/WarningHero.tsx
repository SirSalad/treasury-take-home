import type { GovernmentWarningResult, WarningVerdict } from "@/lib/verification";

/**
 * Government Warning Statement hero (claude-design): the mandatory-statement
 * check gets its own card with a required-vs-detected diff and compliance
 * badges, because it is the single highest-stakes element on the label
 * (27 CFR Part 16) and "Jenny's catch" from the discovery interviews.
 */

const REQUIRED_BODY =
  "(1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.";

const VERDICT_META: Record<
  WarningVerdict,
  { icon: string; label: string; accent: string; detBg: string }
> = {
  compliant: { icon: "✓", label: "Compliant", accent: "#226e2a", detBg: "#f3f8f4" },
  altered: { icon: "⚠", label: "Altered", accent: "#7a5a00", detBg: "#fffaf0" },
  missing: { icon: "✗", label: "Missing", accent: "#b50909", detBg: "#fef6f6" },
};

function Badge({ ok, text }: { ok: boolean | null; text: string }) {
  const color = ok === null ? "#6e767e" : ok ? "#226e2a" : "#b50909";
  const bg = ok === null ? "#f4f5f6" : ok ? "#eaf4ec" : "#fdeced";
  const border = ok === null ? "#e4e8ec" : ok ? "#bfe0c6" : "#f3c9cb";
  const icon = ok === null ? "—" : ok ? "✓" : "✗";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md px-[11px] py-[5px] text-xs font-bold"
      style={{ color, background: bg, border: `1px solid ${border}` }}
    >
      <span aria-hidden="true">{icon}</span> {text}
    </span>
  );
}

export function WarningHero({ result }: { result: GovernmentWarningResult }) {
  const meta = VERDICT_META[result.verdict];
  const found = result.found_text;

  return (
    <section
      aria-label="Government warning statement check"
      className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card"
      style={{ borderTop: `4px solid ${meta.accent}` }}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-2.5 gap-y-1.5 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[14px] font-extrabold text-fed-navy">Government Warning Statement</h3>
          <span className="rounded bg-fed-red-wash px-1.5 py-[2px] text-[10px] font-bold tracking-[.3px] text-fed-red-deep">
            MANDATORY · 27 CFR §16.21
          </span>
        </div>
        <span
          className="inline-flex items-center gap-1.5 text-[13px] font-extrabold"
          style={{ color: meta.accent }}
        >
          <span aria-hidden="true">{meta.icon}</span> {meta.label}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5 px-4 pb-2.5">
        <Badge ok={found !== null} text="Statement present" />
        <Badge ok={result.header_all_caps ?? null} text="Header in capitals" />
        <Badge
          ok={found === null ? false : result.similarity >= 0.97}
          text={`Wording ${found === null ? "" : `${Math.round(result.similarity * 100)}%`} exact`}
        />
      </div>

      <div className="grid max-h-[150px] grid-cols-1 gap-px overflow-y-auto border-t border-[#e6e8ea] bg-[#e6e8ea] md:grid-cols-2">
        <div className="bg-[#f3f8f4] px-3.5 py-2.5">
          <div className="mb-1 text-[10px] font-bold uppercase tracking-[.5px] text-fed-green">
            Required by TTB
          </div>
          <p className="text-[11px] leading-[1.5] text-[#2b3b2d]">
            <strong className="font-extrabold">GOVERNMENT WARNING:</strong> {REQUIRED_BODY}
          </p>
        </div>
        <div className="px-3.5 py-2.5" style={{ background: meta.detBg }}>
          <div
            className="mb-1 text-[10px] font-bold uppercase tracking-[.5px]"
            style={{ color: meta.accent }}
          >
            Detected on Label
          </div>
          {found ? (
            <p className="text-[11px] leading-[1.5] text-[#2b2b2b]">{found}</p>
          ) : (
            <p className="text-[11px] font-semibold leading-[1.5] text-fed-red-deep">
              No Government Warning statement could be located on this label.
            </p>
          )}
          {(result.issues ?? []).length > 0 && (
            <ul
              className="mt-1.5 space-y-1 text-[11px] leading-snug"
              style={{ color: meta.accent }}
            >
              {(result.issues ?? []).map((issue) => (
                <li key={issue}>• {issue}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
