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
      <div className="flex flex-wrap items-center justify-between gap-2.5 px-[18px] py-3.5">
        <div className="flex items-center gap-2.5">
          <h3 className="text-[15px] font-extrabold text-fed-navy">Government Warning Statement</h3>
          <span className="rounded bg-fed-red-wash px-2 py-[3px] text-[11px] font-bold tracking-[.3px] text-fed-red-deep">
            MANDATORY · 27 CFR §16.21
          </span>
        </div>
        <span
          className="inline-flex items-center gap-[7px] text-[13px] font-extrabold"
          style={{ color: meta.accent }}
        >
          <span aria-hidden="true">{meta.icon}</span> {meta.label}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 px-[18px] pb-3.5">
        <Badge ok={found !== null} text="Statement present" />
        <Badge ok={result.header_all_caps} text="Header in capitals" />
        <Badge
          ok={found === null ? false : result.similarity >= 0.97}
          text={`Wording ${found === null ? "" : `${Math.round(result.similarity * 100)}%`} exact`}
        />
      </div>

      <div className="grid grid-cols-1 gap-px border-t border-[#e6e8ea] bg-[#e6e8ea] md:grid-cols-2">
        <div className="bg-[#f3f8f4] px-4 py-3.5">
          <div className="mb-2 text-[11px] font-bold uppercase tracking-[.5px] text-fed-green">
            Required by TTB
          </div>
          <p className="text-xs leading-[1.6] text-[#2b3b2d]">
            <strong className="font-extrabold">GOVERNMENT WARNING:</strong> {REQUIRED_BODY}
          </p>
        </div>
        <div className="px-4 py-3.5" style={{ background: meta.detBg }}>
          <div
            className="mb-2 text-[11px] font-bold uppercase tracking-[.5px]"
            style={{ color: meta.accent }}
          >
            Detected on Label
          </div>
          {found ? (
            <p className="text-xs leading-[1.6] text-[#2b2b2b]">{found}</p>
          ) : (
            <p className="text-xs font-semibold leading-[1.6] text-fed-red-deep">
              No Government Warning statement could be located on this label.
            </p>
          )}
          {result.issues.length > 0 && (
            <ul
              className="mt-2 space-y-1 text-[11.5px] leading-snug"
              style={{ color: meta.accent }}
            >
              {result.issues.map((issue) => (
                <li key={issue}>• {issue}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
