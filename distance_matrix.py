import csv
import time
import requests

GOOGLE_API_KEY = "AIzaSyAnkSa_iZRgtY1ofYF_FAcgckAZD3Mqeqk"

DESTINATIONS = {
    "Friend 1 (Cumberland)": "41 Cumberland St, San Francisco, CA 94110",
    "Friend 2 (Larkspur)": "930 Larkspur Rd, Oakland, CA 94610",
    "Vic Work (Oyster Point)": "354 Oyster Point Blvd, South San Francisco, CA 94080",
}

MODES = ["driving", "walking", "transit"]

MODE_LABEL = {
    "driving": "Drive",
    "walking": "Walk",
    "transit": "Transit",
}

INPUT_CSV = "listings.csv"
OUTPUT_CSV = "listings_with_distances.csv"

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def fetch_distances(origins: list[str], destinations: list[str], mode: str) -> dict:
    """
    Returns { origin: { destination: {"distance_km": float, "duration_min": float} } }
    Batches origins in groups of 25 (API limit).
    """
    results = {o: {} for o in origins}

    for i in range(0, len(origins), 25):
        batch = origins[i : i + 25]
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
            raise RuntimeError(f"Distance Matrix API error ({mode}): {data['status']}")

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


def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    origins = [row["Address"] for row in rows]
    dest_names = list(DESTINATIONS.keys())
    dest_addrs = list(DESTINATIONS.values())

    # Collect results per mode
    all_results: dict[str, dict] = {}
    for mode in MODES:
        print(f"Fetching {MODE_LABEL[mode]} distances for {len(origins)} listings...")
        all_results[mode] = fetch_distances(origins, dest_addrs, mode)

    # Build extra column names: grouped by destination, then mode
    extra_fields = []
    for dest_name in dest_names:
        for mode in MODES:
            extra_fields.append(f"{dest_name} - {MODE_LABEL[mode]} Distance (km)")
            extra_fields.append(f"{dest_name} - {MODE_LABEL[mode]} Time (min)")

    out_fields = fieldnames + extra_fields

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for row in rows:
            address = row["Address"]
            for dest_name, dest_addr in DESTINATIONS.items():
                for mode in MODES:
                    info = all_results[mode].get(address, {}).get(dest_addr, {})
                    row[f"{dest_name} - {MODE_LABEL[mode]} Distance (km)"] = info.get("distance_km", "N/A")
                    row[f"{dest_name} - {MODE_LABEL[mode]} Time (min)"] = info.get("duration_min", "N/A")
            writer.writerow(row)

    print(f"Done. Results written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
