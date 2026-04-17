"""Refresh the dashboard from whatever is in searches/.

Steps:
  1. Merge all CSVs in searches/ (deduped by Listing URL), fetch Google
     Distance Matrix rows for listings we haven't processed yet, and append
     them to listings_with_distances.csv.
  2. Rebuild index.html from listings_with_distances.csv.
"""

import distance_matrix
import build_dashboard


if __name__ == "__main__":
    print("=== Step 1: merge searches + distance matrix ===")
    distance_matrix.main()
    print()
    print("=== Step 2: rebuild dashboard ===")
    build_dashboard.main()
