/**
 * USWDS-style "official government website" banner. A familiar, trust-building
 * strip that sits above the header on every federal site. Kept static (no
 * expand/collapse) to match the "clean, obvious, no hunting for buttons"
 * guidance from the discovery interviews.
 */
export function GovBanner() {
  return (
    <div className="bg-secondary text-secondary-foreground">
      <div className="container flex items-center gap-2 py-1 text-xs">
        <span aria-hidden="true">🇺🇸</span>
        <span>An official website of the United States government</span>
      </div>
    </div>
  );
}
