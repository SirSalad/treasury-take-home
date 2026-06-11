import { fieldLabel, type FieldResult, type FieldStatus } from "@/lib/verification";

/**
 * The Verification Checklist (claude-design): one compact row per requirement —
 * what the application says, what was read off the label, the result, and a
 * numbered chip that ties the row to its highlight box on the artwork.
 * Hovering or focusing a row highlights the matching region.
 */

const STATUS_META: Record<FieldStatus, { icon: string; label: string; color: string }> = {
  match: { icon: "✓", label: "Pass", color: "#226e2a" },
  soft_warning: { icon: "⚠", label: "Check", color: "#7a5a00" },
  mismatch: { icon: "✗", label: "Fail", color: "#b50909" },
  not_checked: { icon: "—", label: "Not checked", color: "#6e767e" },
};

interface ReviewChecklistProps {
  fields: FieldResult[];
  /** Region number per field key (fields with a located box), for the chips. */
  regionNumbers: Map<string, number>;
  activeKey: string | null;
  onActivate: (key: string | null) => void;
  onSelect: (key: string) => void;
}

export function ReviewChecklist({
  fields,
  regionNumbers,
  activeKey,
  onActivate,
  onSelect,
}: ReviewChecklistProps) {
  const passed = fields.filter((f) => f.status === "match").length;
  const checked = fields.filter((f) => f.status !== "not_checked").length;

  return (
    <section
      aria-label="Verification checklist"
      className="overflow-hidden rounded-[10px] border border-fed-line bg-white shadow-card"
    >
      <div className="flex items-center justify-between border-b border-[#e6e8ea] px-[18px] py-2.5">
        <h3 className="text-[14.5px] font-extrabold text-fed-navy">Verification Checklist</h3>
        <span className="text-[12.5px] text-fed-gray">
          {passed} of {checked} checks passed
        </span>
      </div>
      <div className="grid grid-cols-[1.35fr_1.35fr_110px_30px] gap-0 border-b border-[#e6e8ea] bg-fed-head-bg px-[18px] py-1.5 text-[10.5px] font-bold uppercase tracking-[.5px] text-fed-gray-light">
        <div>Requirement</div>
        <div>On Label</div>
        <div>Result</div>
        <div />
      </div>
      {/* Cap the row list so a many-field label keeps the Government Warning
          below it on screen; longer lists scroll within this region. */}
      <div className="max-h-[290px] overflow-y-auto">
        {fields.map((field) => {
          const meta = STATUS_META[field.status];
          const num = regionNumbers.get(field.field);
          const isActive = activeKey === field.field;
          return (
            <button
              type="button"
              key={field.field}
              onMouseEnter={() => onActivate(field.field)}
              onMouseLeave={() => onActivate(null)}
              onFocus={() => onActivate(field.field)}
              onBlur={() => onActivate(null)}
              onClick={() => onSelect(field.field)}
              aria-label={`${fieldLabel(field.field)}: ${meta.label}. Application: ${field.expected ?? "not supplied"}. On label: ${field.found ?? "not found"}.`}
              className={`grid w-full grid-cols-[1.35fr_1.35fr_110px_30px] items-center gap-0 border-b border-fed-line-soft px-[18px] py-2.5 text-left transition-colors last:border-b-0 focus-visible:outline-none ${
                isActive
                  ? "bg-fed-blue-wash shadow-[inset_3px_0_0_#005ea2]"
                  : "hover:bg-fed-blue-wash"
              }`}
            >
              <div className="min-w-0 pr-3">
                <div className="text-[13.5px] font-bold text-fed-ink">
                  {fieldLabel(field.field)}
                </div>
                <div
                  className="mt-px truncate text-[11.5px] text-fed-gray-light"
                  title={field.expected ?? undefined}
                >
                  App: {field.expected ?? "—"}
                </div>
              </div>
              <div
                className="min-w-0 truncate pr-3 text-[13px] font-medium text-fed-slate"
                title={field.found ?? undefined}
              >
                {field.found ?? <span className="text-fed-gray-light">Not found</span>}
              </div>
              <div>
                <span
                  className="inline-flex items-center gap-[5px] text-xs font-bold"
                  style={{ color: meta.color }}
                >
                  <span aria-hidden="true">{meta.icon}</span> {meta.label}
                </span>
              </div>
              <div>
                {num !== undefined && (
                  <span
                    aria-hidden="true"
                    className="flex h-[22px] w-[22px] items-center justify-center rounded-full text-[11px] font-bold"
                    style={{
                      color: meta.color,
                      border: `1.5px solid ${meta.color}`,
                      background: "#fff",
                    }}
                  >
                    {num}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
