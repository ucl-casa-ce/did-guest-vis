# AGENTS.md — BBC Desert Island Discs Visualiser (`did-guest-vis`)

This document serves as the persistent architectural reference, system guide, and operational runbook for AI agents and developers working on this codebase.

---

## 1. Project Overview & Purpose

**BBC Desert Island Discs - Global Castaway Visualiser** is an interactive, fullscreen web application that maps the birthplace locations of over 3,200 castaways spanning 80+ years (from 1942 to the present) of the iconic BBC Radio 4 programme *Desert Island Discs*.

* **Production URL / Docker Registry:** `ghcr.io/ucl-casa-ce/dw/did-guest-vis:latest`
* **GitHub Repository:** `https://github.com/ucl-casa-ce/did-guest-vis`
* **Maintainer:** `djw` / UCL CASA (`ucl-casa-ce`)

---

## 2. System Architecture & Tech Stack

The system consists of two primary layers:
1. **Frontend Client:** Pure client-side static web app (vanilla HTML5, CSS3, ES6 JavaScript) served by Nginx. No heavy frontend frameworks or build steps are used.
2. **Data Enrichment & Ingestion Pipeline:** Offline Python scripts that ingest, geocode, and enrich data from the BBC Podcast RSS feed, BBC Programmes JSON API, MediaWiki API, and Wikidata Entity API.

```
                    ┌────────────────────────────┐
                    │  BBC Podcast RSS Feed      │
                    │  (capped at 2000 episodes) │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
┌─────────────────────────┐  parse_rss.py /
│ Wikipedia Archive Pages │  ingest_historical_archive.py
│ (1942 - 1980 historical)│       │
└───────────┬─────────────┘       │
            │                     │
            └──────────┬──────────┘
                       ▼
                 [data.json] <────► resolve_all_wikidata.py <────► [geocache.json]
                       │            (MediaWiki & Wikidata APIs)
                       │
                       ├──────────► enrich_images.py (BBC Programmes API -> imagePid)
                       │
                       ├──────────► enrich_wikipedia.py (MediaWiki Search -> wikipediaUrl)
                       │
                       ▼
                 [data.json] (3,280+ enriched castaways)
                       │
                       ▼ (served via Nginx / Docker)
          ┌──────────────────────────────────────────┐
          │               Frontend                   │
          │   index.html | app.js | styles.css       │
          │     Leaflet 1.9.4 + CartoDB Positron     │
          └──────────────────────────────────────────┘
```

---

## 3. Data Schema & Core Files

### `data.json`
Array of castaway objects. Sample record:
```json
{
  "id": "classic__arsène_wenger",
  "name": "Classic  Arsène Wenger",
  "broadcastDate": "24 May 2026",
  "episodeUrl": "http://www.bbc.co.uk/programmes/p0nd9nr8",
  "description": "<p>Laurene Laverne talks to the former football manager Arsène Wenger in a programme first broadcast in 2020.</p>",
  "bornIn": "Strasbourg",
  "bornInLat": 48.573333333333,
  "bornInLng": 7.7522222222222,
  "imagePid": "p0nd9pmk",
  "wikipediaUrl": "https://en.wikipedia.org/wiki/Ars%C3%A8ne_Wenger"
}
```

* `id`: Sanitized identifier (e.g. `classic__arsène_wenger` or lowercase title).
* `name`: Episode display title as received from feed/archive.
* `broadcastDate`: Formatted date string (e.g., `"24 May 2026"` or `"12 Jan 1980"`).
* `episodeUrl`: Canonical link to BBC episode page.
* `description`: Raw/semi-sanitized HTML summary from BBC.
* `bornIn`: Resolved birthplace name (city/town).
* `bornInLat`, `bornInLng`: Latitude and Longitude floats (or `null` if unmapped).
* `imagePid`: BBC 16:9 portrait PID. If present, loaded via:
  `https://ichef.bbci.co.uk/images/ic/640x360/{imagePid}.jpg`
* `wikipediaUrl`: Canonical Wikipedia biography link.

### `geocache.json`
Key-value store of place names and Wikidata QIDs mapped to coordinates (over 2,900 entries):
```json
{
  "Strasbourg": { "lat": 48.573333333333, "lng": 7.7522222222222 },
  "Q183337": { "bornIn": "Marylebone", "coords": [51.52, -0.16] }
}
```
*Always check and update this cache when geocoding to prevent Wikidata/MediaWiki rate limiting.*

---

## 4. Frontend Architecture (`index.html`, `app.js`, `styles.css`)

### Map & Tiles
* **Engine:** Leaflet 1.9.4 with Canvas-rendered `L.circleMarker` elements for high performance with 3,000+ points.
* **Basemap:** OpenStreetMap standard tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`), completely free and open-source without requiring any API keys.
* **Controls:** Default Leaflet zoom control moved to `bottomleft` to avoid colliding with the floating HUD.

### Dynamic Spiral Dispersion (Jittering Algorithm)
Because hundreds of castaways share identical birthplaces (e.g., London, New York, Paris), raw coordinates stack. `app.js` calculates a dynamic spiral displacement on runtime load:
$$\theta = n \times 0.5$$
$$r = 0.0006 \times \sqrt{n}$$
Each overlapping point is placed on a tight spiral radius (~60m scale), keeping dots within their home city while ensuring every point is individually visible, hoverable, and clickable.

### Decade Color Mapping
Castaways are categorized and colored by broadcast decade:
* **1940s:** Sand Gold (`#FCD34D`)
* **1950s:** Warm Amber (`#F59E0B`)
* **1960s:** Orange Ochre (`#D97706`)
* **1970s:** Coral Copper (`#EA580C`)
* **1980s:** Coral Pink (`#E11D48`)
* **1990s:** Sea Glass Green (`#14B8A6`)
* **2000s:** Light Teal (`#0D9488`)
* **2010s:** Deep Turquoise (`#0F766E`)
* **2020s:** Deep Abyssal Blue (`#1E3A8A`)
* **Fallback:** Warm Pebble Gray (`#9CA3AF`)

