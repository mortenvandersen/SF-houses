import csv
import time
import requests

GOOGLE_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"

FRIEND_ADDRESSES = {
    "Friend 1": "[friend 1 address]",
    "Friend 2": "[friend 2 address]",
}

INPUT_CSV = "listings.csv"
OUTPUT_CSV = "listings_with_distances.csv"

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def get_driving_distances(origins: list[str], destinations: list[str]) -> dict:
    """
    Returns a dict: { origin: { destination: {"distance_km": float, "duration_min": float} } }
    Batches up to 25 origins per request (API limit).
    """
    results = {o: {} for o in origins}

    for i in range(0, len(origins), 25):
        batch = origins[i : i + 25]
        params = {
            "origins": "|".join(batch),
            "destinations": "|".join(destinations),
            "mode": "driving",
            "key": GOOGLE_API_KEY,
        }
        resp = requests.get(DISTANCE_MATRIX_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data["status"] != "OK":
            raise RuntimeError(f"Distance Matrix API error: {data['status']}")

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
                    results[origin][dest] = {
                        "distance_km": None,
                        "duration_min": None,
                    }

        if i + 25 < len(origins):
            time.sleep(0.2)  # stay within QPS limits

    return results


def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    origins = [row["Address"] for row in rows]
    destinations = list(FRIEND_ADDRESSES.values())
    friend_names = list(FRIEND_ADDRESSES.keys())

    print(f"Fetching distances for {len(origins)} listings to {len(destinations)} destinations...")
    distances = get_driving_distances(origins, destinations)

    extra_fields = []
    for name in friend_names:
        extra_fields += [
            f"{name} Distance (km)",
            f"{name} Drive Time (min)",
        ]

    out_fields = list(fieldnames) + extra_fields

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for row in rows:
            address = row["Address"]
            for name, dest in FRIEND_ADDRESSES.items():
                info = distances.get(address, {}).get(dest, {})
                row[f"{name} Distance (km)"] = info.get("distance_km", "N/A")
                row[f"{name} Drive Time (min)"] = info.get("duration_min", "N/A")
            writer.writerow(row)

    print(f"Done. Results written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
