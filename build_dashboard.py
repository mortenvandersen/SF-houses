"""Build a self-contained dashboard.html from listings_with_distances.csv.

Reads the CSV (which may contain embedded newlines inside descriptions),
normalizes the rows, and inlines them as JSON into a single HTML file that
can be opened directly in a browser (no local server needed).

Re-run this script whenever listings_with_distances.csv changes.
"""

import csv
import json
import re
from pathlib import Path

INPUT_CSV = "listings_with_distances.csv"
TEMPLATE_HTML = "dashboard.template.html"
OUTPUT_HTML = "dashboard.html"

# Friend / work destination names, as declared in distance_matrix.py.
DESTINATIONS = [
    "Friend 1 (Cumberland)",
    "Friend 2 (Larkspur)",
    "Vic Work (Oyster Point)",
]
MODES = ["Drive", "Walk", "Transit"]

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


def load_rows() -> list[dict]:
    with open(INPUT_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cleaned: list[dict] = []
    for row in rows:
        out = dict(row)
        out["_priceValue"] = parse_price(row.get("Price", ""))
        out["_ppsfValue"] = parse_price(row.get("Price Per Sq. Ft.", ""))
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
