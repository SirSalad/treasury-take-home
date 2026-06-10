import { AlertCircle, ImageUp, X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

interface LabelUploadProps {
  /** The currently selected file, or null when none is chosen. */
  value: File | null;
  /** Called with the new file (or null when cleared). */
  onChange: (file: File | null) => void;
  /** Object URL of the selected image, for the thumbnail preview. */
  previewUrl: string | null;
  /** Validation message; presence flips the control into the error state. */
  error?: string;
  /** Disables interaction while a verification is in flight. */
  disabled?: boolean;
}

/** Human-readable file size, e.g. "412 KB". */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

/**
 * Accessible image picker for the label artwork — the "actual" side of the
 * comparison. Supports click-to-browse and drag-and-drop, shows a thumbnail
 * preview once a file is chosen, and surfaces validation errors with
 * `role="alert"`. Only the image is held client-side; it is uploaded on submit.
 */
export function LabelUpload({
  value,
  onChange,
  previewUrl,
  error,
  disabled = false,
}: LabelUploadProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = React.useState(false);
  const errorId = error ? "label-upload-error" : undefined;

  function handleFiles(files: FileList | null) {
    const file = files?.[0] ?? null;
    if (file && file.type.startsWith("image/")) {
      onChange(file);
    } else if (file) {
      // A non-image was dropped; reject it but keep any prior selection.
      onChange(null);
    }
  }

  function clear() {
    onChange(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="space-y-1.5">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="sr-only"
        aria-describedby={errorId}
        aria-invalid={Boolean(error)}
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />

      {value && previewUrl ? (
        <div
          className={cn(
            "flex items-center gap-4 rounded-md border bg-card p-3",
            error ? "border-destructive" : "border-input",
          )}
        >
          <img
            src={previewUrl}
            alt="Selected label preview"
            className="size-16 shrink-0 rounded object-cover"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-foreground">{value.name}</p>
            <p className="text-sm text-muted-foreground">{formatSize(value.size)}</p>
          </div>
          <button
            type="button"
            onClick={clear}
            disabled={disabled}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
          >
            <X className="size-4" aria-hidden="true" />
            Remove
            <span className="sr-only"> selected label image</span>
          </button>
        </div>
      ) : (
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
            if (!disabled) handleFiles(e.dataTransfer.files);
          }}
          disabled={disabled}
          className={cn(
            "flex w-full flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-6 py-10 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
            dragging && "border-primary bg-primary/5",
            error ? "border-destructive" : "border-input hover:border-primary hover:bg-muted/50",
          )}
        >
          <ImageUp className="size-8 text-muted-foreground" aria-hidden="true" />
          <span className="text-sm font-medium text-foreground">
            Drop the label image here, or <span className="text-primary underline">browse</span>
          </span>
          <span className="text-sm text-muted-foreground">PNG or JPEG, up to 20 MB</span>
        </button>
      )}

      {error && (
        <p
          id={errorId}
          role="alert"
          className="flex items-center gap-1 text-sm font-medium text-destructive"
        >
          <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}
