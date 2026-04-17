/**
 * Zillow listing scraper — bookmarklet source.
 *
 * Extracts Zillow's hydrated Next.js JSON (embedded in every listing page)
 * and upserts the longest "description" value plus the full JSON blob to
 * the Supabase `listing_extras` table.
 *
 * To regenerate the bookmarklet URL: paste this file's contents into any
 * JS minifier, prepend "javascript:", and save that as a browser bookmark.
 */
(async () => {
  const URL = "https://sklvnnnxcgnkbccvvwpx.supabase.co";
  const KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNrbHZubm54Y2dua2JjY3Z2d3B4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYzNjc0MDIsImV4cCI6MjA5MTk0MzQwMn0.-I3mDHdYOxYv9WV6vrUQejTtd7uRYNP0rkR-GM6KRSU";

  if (!location.hostname.includes("zillow.com")) {
    alert("Open a Zillow listing page first.");
    return;
  }

  const node = document.getElementById("__NEXT_DATA__");
  if (!node) { alert("Could not find listing data on this page."); return; }

  let data;
  try { data = JSON.parse(node.textContent); }
  catch (e) { alert("Failed to parse listing data."); return; }

  // Walk the object tree (and re-parse embedded JSON strings) collecting
  // every string value stored under the given key; return the longest.
  const seen = new WeakSet();
  const collect = (obj, key, acc) => {
    if (obj == null || typeof obj !== "object" || seen.has(obj)) return acc;
    seen.add(obj);
    if (Array.isArray(obj)) { for (const v of obj) collect(v, key, acc); return acc; }
    if (typeof obj[key] === "string") acc.push(obj[key]);
    for (const k of Object.keys(obj)) {
      let v = obj[k];
      if (typeof v === "string" && (v.startsWith("{") || v.startsWith("["))) {
        try { v = JSON.parse(v); } catch (e) { continue; }
      }
      collect(v, key, acc);
    }
    return acc;
  };
  const descriptions = collect(data, "description", []);
  const description = descriptions.sort((a, b) => b.length - a.length)[0] || null;

  const zpidMatch = location.pathname.match(/(\d+)_zpid/);
  const zpid = zpidMatch ? zpidMatch[1] : null;
  const listingUrl = location.origin + location.pathname;

  const payload = {
    listing_url: listingUrl,
    zpid,
    description,
    raw: data,
    scraped_at: new Date().toISOString(),
  };

  try {
    const resp = await fetch(`${URL}/rest/v1/listing_extras?on_conflict=listing_url`, {
      method: "POST",
      headers: {
        "apikey": KEY,
        "Authorization": "Bearer " + KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
      },
      body: JSON.stringify(payload),
    });
    if (resp.ok) alert(`Saved. Description: ${description ? description.length + " chars" : "not found"}.`);
    else alert(`Supabase error ${resp.status}: ${await resp.text()}`);
  } catch (e) {
    alert("Network error: " + e.message);
  }
})();
