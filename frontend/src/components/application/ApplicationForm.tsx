import * as React from "react";

import { Field } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  EMPTY_APPLICATION_FORM,
  PRODUCT_SOURCE_OPTIONS,
  PRODUCT_TYPE_OPTIONS,
  type ApplicationForm as ApplicationFormData,
} from "@/lib/application";
import { isWine, validateApplication, type ApplicationErrors } from "@/lib/application-validation";

interface ApplicationFormProps {
  /** Pre-fill the form (e.g. when editing). Defaults to an empty application. */
  initialValue?: ApplicationFormData;
  /** Called with the validated form data once the user submits successfully. */
  onSubmit: (form: ApplicationFormData) => void;
  /** Disables the form while a submission is in flight. */
  isSubmitting?: boolean;
  /** Text for the submit button. */
  submitLabel?: string;
}

/** Order errors appear in the summary, matching the visual field order. */
const FIELD_ORDER: Array<keyof ApplicationFormData> = [
  "source",
  "productType",
  "brandName",
  "alcoholContentPct",
  "countryOfOrigin",
  "vintage",
];

/**
 * Accessible entry form for a TTB COLA application (Form 5100.31 / OMB
 * 1513-0020) — the "expected" side of the label comparison. Validates before
 * submit and surfaces problems both inline and in a focusable error summary at
 * the top, so keyboard and screen-reader users are taken straight to what needs
 * fixing (WCAG 3.3.1 / 3.3.3).
 */
