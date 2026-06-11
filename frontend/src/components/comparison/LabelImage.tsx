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

// Focus-zoom cap: enough to read fine print (the Government Warning is the
// smallest text on the label) without blowing a small crop into mush. No
// lower bound — a region that already fills the view needs no zoom at all.
const MAX_FOCUS_ZOOM = 4;

/** The nearest ancestor that actually scrolls, for container-scoped panning. */
function closestScrollable(el: HTMLElement | null): HTMLElement | null {
  for (let node = el; node; node = node.parentElement) {
    const style = window.getComputedStyle(node);
    if (/(auto|scroll)/.test(style.overflowY + style.overflowX)) return node;
  }
  return null;
}

interface LabelImageProps {
  /** Object URL or path of the original label artwork. */
  src: string;
  alt?: string;
  regions: ImageRegion[];
  /** Key of the currently emphasized region (hover or selection). */
  activeKey?: string | null;
  /**
   * Key of the *selected* region to focus: the image zooms so the region is
   * comfortably readable and scrolls it to the center of the viewport.
   */
  focusKey?: string | null;
  /** Magnification over the fitted size (1 = fit). Layout-affecting, so the
   * surrounding scroll container can actually pan over the zoomed image. */
  zoom?: number;
  /** Called when focusing a region wants a different zoom (auto-zoom). */
  onAutoZoom?: (zoom: number) => void;
  /** Selecting a region by clicking its box. */
  onSelect?: (key: string) => void;
  className?: string;
  /** Extra classes for the <img>, e.g. a height cap so it sizes to the viewport. */
  imgClassName?: string;
}

/**
 * The original label artwork with verification regions drawn over it. Boxes are
 * positioned as percentages of the image's natural dimensions, so the overlay
 * stays aligned at any rendered size. Clicking a box selects its field; the
 * active region is emphasized and the rest dimmed; the focused region is
 * zoomed to a readable size and centered in the scroll viewport — the "show me
 * where" gesture reviewers reach for on fine print.
 */
