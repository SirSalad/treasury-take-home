"""The label test corpus: source of truth for cases and golden verdicts.

Each entry pairs an *expected* COLA application with the text *printed* on a
synthetic label image and the *golden* verdict the verification engine should
return. The generator (:mod:`generate`) renders the images and writes
``manifest.json`` from this list; the tests load the manifest and assert the
engine reproduces these verdicts.

The set is deliberately small but spans the verdict space called out in the
discovery interviews:

* a clean distilled-spirits pass (the brief's OLD TOM DISTILLERY example);
* a clean imported-wine pass (a second product type + import fields);
* a case-only brand difference -> soft warning (Dave's "STONE'S THROW");
* an ABV mismatch -> hard fail (the most common data-entry error);
* a title-case government warning -> altered/fail (Jenny's real catch);
* a missing government warning -> fail.
"""

from __future__ import annotations

from .schema import (
    GOVERNMENT_WARNING_TEXT,
    CorpusCase,
    FieldVerdict,
    Golden,
    Manifest,
    OverallVerdict,
    WarningVerdict,
)

MANIFEST_VERSION = 1


CASES: list[CorpusCase] = [
    CorpusCase(
        id="old_tom_clean_pass",
        title="OLD TOM DISTILLERY — clean pass",
        description=(
            "The brief's example distilled-spirits label. Every field on the "
            "label matches the application and the government warning is exact, "
            "so the engine should return a clean pass."
        ),
        image="images/old_tom_clean_pass.png",
        application={
            "serial_number": "24-001",
            "source": "domestic",
            "product_type": "distilled_spirits",
            "brand_name": "OLD TOM DISTILLERY",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content_pct": 45.0,
            "alcohol_content_text": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "name_and_address": "Bottled by Old Tom Distillery, Bardstown, KY",
        },
        label={
            "brand_name": "OLD TOM DISTILLERY",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content_text": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "name_and_address": "Bottled by Old Tom Distillery, Bardstown, KY",
            "government_warning": GOVERNMENT_WARNING_TEXT,
        },
        golden=Golden(
            overall=OverallVerdict.PASS,
            fields={
                "brand_name": FieldVerdict.MATCH,
                "class_type": FieldVerdict.MATCH,
                "alcohol_content": FieldVerdict.MATCH,
                "net_contents": FieldVerdict.MATCH,
                "name_and_address": FieldVerdict.MATCH,
            },
            government_warning=WarningVerdict.COMPLIANT,
            rationale="All fields match and the warning is verbatim and all-caps.",
        ),
    ),
    CorpusCase(
        id="coastal_vines_wine_pass",
        title="COASTAL VINES — imported wine, clean pass",
        description=(
            "A second product type (wine) and source (imported) so the corpus "
            "exercises vintage, appellation, and country-of-origin fields. "
            "Everything matches; clean pass."
        ),
        image="images/coastal_vines_wine_pass.png",
        application={
            "serial_number": "24-118",
            "source": "imported",
            "product_type": "wine",
            "brand_name": "COASTAL VINES",
            "class_type": "Cabernet Sauvignon",
            "alcohol_content_pct": 13.5,
            "alcohol_content_text": "13.5% Alc./Vol.",
            "net_contents": "750 mL",
            "vintage": "2021",
            "country_of_origin": "Product of France",
            "name_and_address": "Imported by Coastal Vines Selections, New York, NY",
        },
        label={
            "brand_name": "COASTAL VINES",
            "class_type": "Cabernet Sauvignon",
            "alcohol_content_text": "13.5% Alc./Vol.",
            "net_contents": "750 mL",
            "vintage": "2021",
            "country_of_origin": "Product of France",
            "name_and_address": "Imported by Coastal Vines Selections, New York, NY",
            "government_warning": GOVERNMENT_WARNING_TEXT,
        },
        golden=Golden(
            overall=OverallVerdict.PASS,
            fields={
                "brand_name": FieldVerdict.MATCH,
                "class_type": FieldVerdict.MATCH,
                "alcohol_content": FieldVerdict.MATCH,
                "net_contents": FieldVerdict.MATCH,
                "vintage": FieldVerdict.MATCH,
                "country_of_origin": FieldVerdict.MATCH,
                "name_and_address": FieldVerdict.MATCH,
            },
            government_warning=WarningVerdict.COMPLIANT,
            rationale="All wine fields match and the warning is compliant.",
        ),
    ),
    CorpusCase(
        id="stones_throw_case_diff",
        title="STONE'S THROW — case-only brand difference (soft warning)",
        description=(
            "Dave's nuance: the label reads 'STONE'S THROW' in all caps while "
            "the application has 'Stone's Throw'. Obviously the same brand, so "
            "this is a soft warning, not a hard mismatch."
        ),
        image="images/stones_throw_case_diff.png",
        application={
            "serial_number": "24-203",
            "source": "domestic",
            "product_type": "distilled_spirits",
            "brand_name": "Stone's Throw",
            "class_type": "London Dry Gin",
            "alcohol_content_pct": 40.0,
            "alcohol_content_text": "40% Alc./Vol. (80 Proof)",
            "net_contents": "750 mL",
            "name_and_address": "Distilled by Stone's Throw Spirits, Portland, OR",
        },
        label={
            "brand_name": "STONE'S THROW",
            "class_type": "London Dry Gin",
            "alcohol_content_text": "40% Alc./Vol. (80 Proof)",
            "net_contents": "750 mL",
            "name_and_address": "Distilled by Stone's Throw Spirits, Portland, OR",
            "government_warning": GOVERNMENT_WARNING_TEXT,
        },
        golden=Golden(
            overall=OverallVerdict.WARNING,
            fields={
                "brand_name": FieldVerdict.SOFT_WARNING,
                "class_type": FieldVerdict.MATCH,
                "alcohol_content": FieldVerdict.MATCH,
                "net_contents": FieldVerdict.MATCH,
                "name_and_address": FieldVerdict.MATCH,
            },
            government_warning=WarningVerdict.COMPLIANT,
            rationale=(
                "Brand differs only by letter case; flag as a soft warning for a "
                "human glance rather than failing the label."
            ),
        ),
    ),
    CorpusCase(
        id="abv_mismatch",
        title="Silver Creek — ABV mismatch (fail)",
        description=(
            "The most common data-entry error: the application says 45% but the "
            "label prints 40%. A genuine numeric mismatch the agent must catch."
        ),
        image="images/abv_mismatch.png",
        application={
            "serial_number": "24-077",
            "source": "domestic",
            "product_type": "distilled_spirits",
            "brand_name": "SILVER CREEK",
            "class_type": "Tennessee Whiskey",
            "alcohol_content_pct": 45.0,
            "alcohol_content_text": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "name_and_address": "Bottled by Silver Creek Distillers, Lynchburg, TN",
        },
        label={
            "brand_name": "SILVER CREEK",
            "class_type": "Tennessee Whiskey",
            # Printed ABV disagrees with the application on purpose.
            "alcohol_content_text": "40% Alc./Vol. (80 Proof)",
            "net_contents": "750 mL",
            "name_and_address": "Bottled by Silver Creek Distillers, Lynchburg, TN",
            "government_warning": GOVERNMENT_WARNING_TEXT,
        },
        golden=Golden(
            overall=OverallVerdict.FAIL,
            fields={
                "brand_name": FieldVerdict.MATCH,
                "class_type": FieldVerdict.MATCH,
                "alcohol_content": FieldVerdict.MISMATCH,
                "net_contents": FieldVerdict.MATCH,
                "name_and_address": FieldVerdict.MATCH,
            },
            government_warning=WarningVerdict.COMPLIANT,
            rationale="Label ABV (40%) does not match the application (45%).",
        ),
    ),
    CorpusCase(
        id="altered_warning_titlecase",
        title="Highland Mist — title-case government warning (fail)",
        description=(
            "Jenny's catch: every field matches, but the warning reads "
            "'Government Warning:' in title case instead of the required all-caps "
            "'GOVERNMENT WARNING:'. The exact-match warning path must fail it."
        ),
        image="images/altered_warning_titlecase.png",
        application={
            "serial_number": "24-149",
            "source": "domestic",
            "product_type": "malt_beverage",
            "brand_name": "HIGHLAND MIST",
            "class_type": "India Pale Ale",
            "alcohol_content_pct": 6.5,
            "alcohol_content_text": "6.5% Alc./Vol.",
            "net_contents": "12 FL OZ",
            "name_and_address": "Brewed by Highland Mist Brewing, Asheville, NC",
        },
        label={
            "brand_name": "HIGHLAND MIST",
            "class_type": "India Pale Ale",
            "alcohol_content_text": "6.5% Alc./Vol.",
            "net_contents": "12 FL OZ",
            "name_and_address": "Brewed by Highland Mist Brewing, Asheville, NC",
            # 'GOVERNMENT WARNING:' downgraded to title case — non-compliant.
            "government_warning": GOVERNMENT_WARNING_TEXT.replace(
                "GOVERNMENT WARNING:", "Government Warning:"
            ),
        },
        golden=Golden(
            overall=OverallVerdict.FAIL,
            fields={
                "brand_name": FieldVerdict.MATCH,
                "class_type": FieldVerdict.MATCH,
                "alcohol_content": FieldVerdict.MATCH,
                "net_contents": FieldVerdict.MATCH,
                "name_and_address": FieldVerdict.MATCH,
            },
            government_warning=WarningVerdict.ALTERED,
            rationale=(
                "'GOVERNMENT WARNING:' must be all caps; title case is a "
                "non-compliant alteration regardless of other fields matching."
            ),
        ),
    ),
    CorpusCase(
        id="missing_warning",
        title="Cedar Ridge — missing government warning (fail)",
        description=(
            "Fields match but the mandatory government warning is absent from the "
            "label entirely. The warning is required on all alcohol beverages, so "
            "this fails."
        ),
        image="images/missing_warning.png",
        application={
            "serial_number": "24-256",
            "source": "domestic",
            "product_type": "wine",
            "brand_name": "CEDAR RIDGE",
            "class_type": "Chardonnay",
            "alcohol_content_pct": 12.5,
            "alcohol_content_text": "12.5% Alc./Vol.",
            "net_contents": "750 mL",
            "vintage": "2022",
            "name_and_address": "Produced and bottled by Cedar Ridge Vineyards, Sonoma, CA",
        },
        label={
            "brand_name": "CEDAR RIDGE",
            "class_type": "Chardonnay",
            "alcohol_content_text": "12.5% Alc./Vol.",
            "net_contents": "750 mL",
            "vintage": "2022",
            "name_and_address": "Produced and bottled by Cedar Ridge Vineyards, Sonoma, CA",
            # No government_warning key: nothing is printed.
            "government_warning": None,
        },
        golden=Golden(
            overall=OverallVerdict.FAIL,
            fields={
                "brand_name": FieldVerdict.MATCH,
                "class_type": FieldVerdict.MATCH,
                "alcohol_content": FieldVerdict.MATCH,
                "net_contents": FieldVerdict.MATCH,
                "vintage": FieldVerdict.MATCH,
                "name_and_address": FieldVerdict.MATCH,
            },
            government_warning=WarningVerdict.MISSING,
            rationale="The mandatory government health warning is absent.",
        ),
    ),
]


def build_manifest() -> Manifest:
    """Assemble the in-memory manifest from :data:`CASES`."""
    return Manifest(version=MANIFEST_VERSION, cases=CASES)