export function ApplicationForm({
  initialValue = EMPTY_APPLICATION_FORM,
  onSubmit,
  isSubmitting = false,
  submitLabel = "Verify label",
}: ApplicationFormProps) {
  const [form, setForm] = React.useState<ApplicationFormData>(initialValue);
  const [errors, setErrors] = React.useState<ApplicationErrors>({});
  const summaryRef = React.useRef<HTMLDivElement>(null);

  function update<K extends keyof ApplicationFormData>(key: K, value: ApplicationFormData[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validateApplication(form);
    setErrors(found);

    if (Object.keys(found).length > 0) {
      // Move focus to the summary so assistive tech announces the problems.
      requestAnimationFrame(() => summaryRef.current?.focus());
      return;
    }
    onSubmit(form);
  }

  const errorEntries = FIELD_ORDER.filter((key) => errors[key]).map((key) => ({
    key,
    message: errors[key] as string,
  }));

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-8">
      {errorEntries.length > 0 && (
        <div
          ref={summaryRef}
          tabIndex={-1}
          role="alert"
          className="rounded-md border border-destructive bg-mismatch-muted p-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <h3 className="font-bold text-destructive">
            Please fix {errorEntries.length} {errorEntries.length === 1 ? "field" : "fields"} before
            continuing
          </h3>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
            {errorEntries.map(({ key, message }) => (
              <li key={key}>
                <a className="font-medium text-destructive underline" href={`#${key}`}>
                  {message}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <fieldset className="space-y-5" disabled={isSubmitting}>
        <legend className="text-lg font-bold text-foreground">Product</legend>

        <Field
          id="source"
          label="Source"
          help="Where the product is made. Imported products must list a country of origin."
          error={errors.source}
          required
        >
          {({ id, describedBy, invalid }) => (
            <Select
              id={id}
              value={form.source}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(e) => update("source", e.target.value as ApplicationFormData["source"])}
            >
              <option value="">Select one…</option>
              {PRODUCT_SOURCE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field
          id="productType"
          label="Product type"
          help="The class of beverage. Wine adds appellation and vintage fields."
          error={errors.productType}
          required
        >
          {({ id, describedBy, invalid }) => (
            <Select
              id={id}
              value={form.productType}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(e) =>
                update("productType", e.target.value as ApplicationFormData["productType"])
              }
            >
              <option value="">Select one…</option>
              {PRODUCT_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field
            id="serialNumber"
            label="TTB serial number"
            help="Optional. From block 5 of the form, e.g. 24-001."
          >
            {({ id, describedBy }) => (
              <Input
                id={id}
                value={form.serialNumber}
                aria-describedby={describedBy}
                onChange={(e) => update("serialNumber", e.target.value)}
              />
            )}
          </Field>

          <Field
            id="plantRegistryNumber"
            label="Plant registry / basic permit number"
            help="Optional. The producer's TTB-issued number."
          >
            {({ id, describedBy }) => (
              <Input
                id={id}
                value={form.plantRegistryNumber}
                aria-describedby={describedBy}
                onChange={(e) => update("plantRegistryNumber", e.target.value)}
              />
            )}
          </Field>
        </div>
      </fieldset>

      <fieldset className="space-y-5" disabled={isSubmitting}>
        <legend className="text-lg font-bold text-foreground">Label content</legend>
        <p className="text-sm text-muted-foreground">
          Enter these exactly as they appear on the application. The app compares them against the
          uploaded label artwork.
        </p>

        <Field
          id="brandName"
          label="Brand name"
          help='The primary brand, e.g. "Old Tom Distillery".'
          error={errors.brandName}
          required
        >
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              value={form.brandName}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(e) => update("brandName", e.target.value)}
            />
          )}
        </Field>

        <Field
          id="fancifulName"
          label="Fanciful name"
          help='Optional. A product name distinct from the brand, e.g. "Midnight Reserve".'
        >
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={form.fancifulName}
              aria-describedby={describedBy}
              onChange={(e) => update("fancifulName", e.target.value)}
            />
          )}
        </Field>

        <Field
          id="classType"
          label="Class / type designation"
          help='e.g. "Kentucky Straight Bourbon Whiskey".'
        >
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={form.classType}
              aria-describedby={describedBy}
              onChange={(e) => update("classType", e.target.value)}
            />
          )}
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field
            id="alcoholContentPct"
            label="Alcohol content (% ABV)"
            help="Optional. A number between 0 and 100, e.g. 45."
            error={errors.alcoholContentPct}
          >
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                type="number"
                inputMode="decimal"
                min={0}
                max={100}
                step="0.1"
                value={form.alcoholContentPct}
                aria-describedby={describedBy}
                aria-invalid={invalid}
                onChange={(e) => update("alcoholContentPct", e.target.value)}
              />
            )}
          </Field>

          <Field id="netContents" label="Net contents" help='e.g. "750 mL".'>
            {({ id, describedBy }) => (
              <Input
                id={id}
                value={form.netContents}
                aria-describedby={describedBy}
                onChange={(e) => update("netContents", e.target.value)}
              />
            )}
          </Field>
        </div>

        <Field
          id="alcoholContentText"
          label="Alcohol statement as printed"
          help='Optional. The full statement exactly as on the label, e.g. "45% Alc./Vol. (90 Proof)".'
        >
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={form.alcoholContentText}
              aria-describedby={describedBy}
              onChange={(e) => update("alcoholContentText", e.target.value)}
            />
          )}
        </Field>
      </fieldset>

      <fieldset className="space-y-5" disabled={isSubmitting}>
        <legend className="text-lg font-bold text-foreground">
          Responsible party &amp; origin
        </legend>

        <Field
          id="nameAndAddress"
          label="Name and address of bottler / producer / importer"
          help="The responsible party shown on the label."
        >
          {({ id, describedBy }) => (
            <Textarea
              id={id}
              rows={3}
              value={form.nameAndAddress}
              aria-describedby={describedBy}
              onChange={(e) => update("nameAndAddress", e.target.value)}
            />
          )}
        </Field>

        <Field
          id="countryOfOrigin"
          label="Country of origin"
          help={
            form.source === "imported"
              ? "Required for imported products."
              : "Required only for imported products."
          }
          error={errors.countryOfOrigin}
          required={form.source === "imported"}
        >
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              value={form.countryOfOrigin}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(e) => update("countryOfOrigin", e.target.value)}
            />
          )}
        </Field>
      </fieldset>

      {isWine(form.productType) && (
        <fieldset className="space-y-5" disabled={isSubmitting}>
          <legend className="text-lg font-bold text-foreground">Wine details</legend>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field
              id="appellation"
              label="Appellation"
              help={'Optional. The wine’s region of origin, e.g. "Napa Valley".'}
            >
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  value={form.appellation}
                  aria-describedby={describedBy}
                  onChange={(e) => update("appellation", e.target.value)}
                />
              )}
            </Field>

            <Field
              id="vintage"
              label="Vintage"
              help="Optional. The 4-digit harvest year, e.g. 2021."
              error={errors.vintage}
            >
              {({ id, describedBy, invalid }) => (
                <Input
                  id={id}
                  inputMode="numeric"
                  value={form.vintage}
                  aria-describedby={describedBy}
                  aria-invalid={invalid}
                  onChange={(e) => update("vintage", e.target.value)}
                />
              )}
            </Field>
          </div>
        </fieldset>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" size="lg" disabled={isSubmitting}>
          {isSubmitting ? "Verifying…" : submitLabel}
        </Button>
        <span className="text-sm text-muted-foreground">
          <span aria-hidden="true" className="text-destructive">
            *
          </span>{" "}
          indicates a required field
        </span>
      </div>
    </form>
  );
}