export function LabelImage({
  src,
  alt = "Original label artwork",
  regions,
  activeKey,
  focusKey,
  zoom = 1,
  onAutoZoom,
  onSelect,
  className,
  imgClassName,
}: LabelImageProps) {
  // Natural pixel dimensions of the loaded image; boxes (in pixel space) are
  // converted to percentages against these. Until the image loads we have no
  // basis to place overlays, so they are withheld.
  const [natural, setNatural] = React.useState<{ w: number; h: number } | null>(null);
  // The fitted (zoom = 1) rendered width, the basis for layout-affecting zoom.
  const [baseWidth, setBaseWidth] = React.useState<number | null>(null);
  const wrapperRef = React.useRef<HTMLDivElement>(null);
  const regionRefs = React.useRef(new Map<string, HTMLButtonElement>());

  // Drag-to-pan over the zoomed image. The pointer is captured on the wrapper
  // so the pan keeps tracking outside it; movement past a small threshold
  // counts as a drag and suppresses the click that would otherwise select a
  // region box under the cursor.
  const panRef = React.useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    scrollLeft: number;
    scrollTop: number;
    dragged: boolean;
  } | null>(null);
  const [panning, setPanning] = React.useState(false);

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    // Left button / primary touch only; let right-click menus through.
    if (event.button !== 0) return;
    const container = closestScrollable(wrapperRef.current);
    if (!container) return;
    panRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: container.scrollLeft,
      scrollTop: container.scrollTop,
      dragged: false,
    };
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const pan = panRef.current;
    if (!pan || event.pointerId !== pan.pointerId) return;
    const dx = event.clientX - pan.startX;
    const dy = event.clientY - pan.startY;
    if (!pan.dragged && Math.hypot(dx, dy) < 5) return; // still a click
    if (!pan.dragged) {
      // Capture only once it is a real drag — capturing on pointerdown would
      // retarget the derived click away from the region buttons.
      event.currentTarget.setPointerCapture(pan.pointerId);
    }
    pan.dragged = true;
    setPanning(true);
    const container = closestScrollable(wrapperRef.current);
    container?.scrollTo({ left: pan.scrollLeft - dx, top: pan.scrollTop - dy });
  }

  function handlePointerEnd(event: React.PointerEvent<HTMLDivElement>) {
    const pan = panRef.current;
    if (!pan || event.pointerId !== pan.pointerId) return;
    setPanning(false);
    // Keep panRef.dragged alive through the click that follows pointerup; the
    // click-capture handler below reads and clears it.
    if (!pan.dragged) panRef.current = null;
  }

  function handleClickCapture(event: React.MouseEvent<HTMLDivElement>) {
    if (panRef.current?.dragged) {
      // This click is the tail end of a pan, not a selection.
      event.preventDefault();
      event.stopPropagation();
      panRef.current = null;
    }
  }

  function handleLoad(event: React.SyntheticEvent<HTMLImageElement>) {
    const img = event.currentTarget;
    if (img.naturalWidth && img.naturalHeight) {
      setNatural({ w: img.naturalWidth, h: img.naturalHeight });
      setBaseWidth(img.clientWidth);
    }
  }

  // Focusing a region: pick a zoom that renders it comfortably wide, then
  // scroll it to the center of the nearest scrollable ancestor. Splitting the
  // two effects lets the zoomed layout settle before the scroll measures it.
  const focused = focusKey ? (regions.find((r) => r.key === focusKey) ?? null) : null;

  React.useEffect(() => {
    if (!focused || !natural || !baseWidth || !onAutoZoom) return;
    const container = closestScrollable(wrapperRef.current);
    if (!container) return;
    // Region size at zoom 1, in px (the fitted image keeps its aspect ratio).
    const baseHeight = baseWidth * (natural.h / natural.w);
    const regionW = Math.max(((focused.box.x_max - focused.box.x_min) / natural.w) * baseWidth, 8);
    const regionH = Math.max(((focused.box.y_max - focused.box.y_min) / natural.h) * baseHeight, 8);
    // Zoom so the region fills ~70% of the *viewport pane* in its tighter
    // dimension — readable, with context around it — never zooming out.
    const target = Math.min(
      MAX_FOCUS_ZOOM,
      Math.max(
        1,
        Math.min((0.7 * container.clientWidth) / regionW, (0.8 * container.clientHeight) / regionH),
      ),
    );
    if (Math.abs(target - zoom) > 0.05) onAutoZoom(Math.round(target * 4) / 4);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-fit only when the focus target or image changes, not on manual zoom
  }, [focused?.key, natural, baseWidth]);

  React.useEffect(() => {
    if (!focusKey) return;
    const el = regionRefs.current.get(focusKey);
    if (!el) return;
    // Let the zoomed layout paint, then pan ONLY the nearest scroll container
    // so the region's center meets the viewport's center. (scrollIntoView is
    // unusable here: it also scrolls the page, and a flex-centered container
    // makes start-side overflow unreachable.)
    const id = requestAnimationFrame(() => {
      const container = closestScrollable(wrapperRef.current);
      if (!container) return;
      const crect = container.getBoundingClientRect();
      const rrect = el.getBoundingClientRect();
      container.scrollTo({
        left:
          container.scrollLeft + (rrect.left + rrect.width / 2) - (crect.left + crect.width / 2),
        top: container.scrollTop + (rrect.top + rrect.height / 2) - (crect.top + crect.height / 2),
        behavior: "smooth",
      });
    });
    return () => cancelAnimationFrame(id);
  }, [focusKey, zoom, natural, baseWidth]);

  const hasActive = Boolean(activeKey);
  const zoomed = zoom !== 1 && baseWidth != null;

  return (
    // max-w-full must come off while zoomed: the wrapper is the coordinate
    // space for the %-positioned region overlays, so clamping it to the
    // container while the image grows would shear every box off the artwork.
    <div
      ref={wrapperRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerEnd}
      onPointerCancel={handlePointerEnd}
      onClickCapture={handleClickCapture}
      className={cn(
        "relative inline-block touch-none select-none",
        !zoomed && "max-w-full",
        panning ? "cursor-grabbing" : "cursor-grab",
        className,
      )}
    >
      <img
        src={src}
        alt={alt}
        onLoad={handleLoad}
        draggable={false}
        // Inline sizing overrides the fit classes while zoomed, growing the
        // layout box so the overflow container gains real scroll range.
        style={
          zoomed
            ? { width: baseWidth * zoom, maxWidth: "none", maxHeight: "none", height: "auto" }
            : undefined
        }
        className={cn("block max-w-full rounded-md border", imgClassName ?? "h-auto")}
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
              ref={(el) => {
                if (el) regionRefs.current.set(region.key, el);
                else regionRefs.current.delete(region.key);
              }}
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
