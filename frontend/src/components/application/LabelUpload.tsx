import { AlertCircle, ImageUp, X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

interface LabelUploadProps {
  /** The selected label images, in display order (front, back, …). */
  value: File[];
  /** Called with the new file list whenever images are added or removed. */
  onChange: (files: File[]) => void;
  /** Validation message; presence flips the control into the error state. */
  error?: string;
  /** Disables interaction while a verification is in flight. */
  disabled?: boolean;
}

/** Largest label image we accept, mirroring the "up to 20 MB" hint. */
const MAX_BYTES = 20 * 1024 * 1024;

/** Most images per filing, mirroring the backend's cap. */
const MAX_FILES = 6;

/** Position hints mirroring how COLA filings order their label attachments. */
const POSITION_HINTS = ["front", "back", "neck", "other", "other", "other"];

/** Human-readable file size, e.g. "412 KB". */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

/** Validate a picked file against the advertised constraints. */
function rejectionReason(file: File): string | null {
  if (!file.type.startsWith("image/")) {
    return `“${file.name}” isn’t an image. Upload a PNG or JPEG of the label.`;
  }
  if (file.size > MAX_BYTES) {
    return `“${file.name}” is ${formatSize(file.size)}, over the 20 MB limit. Try a smaller file.`;
  }
  return null;
}

/** A thumbnail object URL per file, revoked when the file leaves the list. */
function usePreviews(files: File[]): string[] {
  const [urls, setUrls] = React.useState<string[]>([]);
  React.useEffect(() => {
    const next = files.map((file) => URL.createObjectURL(file));
    setUrls(next);
    return () => next.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);
  return urls;
}

/**
 * Accessible image picker for the filing's label set — the "actual" side of
 * the comparison. A COLA carries several label images (front, back, neck) and
 * the mandatory content is split across them, so the picker accepts up to
 * {@link MAX_FILES} images: click-to-browse or drag-and-drop (multi-select),
 * each listed with a thumbnail, its position in the set, and a remove button.
 * Only the images are held client-side; they upload on submit.
 */
export function LabelUpload({ value, onChange, error, disabled = false }: LabelUploadProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = React.useState(false);
  // Client-side validation message (wrong type / too big). The parent's `error`
  // prop (e.g. "attach an image before submitting") takes precedence over it.
  const [localError, setLocalError] = React.useState<string | undefined>();
  const previews = usePreviews(value);
  const shownError = error ?? localError;
  const errorId = shownError ? "label-upload-error" : undefined;

  function addFiles(files: FileList | null) {
    const picked = Array.from(files ?? []);
    if (!picked.length) return;
    for (const file of picked) {
      const reason = rejectionReason(file);
      if (reason) {
        // Reject the bad file and explain why, rather than silently ignoring it.
        setLocalError(reason);
        if (inputRef.current) inputRef.current.value = "";
        return;
      }
    }
    const next = [...value, ...picked];
    if (next.length > MAX_FILES) {
      setLocalError(`A filing can carry at most ${MAX_FILES} label images.`);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setLocalError(undefined);
    onChange(next);
    if (inputRef.current) inputRef.current.value = "";
  }

  function removeAt(index: number) {
    setLocalError(undefined);
    onChange(value.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-1.5">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="sr-only"
        aria-label="Upload label artwork (PNG or JPEG, up to 20 MB each)"
        aria-describedby={errorId}
        aria-invalid={Boolean(shownError)}
        disabled={disabled}
        onChange={(e) => addFiles(e.target.files)}
      />

      {value.length > 0 && (
        <ul className="space-y-2">
          {value.map((file, index) => (
            <li
              key={`${file.name}-${index}`}
              className={cn(
                "flex items-center gap-4 rounded-md border bg-card p-3",
                shownError ? "border-destructive" : "border-input",
              )}
            >
              {previews[index] && (
                <img
                  src={previews[index]}
                  alt={`Label image ${index + 1} preview`}
                  className="size-16 shrink-0 rounded object-cover"
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{file.name}</p>
                <p className="text-sm text-muted-foreground">
                  Image {index + 1} ({POSITION_HINTS[index]}) · {formatSize(file.size)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => removeAt(index)}
                disabled={disabled}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
              >
                <X className="size-4" aria-hidden="true" />
                Remove
                <span className="sr-only"> label image {index + 1}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {value.length < MAX_FILES && (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!disabled) addFiles(e.dataTransfer.files);
          }}
          disabled={disabled}
          className={cn(
            "flex w-full flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-6 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
            value.length ? "py-4" : "py-10",
            dragging && "border-primary bg-primary/5",
            shownError
              ? "border-destructive"
              : "border-input hover:border-primary hover:bg-muted/50",
          )}
        >
          <ImageUp className="size-8 text-muted-foreground" aria-hidden="true" />
          <span className="text-sm font-medium text-foreground">
            {value.length
              ? "Add another label image (back, neck, …), or "
              : "Drop the label images here (front, back, …), or "}
            <span className="text-primary underline">browse</span>
          </span>
          <span className="text-sm text-muted-foreground">
            PNG or JPEG, up to 20 MB each · up to {MAX_FILES} images per filing
          </span>
        </button>
      )}

      {shownError && (
        <p
          id={errorId}
          role="alert"
          className="flex items-center gap-1 text-sm font-medium text-destructive"
        >
          <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
          {shownError}
        </p>
      )}
    </div>
  );
}
