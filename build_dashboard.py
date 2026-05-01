"""Build a self-contained dashboard.html from listings_with_distances.csv.

Reads the CSV (which may contain embedded newlines inside descriptions),
normalizes the rows, and inlines them as JSON into a single HTML file that
can be opened directly in a browser (no local server needed).

Re-run this script whenever listings_with_distances.csv changes.
"""

import csv
import json
import re
from datetime import date, timedelta
from pathlib import Path

INPUT_CSV = "listings_with_distances.csv"
TEMPLATE_HTML = "dashboard.template.html"
OUTPUT_HTML = "index.html"

# Friend / work destination names, as declared in distance_matrix.py.
DESTINATIONS = [
    "Friend 1 (Cumberland)",
    "Friend 2 (Larkspur)",
    "Vic Work (Oyster Point)",
]
MODES = ["Drive", "Walk", "Transit"]

REGIONS = ["San Francisco", "Hillsborough area", "Oakland"]

REGION_BY_COUNTY = {
    "san francisco county": "San Francisco",
    "san mateo county": "Hillsborough area",
    "alameda county": "Oakland",
    "contra costa county": "Oakland",
}

REGION_BY_CITY = {
    "san francisco": "San Francisco",
    "hillsborough": "Hillsborough area",
    "burlingame": "Hillsborough area",
    "san mateo": "Hillsborough area",
    "millbrae": "Hillsborough area",
    "belmont": "Hillsborough area",
    "foster city": "Hillsborough area",
    "san bruno": "Hillsborough area",
    "south san francisco": "Hillsborough area",
    "redwood city": "Hillsborough area",
    "san carlos": "Hillsborough area",
    "daly city": "Hillsborough area",
    "brisbane": "Hillsborough area",
    "pacifica": "Hillsborough area",
    "oakland": "Oakland",
    "berkeley": "Oakland",
    "piedmont": "Oakland",
    "emeryville": "Oakland",
    "alameda": "Oakland",
    "albany": "Oakland",
    "el cerrito": "Oakland",
    "san leandro": "Oakland",
}


def assign_region(row: dict) -> str:
    county = (row.get("County") or "").strip().lower()
    if county in REGION_BY_COUNTY:
        return REGION_BY_COUNTY[county]
    city = (row.get("City") or "").strip().lower()
    if city in REGION_BY_CITY:
        return REGION_BY_CITY[city]
    return "Other"


NUMERIC_FIELDS = {
    "Beds",
    "Baths",
    "Footage",
    "Latitude",
    "Longitude",
    "Lowest Rent",
    "Highest Rent",
    "Year Built (Premium Data)",
    "Walk Score (Premium Data)",
    "Transit Score (Premium Data)",
    "Bike Score (Premium Data)",
    "Elementary School Rating (Premium Data)",
    "Middle School Rating (Premium Data)",
    "High School Rating (Premium Data)",
    "Days on Zillow",
}

# Also treat all the commute distance/time columns as numeric.
for _d in DESTINATIONS:
    for _m in MODES:
        NUMERIC_FIELDS.add(f"{_d} - {_m} Distance (km)")
        NUMERIC_FIELDS.add(f"{_d} - {_m} Time (min)")


def parse_price(raw: str) -> float | None:
    """Turn '$8,500' or '$7.09' into a float; return None if unparseable."""
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.]", "", raw)
    if not cleaned or cleaned == ".":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_number(raw: str) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_iso_date(raw: str) -> str | None:
    """Extract an ISO YYYY-MM-DD date from values like 'Thu, 2026-04-16'."""
    if not raw:
        return None
    m = ISO_DATE_RE.search(raw)
    return m.group(0) if m else None


def parse_days_on_zillow(raw: str) -> int | None:
    """Parse 'Days on Zillow' values like '5', '0', or '12 hours' into days."""
    if not raw:
        return None
    s = raw.strip().lower()
    if "hour" in s:
        return 0
    m = re.match(r"\d+", s)
    return int(m.group(0)) if m else None


def listed_date_from(scraped_iso: str | None, days_on_zillow: int | None) -> str | None:
    if not scraped_iso or days_on_zillow is None:
        return None
    try:
        d = date.fromisoformat(scraped_iso) - timedelta(days=days_on_zillow)
    except ValueError:
        return None
    return d.isoformat()


def load_rows() -> list[dict]:
    with open(INPUT_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cleaned: list[dict] = []
    for row in rows:
        out = dict(row)
        out["_priceValue"] = parse_price(row.get("Price", ""))
        out["_ppsfValue"] = parse_price(row.get("Price Per Sq. Ft.", ""))
        out["_region"] = assign_region(row)
        scraped = parse_iso_date(row.get("Date Scraped", ""))
        days = parse_days_on_zillow(row.get("Days on Zillow", ""))
        listed = listed_date_from(scraped, days)
        out["_scrapedDate"] = scraped
        out["_listedDate"] = listed
        out["_sortDate"] = listed or scraped
        for field in NUMERIC_FIELDS:
            if field in out:
                out[f"_num:{field}"] = parse_number(out[field])
        cleaned.append(out)
    return cleaned


def main() -> None:
    rows = load_rows()
    # Escape "</" so embedded descriptions cannot accidentally close the <script> tag.
    data_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    meta = {
        "destinations": DESTINATIONS,
        "modes": MODES,
        "count": len(rows),
        "source": INPUT_CSV,
        "regions": REGIONS,
    }
    meta_json = json.dumps(meta, ensure_ascii=False)

    template = Path(TEMPLATE_HTML).read_text(encoding="utf-8")
    html = template.replace(
        "/*__DATA_PLACEHOLDER__*/null", data_json
    ).replace(
        "/*__META_PLACEHOLDER__*/null", meta_json
    )
    Path(OUTPUT_HTML).write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_HTML} with {len(rows)} listings.")


if __name__ == "__main__":
    main()
