/**
 * USWDS-style banner strip above the header. The federal design language is
 * part of the prototype's look, but this is a take-home exercise — so the
 * strip carries a non-affiliation disclaimer instead of the official-website
 * claim. The small stars-and-stripes glyph is drawn in CSS (no image request,
 * works offline). Kept static (no expand/collapse) to match the "clean,
 * obvious, no hunting for buttons" guidance from the discovery interviews.
 */
export function GovBanner() {
  return (
    <div className="border-b border-[#dfe3e8] bg-[#f0f0f0]">
      <div className="mx-auto flex max-w-[1480px] items-center gap-2.5 px-7 py-[7px] text-[11.5px] text-fed-ink">
        <span
          aria-hidden="true"
          className="relative h-[11px] w-4 flex-none overflow-hidden rounded-[1px] shadow-[0_0_0_1px_rgba(0,0,0,.12)]"
          style={{
            background:
              "repeating-linear-gradient(180deg, #b22234 0, #b22234 1.571px, #fff 1.571px, #fff 3.143px)",
          }}
        >
          <span className="absolute left-0 top-0 h-[6px] w-[7px] bg-[#3c3b6e]" />
        </span>
        <span className="text-fed-slate">
          Not endorsed by any governmental agency
        </span>
      </div>
    </div>
  );
}
