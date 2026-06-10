import * as React from "react";

import { cn } from "@/lib/utils";
import type { BoundingBox } from "@/lib/verification";
import type { VerificationStatus } from "@/lib/status";

/** One highlightable region on the label image. */
export interface ImageRegion {
  /** Stable key matching the field/row this region belongs to. */
  key: string;
  box: BoundingBox;
  status: VerificationStatus;
  /** Accessible name for the region, e.g. the field label. */
  label: string;
}

// Border color per status for the overlay rectangles. Kept distinct from fill
// so a faint tint reads against busy artwork while the border stays crisp.
const BORDER: Record<VerificationStatus, string> = {
  match: "border-match",
  warning: "border-warning",
  mismatch: "border-mismatch",
};

const FILL: Record<VerificationStatus, string> = {
  match: "bg-match/10",
  warning: "bg-warning/10",
  mismatch: "bg-mismatch/10",
};

interface LabelImageProps {
  /** Object URL or path of the original label artwork. */
  src: string;
  alt?: string;
  regions: ImageRegion[];
  /** Key of the currently selected region (highlighted + scrolled into view). */
  activeKey?: string | null;
  /** Selecting a region by clicking its box. */
  onSelect?: (key: string) => void;
  className?: string;
}

/**
 * The original label artwork with verification regions drawn over it. Boxes are
 * positioned as percentages of the image's natural dimensions, so the overlay
 * stays aligned at any rendered size. Clicking a box selects its field; the
 * active region is emphasized and the rest dimmed, so the connection between the
 * extracted-field row and where it sits on the label is obvious.
 */
export function LabelImage({
  src,
  alt = "Original label artwork",
  regions,
  activeKey,
  onSelect,
  className,
}: LabelImageProps) {
  // Natural pixel dimensions of the loaded image; boxes (in pixel space) are
  // converted to percentages against these. Until the image loads we have no
  // basis to place overlays, so they are withheld.
  const [natural, setNatural] = React.useState<{ w: number; h: number } | null>(null);

  function handleLoad(event: React.SyntheticEvent<HTMLImageElement>) {
    const img = event.currentTarget;
    if (img.naturalWidth && img.naturalHeight) {
      setNatural({ w: img.naturalWidth, h: img.naturalHeight });
    }
  }

  const hasActive = Boolean(activeKey);

  return (
    <div className={cn("relative inline-block max-w-full", className)}>
      <img
        src={src}
        alt={alt}
        onLoad={handleLoad}
        className="block h-auto max-w-full rounded-md border"
      />
      {natural &&
        regions.map((region) => {
          const left = (region.box.x_min / natural.w) * 100;
          const top = (region.box.y_min / natural.h) * 100;
          const width = ((region.box.x_max - region.box.x_min) / natural.w) * 100;
          const height = ((region.box.y_max - region.box.y_min) / natural.h) * 100;
          const isActive = region.key === activeKey;

          return (
            <button
              type="button"
              key={region.key}
              aria-label={`Highlight ${region.label} on the label`}
              aria-pressed={isActive}
              onClick={() => onSelect?.(region.key)}
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
              }}
              className={cn(
                "absolute rounded-sm border-2 transition-opacity focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
                BORDER[region.status],
                FILL[region.status],
                // When a region is selected, fade the others so the focus is
                // unmistakable; otherwise show all at full strength.
                hasActive && !isActive ? "opacity-30" : "opacity-100",
                isActive && "ring-2 ring-ring ring-offset-1",
              )}
            />
          );
        })}
    </div>
  );
}
