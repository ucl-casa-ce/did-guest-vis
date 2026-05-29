# BBC Desert Island Discs - Global Castaway Visualiser

An interactive fullscreen map vis portraying the 80+ year timeline and global distribution of BBC Radio 4 **Desert Island Discs**. 

All castaways are geocoded by their birthplaces and plotted dynamically on a Leaflet canvas, color-coded by their broadcast decade. When clicked, a panel slides in from the right, displaying their official BBC sounds portrait, a biographical summary, and direct links to listen on BBC Sounds or read on Wikipedia.

All content has come from [BBC DID website](https://www.bbc.co.uk/programmes/b006qnmr), [Wikipedia](https://en.wikipedia.org/wiki/Main_Page) and [WikiData](https://www.wikidata.org/wiki/Wikidata:Main_Page). This page was created using [Antigravity](https://antigravity.google).


## Architecture & Core Pipeline Functions

The backend architecture consists of four distinct, self-contained Python scripts designed to construct, enrich, and cache the database:

```
[BBC Podcast RSS Feed] -> (parse_rss.py) 
                              │
                              ▼
                        [data.json] <─── (resolve_all_wikidata.py) <──> [geocache.json]
                              │
                              ├─── (enrich_images.py) ───► [BBC Programmes JSON]
                              │
                              └─── (enrich_wikipedia.py) ──► [MediaWiki API]
```

### 1. Data Parsing (`parse_rss.py`)
Connects to the official BBC podcast feed, downloads the multi-megabyte XML payload, cleans guest names from episode titles, formats the broadcast dates, parses biographical summaries, and compiles the base `data.json` database.

### 2. Birthplace Geocoding (`resolve_all_wikidata.py`)
Operates completely independently of episode descriptions (critical for historical archive episodes with single-sentence summaries):
* **Name Cleaning:** Sanitizes guest names, stripping title prefixes (e.g. `Dame`, `Sir`, `Professor`) and trailing role suffixes (e.g. `, actor`, `, cook`).
* **Wikipedia Mapping:** Queries the live MediaWiki Search API to match the guest's clean biographical page.
* **Wikidata Entity Resolver:** Bridges the page to its unique Wikidata QID and queries the Wikidata Entity API for the birthplace (`P19`) name and its exact coordinates (`P625`).
* **Incremental Cache (`geocache.json`):** Caches resolved city coordinates locally, ensuring that no online API query is ever repeated, preventing rate-limiting blocks and allowing incremental additions.

### 3. Portrait Enrichment (`enrich_images.py`)
Performs highly parallelized queries against the BBC Programmes API (`.json` endpoints) using a Python `ThreadPoolExecutor` across 15 threads to fetch the unique portrait PID of each guest from the official show pages.
* **Widescreen Portraits:** Resolves and stores widescreen `16:9` portrait IDs inside `data.json`.
* **CORS Avoidance:** Caches all image PIDs locally in the database, completely bypassing browser cross-origin sharing blocks (CORS) and removing runtime network bottlenecks.

### 4. Wikipedia URL Enrichment (`enrich_wikipedia.py`)
An incremental, rate-limit-compliant client that searches and verifies the exact biographical Wikipedia URLs for all 1,998 castaways. Built with robust retries, backoffs, and polite request delays to respect Wikimedia bot guidelines and eliminate rate limits.

### 5. Automated Weekly Update (`update_feed_weekly.py`)
A self-contained, robust automation script designed to run on a recurring weekly basis (e.g. via cron) to keep your visualizer perpetually up to date:
* **Delta Detection:** Connects to the live BBC RSS feed and identifies any newly broadcast episodes that are not yet in your database.
* **All-in-One Processing:** For each new episode detected, it performs name-cleaning, resolves birthplace coordinates via Wikipedia Search/Wikidata APIs (utilizing your local `geocache.json` first), resolves the Sounds widescreen portrait PID, and fetches the verified Wikipedia link—all in a single polite, rate-limit-compliant sweep.
* **Reverse-Chronological Prepending:** Automatically prepends the new castaways to the top of `data.json`, ensuring the main dashboard is updated instantly without affecting the timeline sorting.

## Interactive Map Design & Layout Process

Utilizes CartoDB Positron bright light map tiles. Castaways are color-coded by their broadcast decade using a beach-to-sea gradient:
  * **1940s–1960s (Sunrise/Sand):** Sand Gold (`#FCD34D`) ➔ Warm Amber (`#F59E0B`) ➔ Orange Ochre (`#D97706`)
  * **1970s–1980s (Sunset/Terracotta):** Coral Copper (`#EA580C`) ➔ Coral Pink (`#E11D48`)
  * **1990s–2010s (Seafoam/Teal):** Sea Glass Green (`#14B8A6`) ➔ Light Teal (`#0D9488`) ➔ Deep Turquoise (`#0F766E`)
  * **2020s (Abyssal Ocean):** Deep Abyssal Blue (`#1E3A8A`)
  * **Fallback:** Warm Pebble Gray (`#9CA3AF`)


### Key UI/UX Engineering & Solutions

#### A. Widescreen Scrolling Layout & Safari Flexbox Bugfix
In macOS/iOS Safari, nested flexbox containers with `overflow-y: auto` often suffer from height-calculation bugs, causing scroll containers to collapse, text to overlap, and images to get pushed completely off-screen.
* **The Solution:** a robust, native block-level layout (`display: block; height: 100%; overflow-y: auto;`) for `#details-content` with panel padding moved inside the scroll container. Block layout binds natively to the parent's absolute coordinates, guaranteeing perfect scrolling across all devices and zoom factors.

#### B. Dynamic Spiral dispersion (Jittering)
Due to birthplace concentration (e.g. hundreds of castaways born in London, New York, or Paris), plotting raw coordinates caused dots to stack directly on top of each other, obscuring all but the top dot.
* **The Solution:** Developed a dynamic spiral dispersion algorithm in `app.js` at runtime. If a coordinate key is encountered multiple times, it calculates a radiating spiral angle and radius step (scaled to a tight ~60-meter grid):
  $$\theta = n \times 0.5$$
  $$r = 0.0006 \times \sqrt{n}$$
  This spreads identical birthplaces out into a gorgeous galaxy-like cluster where **every single dot is individually visible, hoverable, and clickable** while remaining within the bounds of its home city.



## Running the Application Locally

Since modern browsers enforce CORS security policies, loading `data.json` via local `file://` protocols is blocked by default. 

To run the application locally:
1. Open your terminal in the project directory.
2. Launch a lightweight local Python HTTP server:
   ```bash
   python3 -m http.server 8000
   ```
3. Open your browser and navigate to:
   [http://localhost:8000](http://localhost:8000)

## Different Dates

The BBC manages and licenses two primary digital audio platforms: BBC Sounds (On-Demand Streaming) and BBC Podcast Downloads (the RSS Feed).

1. The RSS Feed (data.json & DID downloads used on this site) is the Podcast Release Date. The RSS feed (https://podcasts.files.bbci.co.uk/b006qnmr.rss) represents the Global Podcast Edition of the show.

The "Classic" Drop Schedule: The BBC periodically curates and drops historic archive episodes into the podcast feed as "Classic" downloads. 

The Date Value: The pubDate inside the RSS feed is the exact moment the audio file was uploaded and published to the public podcast servers (in this case, 24 May 2026). It is a "Classic" re-release date, which is why the prefix "Classic  " is prepended to the guest's name.

2. The BBC Sounds App/Site (/sounds/brand/b006qnmr) is the Radio Transmission Date. The BBC Sounds platform is the Catch-Up & Live Radio Player for UK audiences.

Broadcast-First Licensing: On BBC Sounds, episodes are tied strictly to the live FM/DAB radio transmission schedule on BBC Radio 4.

Regional & Rights Windows: Due to strict broadcast copyright and music licensing rights, the BBC often streams episodes on the Sounds app under a streaming-only license on a different timeline compared to when the permanent download file is packaged and distributed globally via RSS.

The Date Value: When you see a different date (like April 24) on BBC Sounds, it represents either:

The original on-air radio broadcast date (or a recent repeat transmission date on Radio 4).

A pre-release window where UK listeners on the BBC Sounds app get exclusive early streaming access to episodes weeks before they are legally cleared and published as permanent downloadable audio files in the global podcast RSS feed.

## Capped Podcast RSS Feed vs. 80-Year Archive
The ingestion pipeline (parse_rss.py and update_feed_weekly.py) builds the database by downloading and parsing the official BBC Podcast RSS feed (https://podcasts.files.bbci.co.uk/b006qnmr.rss).

The live BBC RSS feed is capped at a hard limit of exactly 2,000 episodes. Desert Island Discs has broadcast over 3,400 episodes since its inception in 1942. As a result, older episodes from the archive routinely drop off the feed unless they are actively dropped back in as curated "Classic" episodes. This dataset goes back to Dec 1978.