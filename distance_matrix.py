import csv
import os
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or "AIzaSyAnkSa_iZRgtY1ofYF_FAcgckAZD3Mqeqk"

TZ = ZoneInfo("America/Los_Angeles")

# weekday(): Mon=0 Tue=1 Wed=2 Thu=3 Fri=4 Sat=5 Sun=6
DESTINATIONS = {
    "Friend 1 (Cumberland)": {
        "address": "41 Cumberland St, San Francisco, CA 94110",
        "weekdays": [1],       # Tuesday
        "hour": 17,
        "minute": 0,
    },
    "Friend 2 (Larkspur)": {
        "address": "930 Larkspur Rd, Oakland, CA 94610",
        "weekdays": [5],       # Saturday
        "hour": 10,
        "minute": 0,
    },
    "Vic Work (Oyster Point)": {
        "address": "354 Oyster Point Blvd, South San Francisco, CA 94080",
        "weekdays": [0, 1, 2, 3, 4],  # Mon–Fri
        "hour": 6,
        "minute": 30,
    },
}

MODES = ["driving", "walking", "transit"]

MODE_LABEL = {
    "driving": "Drive",
    "walking": "Walk",
    "transit": "Transit",
}

SEARCHES_DIR = Path("searches")
OUTPUT_CSV = "listings_with_distances.csv"

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def next_departure_timestamp(weekdays: list[int], hour: int, minute: int) -> int:
    """Return Unix timestamp of the next upcoming weekday at the given local time."""
    now = datetime.now(TZ)
    candidates = []
    for wd in weekdays:
        days_ahead = wd - now.weekday()
        if days_ahead < 0 or (
            days_ahead == 0
            and (now.hour > hour or (now.hour == hour and now.minute >= minute))
        ):
            days_ahead += 7
        target = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        candidates.append(target)
    return int(min(candidates).timestamp())


