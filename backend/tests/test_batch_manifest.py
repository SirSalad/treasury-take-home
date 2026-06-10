"""Tests for CSV manifest parsing (app.batch.manifest)."""

import pytest

from app.batch.manifest import ManifestError, parse_manifest
from app.models import ProductSource, ProductType

HEADER = "image_filename,brand_name,source,product_type,alcohol_content_pct,net_contents"


def test_parses_a_clean_row_into_expected_fields() -> None:
    csv = f"{HEADER}\nold-tom.png,OLD TOM DISTILLERY,domestic,distilled_spirits,45.0,750 mL\n"
    [row] = parse_manifest(csv)

    assert row.ok
    assert row.row_number == 1
    assert row.image_filename == "old-tom.png"
    assert row.application is not None
    assert row.application.brand_name == "OLD TOM DISTILLERY"
    assert row.application.source is ProductSource.DOMESTIC
    assert row.application.product_type is ProductType.DISTILLED_SPIRITS
    assert float(row.application.alcohol_content_pct) == 45.0
    assert row.application.net_contents == "750 mL"


def test_optional_columns_default_when_blank() -> None:
    # source/product_type omitted entirely; ApplicationInput defaults apply.
    csv = "image_filename,brand_name\nlabel.png,Coastal Vines\n"
    [row] = parse_manifest(csv)

    assert row.ok
    assert row.application is not None
    assert row.application.source is ProductSource.DOMESTIC
    assert row.application.product_type is ProductType.DISTILLED_SPIRITS
    assert row.application.alcohol_content_pct is None


def test_blank_optional_value_is_treated_as_unset() -> None:
    csv = f"{HEADER}\nx.png,Brand,,,,\n"
    [row] = parse_manifest(csv)

    assert row.ok
    assert row.application is not None
    # Empty cells fall back to defaults / None rather than failing validation.
    assert row.application.source is ProductSource.DOMESTIC
    assert row.application.alcohol_content_pct is None
    assert row.application.net_contents is None


def test_header_whitespace_is_normalised() -> None:
    csv = " image_filename , brand_name \nx.png,Brand\n"
    [row] = parse_manifest(csv)
    assert row.ok
    assert row.image_filename == "x.png"


def test_unrecognised_columns_are_ignored() -> None:
    csv = "image_filename,brand_name,internal_ref\nx.png,Brand,ACME-123\n"
    [row] = parse_manifest(csv)
    assert row.ok
    assert row.application is not None
    assert row.application.brand_name == "Brand"


def test_bad_abv_is_a_per_row_error_not_a_raise() -> None:
    csv = f"{HEADER}\nx.png,Brand,domestic,wine,not-a-number,750 mL\n"
    [row] = parse_manifest(csv)

    assert not row.ok
    assert row.application is None
    assert any("alcohol_content_pct" in message for message in row.errors)


def test_out_of_range_abv_is_a_per_row_error() -> None:
    csv = f"{HEADER}\nx.png,Brand,domestic,wine,150,750 mL\n"
    [row] = parse_manifest(csv)
    assert not row.ok
    assert any("alcohol_content_pct" in message for message in row.errors)


def test_invalid_enum_value_is_a_per_row_error() -> None:
    csv = f"{HEADER}\nx.png,Brand,martian,wine,12,750 mL\n"
    [row] = parse_manifest(csv)
    assert not row.ok
    assert any("source" in message for message in row.errors)


def test_missing_brand_name_value_is_a_per_row_error() -> None:
    csv = f"{HEADER}\nx.png,,domestic,wine,12,750 mL\n"
    [row] = parse_manifest(csv)
    assert not row.ok
    assert any("brand_name" in message for message in row.errors)


def test_missing_image_filename_value_is_a_per_row_error() -> None:
    csv = f"{HEADER}\n,Brand,domestic,wine,12,750 mL\n"
    [row] = parse_manifest(csv)
    assert not row.ok
    assert any("image_filename" in message for message in row.errors)
    # The application fields themselves are still valid in this row.
    assert row.application is not None


def test_row_numbers_are_one_based_over_data_rows() -> None:
    csv = f"{HEADER}\na.png,A\nb.png,B\nc.png,C\n"
    rows = parse_manifest(csv)
    assert [r.row_number for r in rows] == [1, 2, 3]


def test_accepts_bytes_with_utf8_bom() -> None:
    csv = (f"{HEADER}\nx.png,Brand,domestic,wine,12,750 mL\n").encode("utf-8-sig")
    [row] = parse_manifest(csv)
    assert row.ok
    assert row.image_filename == "x.png"


def test_empty_content_raises_manifest_error() -> None:
    with pytest.raises(ManifestError):
        parse_manifest("")


def test_missing_required_column_raises_manifest_error() -> None:
    with pytest.raises(ManifestError, match="image_filename"):
        parse_manifest("brand_name\nBrand\n")


def test_header_only_raises_manifest_error() -> None:
    with pytest.raises(ManifestError, match="no data rows"):
        parse_manifest(f"{HEADER}\n")
