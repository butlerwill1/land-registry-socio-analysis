"""Pure postcode parsing and London classification helpers."""

from __future__ import annotations

import re


UNKNOWN_POSTCODE_PART = "Unknown"
OUTWARD_CODE_PATTERN = re.compile(r"^([A-Z]{1,2})(\d[A-Z0-9]?)$")
CENTRAL_DISTRICT_PATTERN = re.compile(
    r"^(?:W1|SW1|NW1|SE1|E1|N1)[A-Z]?$"
)

CENTRAL_LONDON_AREAS = frozenset({"EC", "WC"})
GREATER_LONDON_AREAS = frozenset(
    {
        "BR",
        "CR",
        "DA",
        "E",
        "EC",
        "EN",
        "HA",
        "IG",
        "KT",
        "N",
        "NW",
        "RM",
        "SE",
        "SM",
        "SW",
        "TW",
        "UB",
        "W",
        "WC",
        "WD",
    }
)


def split_postcode(postcode: str | None) -> tuple[str, str, str]:
    """Return the area, outward district, and sector for a UK postcode."""
    if postcode is None:
        return (UNKNOWN_POSTCODE_PART,) * 3

    parts = str(postcode).strip().upper().split()
    if not parts:
        return (UNKNOWN_POSTCODE_PART,) * 3

    outward_match = OUTWARD_CODE_PATTERN.fullmatch(parts[0])
    if outward_match is None:
        return (UNKNOWN_POSTCODE_PART,) * 3

    area = outward_match.group(1)
    district = parts[0]
    sector = UNKNOWN_POSTCODE_PART
    if len(parts) > 1 and re.fullmatch(r"\d[A-Z]{2}", parts[1]):
        sector = f"{district}-{parts[1][0]}"

    return area, district, sector


def classify_london_postcode(
    area_code: str | None,
    district_code: str | None,
) -> str:
    """Classify a postcode as Central London, Greater London, or outside."""
    if area_code is None or district_code is None:
        return "Unknown"

    area = str(area_code).strip().upper()
    district = str(district_code).strip().upper()
    if area == UNKNOWN_POSTCODE_PART.upper() or district == UNKNOWN_POSTCODE_PART.upper():
        return "Unknown"

    if area in CENTRAL_LONDON_AREAS or CENTRAL_DISTRICT_PATTERN.fullmatch(district):
        return "Central London"
    if area in GREATER_LONDON_AREAS:
        return "Greater London"
    return "Outside London"