def fetch_distances(
    origins: list[str],
    destinations: list[str],
    mode: str,
    departure_times: list[int] | None = None,
) -> dict:
    """
    Returns { origin: { destination: {"distance_km": float, "duration_min": float} } }
    departure_times is a per-destination list of Unix timestamps (ignored for walking).
    Batches origins in groups of 25 (API limit).
    """
    results = {o: {} for o in origins}

    for i in range(0, len(origins), 25):
        batch = origins[i : i + 25]

        # Each destination may have a different departure time, so query one dest at a time
        # when departure_times are set; otherwise batch all destinations together.
        if departure_times and mode != "walking":
            for col_idx, (dest, dep_ts) in enumerate(zip(destinations, departure_times)):
                params = {
                    "origins": "|".join(batch),
                    "destinations": dest,
                    "mode": mode,
                    "departure_time": dep_ts,
                    "key": GOOGLE_API_KEY,
                }
                if mode == "driving":
                    params["traffic_model"] = "best_guess"
                resp = requests.get(DISTANCE_MATRIX_URL, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data["status"] != "OK":
                    raise RuntimeError(f"API error ({mode}): {data['status']}")
                for row_idx, row in enumerate(data["rows"]):
                    origin = batch[row_idx]
                    element = row["elements"][0]
                    if element["status"] == "OK":
                        duration_key = (
                            "duration_in_traffic"
                            if mode == "driving" and "duration_in_traffic" in element
                            else "duration"
                        )
                        results[origin][dest] = {
                            "distance_km": round(element["distance"]["value"] / 1000, 2),
                            "duration_min": round(element[duration_key]["value"] / 60, 1),
                        }
                    else:
                        results[origin][dest] = {"distance_km": None, "duration_min": None}
                time.sleep(0.1)
        else:
            params = {
                "origins": "|".join(batch),
                "destinations": "|".join(destinations),
                "mode": mode,
                "key": GOOGLE_API_KEY,
            }
            resp = requests.get(DISTANCE_MATRIX_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data["status"] != "OK":
                raise RuntimeError(f"API error ({mode}): {data['status']}")
            for row_idx, row in enumerate(data["rows"]):
                origin = batch[row_idx]
                for col_idx, element in enumerate(row["elements"]):
                    dest = destinations[col_idx]
                    if element["status"] == "OK":
                        results[origin][dest] = {
                            "distance_km": round(element["distance"]["value"] / 1000, 2),
                            "duration_min": round(element["duration"]["value"] / 60, 1),
                        }
                    else:
                        results[origin][dest] = {"distance_km": None, "duration_min": None}

        if i + 25 < len(origins):
            time.sleep(0.2)

    return results


def load_search_rows() -> tuple[list[dict], list[str], list[str]]:
    """Read every CSV in searches/, dedupe by Listing URL (latest file wins).

    Returns (rows, fieldnames, filenames).
    """
    files = sorted(SEARCHES_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {SEARCHES_DIR}/")

    merged: dict[str, dict] = {}
    fieldnames: list[str] = []
    for path in files:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for fn in reader.fieldnames or []:
                if fn not in fieldnames:
                    fieldnames.append(fn)
            for row in reader:
                if not row.get("Address", "").strip():
                    continue
                key = row.get("Listing URL") or row.get("Address")
                if not key:
                    continue
                merged[key] = row  # later files overwrite earlier ones
    return list(merged.values()), fieldnames, [p.name for p in files]


def already_processed_addresses() -> set[str]:
    """Return addresses already present in the output CSV, or empty set if it doesn't exist."""
    try:
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            return {row["Address"] for row in csv.DictReader(f) if row.get("Address")}
    except FileNotFoundError:
        return set()


def main():
    all_rows, fieldnames, source_files = load_search_rows()

    done = already_processed_addresses()
    rows = [r for r in all_rows if r["Address"] not in done]

    print(f"Search files    : {len(source_files)}")
    for name in source_files:
        print(f"  - {name}")
    print(f"Unique listings : {len(all_rows)}")
    print(f"Already done    : {len(done)}")
    print(f"To process      : {len(rows)}")

    if not rows:
        print("Nothing new to process.")
        return

    origins = [row["Address"] for row in rows]
    dest_names = list(DESTINATIONS.keys())
    dest_addrs = [v["address"] for v in DESTINATIONS.values()]
    departure_times = [
        next_departure_timestamp(v["weekdays"], v["hour"], v["minute"])
        for v in DESTINATIONS.values()
    ]

    # Print the departure times being used
    for name, ts in zip(dest_names, departure_times):
        dt = datetime.fromtimestamp(ts, TZ)
        print(f"  {name}: {dt.strftime('%A %Y-%m-%d %H:%M %Z')}")

    all_results: dict[str, dict] = {}
    for mode in MODES:
        print(f"Fetching {MODE_LABEL[mode]} distances for {len(origins)} listings...")
        all_results[mode] = fetch_distances(origins, dest_addrs, mode, departure_times)

    extra_fields = []
    for dest_name in dest_names:
        for mode in MODES:
            extra_fields.append(f"{dest_name} - {MODE_LABEL[mode]} Distance (km)")
            extra_fields.append(f"{dest_name} - {MODE_LABEL[mode]} Time (min)")

    out_fields = fieldnames + extra_fields

    write_header = not done  # only write header when starting fresh
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        if write_header:
            writer.writeheader()
        for row in rows:
            address = row["Address"]
            for dest_name, dest_addr in zip(dest_names, dest_addrs):
                for mode in MODES:
                    info = all_results[mode].get(address, {}).get(dest_addr, {})
                    row[f"{dest_name} - {MODE_LABEL[mode]} Distance (km)"] = info.get("distance_km", "N/A")
                    row[f"{dest_name} - {MODE_LABEL[mode]} Time (min)"] = info.get("duration_min", "N/A")
            writer.writerow(row)

    print(f"Done. Results written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