### UI Components
1. **Collapsible HUD Header (Left):**
   * Displays mapped count and most recent broadcast date.
   * State persisted in `localStorage` under key `did_menu_collapsed` (defaults to collapsed on mobile `<768px`, expanded on desktop).
   * **Instant Search Bar:** Live search across castaway names and birthplaces with accent-insensitive matching, autocomplete results dropdown (with decade pill, birthplace, date), keyboard navigation (Arrow Up/Down/Enter/Escape), live marker filtering on the map, and smooth animated pan/zoom (`map.flyTo`) directly to the selected castaway.
   * **Decade Legend Filter:** Clicking any decade filters the map markers dynamically, updates the counter, and closes details if the selected guest is hidden. Clicking again resets the filter.
   * **Autoplay Random Tour:** Cycling interval (5s) that jumps to a random visible marker, centres the map, highlights the dot, and opens the sidebar.
2. **Floating Details Sidebar (Right):**
   * Contains hero image (from BBC iChef), title, birthplace, broadcast date, summary HTML, and action buttons ("Listen on BBC Sounds", "Read on Wikipedia").
   * Uses block-level scrolling (`display: block; height: 100%; overflow-y: auto;`) inside `#details-content` to prevent Safari flexbox overflow collapse bugs.

---

## 5. Backend & Data Pipeline Scripts

All scripts are written in Python 3. Standard library modules (`urllib.request`, `json`, `re`, `xml.etree.ElementTree`) are preferred to keep dependencies minimal.

| Script | Purpose |
| :--- | :--- |
| `update_feed_weekly.py` | **Primary Maintenance Script.** Polls the BBC RSS feed for newly published episodes not yet in `data.json`, cleans names, geocodes via Wikipedia/Wikidata (consulting `geocache.json`), fetches BBC portrait PIDs, and prepends new entries to `data.json`. |
| `parse_rss.py` | Full parser for the BBC Podcast RSS feed (`b006qnmr.rss`). Compiles the initial base dataset. Note: The BBC RSS feed is capped at 2,000 episodes. |
| `ingest_historical_archive.py` | Scrapes historical Wikipedia archive tables for pre-1980 episodes (1942–1946, 1951–1960, 1961–1970, 1971–1980) to cover the full 80-year show archive. |
| `resolve_all_wikidata.py` | Geocoding resolver: cleans names (strips prefix titles like *Dame, Sir, Prof* and suffix roles like *, actor*), searches MediaWiki, matches Wikidata QID, and extracts birthplace coordinates (`P19` -> `P625`). |
| `enrich_images.py` | Multithreaded scraper (`ThreadPoolExecutor`, 15 workers) requesting BBC episode `.json` endpoints to resolve widescreen `imagePid` values. |
| `enrich_wikipedia.py` | Multithreaded Wikipedia search to find and verify biographical Wikipedia article URLs. |
| `refine_unresolved.py` | Utility script targeting records in `data.json` that remain unresolved. |

### Notes on SSL in Python Scripts
Existing offline scripts currently use `ssl_context = ssl._create_unverified_context()` to bypass local macOS certificate store issues. When running or modifying these in environments with modern certificates, prefer `ssl.create_default_context()` or `certifi`.

---

## 6. Docker & CI/CD Deployment

### Dockerfile
* **Base Image:** `nginx:alpine`
* **Static Asset Path:** `/usr/share/nginx/html/`
* **Port:** 80
* **CA Certificates Patch:** Runs `apk update && apk upgrade --no-cache ca-certificates && update-ca-certificates` on build to prevent untrusted root CA issues (eMudhra/emSign advisory).

### GitHub Actions (`.github/workflows/docker-publish.yml`)
* Triggers automatically on push to branch `main`.
* Builds with `--pull --no-cache` to ensure fresh base image layers.
* Publishes image to:
  `ghcr.io/ucl-casa-ce/dw/did-guest-vis:latest`

---

## 7. Local Development Runbook

Because modern browsers block cross-origin `fetch("data.json")` over `file://`, run a local static server:

```bash
# From workspace root
python3 -m http.server 8000
```
Then navigate to: `http://localhost:8000`

### Running the Weekly Update Script
```bash
# Test run (dry-run mode without modifying any files)
python3 update_feed_weekly.py --dry-run

# Run full update (modifies data.json and geocache.json)
python3 update_feed_weekly.py
```
This inspects `data.json`, pulls `https://podcasts.files.bbci.co.uk/b006qnmr.rss`, and enriches any new episodes.

---

## 8. Roadmap & Ideas for Future Development

When continuing work on this codebase, consider the following planned improvements:
1. **Music & Luxury Item Extraction:**
   * Explore extracting castaway track selections, book choices, and luxury items from episode transcripts or Wikidata/Wikipedia (exploratory SPARQL scripts exist in `tests/explore_*.py`).
2. **Search & Filter Bar:**
   * Add a client-side search input in the header HUD to quickly find specific castaways by name, profession, or birthplace.
3. **Automated Weekly GitHub Action:**
   * Set up a scheduled GitHub Action cron job (e.g. every Monday) to run `update_feed_weekly.py`, commit changes to `data.json`, and trigger a new Docker build.
4. **Mobile UX Refinements:**
   * Enhance bottom-sheet transition when opening the details panel on small screen viewports.

