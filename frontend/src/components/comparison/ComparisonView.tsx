import * as React from "react";

import { cn } from "@/lib/utils";
import {
  FIELD_STATUS_COLOR,
  WARNING_VERDICT_COLOR,
  fieldLabel,
  type VerificationResult,
} from "@/lib/verification";
import { FieldComparisonTable } from "./FieldComparisonTable";
import { GovernmentWarningCard } from "./GovernmentWarningCard";
import { LabelImage, type ImageRegion } from "./LabelImage";
import { StatusLegend } from "./StatusLegend";
import { VerdictBanner } from "./VerdictBanner";

/** Stable key used for the Government Health Warning's selectable region. */
const WARNING_KEY = "government_warning";

interface ComparisonViewProps {
  result: VerificationResult;
  /** Object URL or path of the uploaded label artwork. */
  imageSrc: string;
  imageAlt?: string;
  className?: string;
}

/**
 * The result screen: an obvious verdict banner over three aligned panes —
 * the application (expected) and the extracted label fields side by side, and
 * the original artwork with the matched regions drawn on it. Selecting a field
 * row (or the warning) highlights its region on the image and vice versa, so an
 * agent can trace any flagged value straight back to where it sits on the label.
 */
export function ComparisonView({ result, imageSrc, imageAlt, className }: ComparisonViewProps) {
  const [activeKey, setActiveKey] = React.useState<string | null>(null);

  // Build the highlightable image regions from every field (and the warning)
  // that carries a bounding box. Memoized so identity is stable across selects.
  const regions = React.useMemo<ImageRegion[]>(() => {
    const out: ImageRegion[] = [];
    for (const field of result.fields) {
      if (field.box) {
        out.push({
          key: field.field,
          box: field.box,
          status: FIELD_STATUS_COLOR[field.status],
          label: fieldLabel(field.field),
        });
      }
    }
    const warning = result.government_warning;
    if (warning.box) {
      out.push({
        key: WARNING_KEY,
        box: warning.box,
        status: WARNING_VERDICT_COLOR[warning.verdict],
        label: "Government Health Warning",
      });
    }
    return out;
  }, [result]);

  // Toggle selection: clicking the active row/region clears it.
  const select = React.useCallback((key: string) => {
    setActiveKey((current) => (current === key ? null : key));
  }, []);

  return (
    <div className={cn("space-y-6", className)}>
      <VerdictBanner
        verdict={result.overall}
        rationale={result.rationale}
        summary={result.summary}
      />

      <StatusLegend />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {/* Panes 1 + 2: expected vs extracted, aligned per field. */}
        <div className="space-y-4">
          <FieldComparisonTable fields={result.fields} activeField={activeKey} onSelect={select} />
          <GovernmentWarningCard
            result={result.government_warning}
            fieldKey={WARNING_KEY}
            active={activeKey === WARNING_KEY}
            onSelect={select}
          />
        </div>

        {/* Pane 3: original artwork with region overlays. Sticky on wide
            screens so it stays in view while scanning the field list. */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Original label
          </h3>
          <LabelImage
            src={imageSrc}
            alt={imageAlt}
            regions={regions}
            activeKey={activeKey}
            onSelect={select}
          />
        </div>
      </div>
    </div>
  );
}
