import json
import urllib.request
import urllib.parse
import ssl
import os
import re
import sys
import time
from datetime import datetime

# Configuration
DECADES = [
    "1942–1946",
    "1951–1960",
    "1961–1970",
    "1971–1980"
]

DATABASE_FILE = "data.json"
CACHE_FILE = "geocache.json"
WIKI_CACHE_DIR = "wikipedia_cache"
CHECKPOINT_FILE = "data_historical_checkpoint.json"

ssl_context = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Ensure directories exist
os.makedirs(WIKI_CACHE_DIR, exist_ok=True)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving cache: {e}")

def clean_tags(text):
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r'<.*?>', '', text)
    # Normalize spaces
    clean = re.sub(r'\s+', ' ', clean)
    # Remove citation brackets like [1] or [Note 2]
    clean = re.sub(r'\[.*?\]', '', clean)
    return clean.strip()

def parse_broadcast_date(date_str):
    date_str = clean_tags(date_str)
    # Remove extra brackets or text (like "(repeated)" or similar)
    date_str = re.sub(r'\(.*?\)', '', date_str).strip()
    
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    short_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Try full month name: "11 February 1978"
    for idx, m in enumerate(months):
        if m in date_str:
            parts = date_str.split(m)
            day = parts[0].strip()
            year = parts[1].strip()
            try:
                # Keep only digits for day and year
                day_val = int(re.sub(r'\D', '', day))
                year_val = int(re.sub(r'\D', '', year))
                return datetime(year_val, idx + 1, day_val)
            except ValueError:
                pass
                
    # Try short month name: "11 Feb 1978"
    for idx, m in enumerate(short_months):
        if m in date_str:
            parts = date_str.split(m)
            day = parts[0].strip()
            year = parts[1].strip()
            try:
                day_val = int(re.sub(r'\D', '', day))
                year_val = int(re.sub(r'\D', '', year))
                return datetime(year_val, idx + 1, day_val)
            except ValueError:
                pass
    return None

def fetch_wikipedia_list(decade):
    cache_path = os.path.join(WIKI_CACHE_DIR, f"wikipedia_{decade}.html")
    if os.path.exists(cache_path):
        print(f"  [Cache] Loaded Wikipedia list for decade {decade} from cache.")
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
            
    # Need to download
    url = f"https://en.wikipedia.org/wiki/List_of_Desert_Island_Discs_episodes_({urllib.parse.quote(decade)})"
    print(f"  [Download] Fetching Wikipedia list for {decade} from {url}...")
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            html = response.read().decode("utf-8")
        # Save to cache
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(html)
        time.sleep(1.0) # Polite sleep
        return html
    except Exception as e:
        print(f"  [Error] Failed to download Wikipedia list for {decade}: {e}")
        return None

def scrape_wikipedia_episodes():
    print("Scraping all Wikipedia episode lists (1942–1980)...")
    episodes = []
    
    for decade in DECADES:
        html = fetch_wikipedia_list(decade)
        if not html:
            continue
            
        # Find all tables with wikitable class
        tables = re.findall(r'<table class="wikitable sortable".*?>.*?</table>', html, re.DOTALL)
        decade_count = 0
        
        for table in tables:
            rows = re.findall(r'<tr>(.*?)</tr>', table, re.DOTALL)
            for row in rows:
                cells = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)
                if not cells or len(cells) < 4:
                    continue
                    
                date_str = clean_tags(cells[0])
                broadcast_dt = parse_broadcast_date(date_str)
                if not broadcast_dt:
                    continue
                    
                # We only want episodes before December 1, 1978
                if broadcast_dt >= datetime(1978, 12, 1):
                    continue
                    
                castaway_cell = cells[1]
                castaway_name = clean_tags(castaway_cell)
                if not castaway_name or "special" in castaway_name.lower() or "compilation" in castaway_name.lower():
                    continue
                    
                # Extract Wikipedia title link
                wiki_title = None
                wiki_match = re.search(r'href="/wiki/([^"#\s]+)"', castaway_cell)
                if wiki_match:
                    wiki_title = wiki_match.group(1)
                    # Filter out non-biographical Wikipedia namespaces
                    if any(ns in wiki_title for ns in ["File:", "Category:", "Special:", "Help:", "Wikipedia:", "Template:"]):
                        wiki_title = None
                
                # If no direct wiki link in the cell, fallback to clean name for slug later
                book_str = clean_tags(cells[2])
                luxury_str = clean_tags(cells[3])
                
                # Extract BBC PID (if 5 or more columns are present)
                pid = None
                if len(cells) >= 5:
                    bbc_cell = cells[4]
                    pid_match = re.search(r'href="https?://www\.bbc\.co\.uk/programmes/([a-z0-9]+)"', bbc_cell)
                    if pid_match:
                        pid = pid_match.group(1)
                    
                # Format dates consistently as "DD Month YYYY"
                months_str = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                formatted_date = f"{broadcast_dt.day} {months_str[broadcast_dt.month-1]} {broadcast_dt.year}"
                
                episodes.append({
                    "name": castaway_name,
                    "broadcastDate": formatted_date,
                    "dateObj": broadcast_dt,
                    "wikiTitle": wiki_title,
                    "book": book_str,
                    "luxury": luxury_str,
                    "pid": pid
                })
                decade_count += 1
                
        print(f"  -> Extracted {decade_count} matching historical episodes from decade {decade}.")
        
    # Sort chronologically by date
    episodes.sort(key=lambda x: x["dateObj"])
    print(f"\nTotal extracted pre-Dec 1978 episodes: {len(episodes)}")
    return episodes

# --- Metadata Enrichment Functions ---

def get_wikidata_qid(page_title):
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=pageprops&titles={urllib.parse.quote(page_title)}&format=json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_info in pages.items():
                pageprops = page_info.get("pageprops", {})
                if "wikibase_item" in pageprops:
                    return pageprops["wikibase_item"]
    except Exception as e:
        print(f"    [Wikidata] QID fetch error for {page_title}: {e}")
    return None

def get_label(qid):
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
        entity = data.get("entities", {}).get(qid, {})
        labels = entity.get("labels", {})
        return labels.get("en", {}).get("value")
    except Exception:
        return None

def resolve_place_coords(place_qid, cache):
    # Check if place is already in geocache by QID
    if place_qid in cache:
        return cache[place_qid]
        
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{place_qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get(place_qid, {})
        place_name = entity.get("labels", {}).get("en", {}).get("value")
        
        # If place name is a top-level cached city, reuse it
        if place_name in cache and isinstance(cache[place_name], dict) and "lat" in cache[place_name]:
            coords = cache[place_name]
            result = {"bornIn": place_name, "bornInLat": coords["lat"], "bornInLng": coords["lng"]}
            cache[place_qid] = result
            return result
            
        claims = entity.get("claims", {})
        coords_claims = claims.get("P625", [])
        if coords_claims:
            val = coords_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
            lat = val.get("latitude")
            lng = val.get("longitude")
            if lat is not None and lng is not None:
                result = {"bornIn": place_name, "bornInLat": lat, "bornInLng": lng}
                cache[place_qid] = result
                # Also cache under place name directly
                cache[place_name] = {"lat": lat, "lng": lng}
                return result
    except Exception as e:
        print(f"    [Wikidata] Place coords fetch error for {place_qid}: {e}")
        
    return None

def get_birthplace_and_coords(qid, cache):
    if qid in cache:
        # Check if the cache entry contains resolved coordinates
        entry = cache[qid]
        if isinstance(entry, dict) and entry.get("bornInLat") is not None:
            return entry
            
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get(qid, {})
        claims = entity.get("claims", {})
        
        # Try fallbacks in order: P19 (birthplace), P740 (formation location), P937 (work location)
        for prop in ["P19", "P740", "P937"]:
            prop_claims = claims.get(prop, [])
            if prop_claims:
                place_qid = prop_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                if place_qid:
                    time.sleep(0.05)
                    coords_data = resolve_place_coords(place_qid, cache)
                    if coords_data:
                        cache[qid] = coords_data
                        return coords_data
                        
    except Exception as e:
        print(f"    [Wikidata] Birthplace resolution error for {qid}: {e}")
        
    # Unresolved: Default to user's requested coordinates: lat -14, lng -13, name "Desert Island"
    print(f"    [Wikidata] Unresolved birthplace for {qid}. Setting to Desert Island (-14, -13) fallback.")
    unresolved_fallback = {"bornIn": "Desert Island", "bornInLat": -14.0, "bornInLng": -13.0}
    cache[qid] = unresolved_fallback
    return unresolved_fallback

def fetch_bbc_details(pid):
    if not pid:
        return {"description": "", "imagePid": "p07my0ks"}
        
    url = f"https://www.bbc.co.uk/programmes/{pid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
                data = json.loads(response.read().decode("utf-8"))
                programme = data.get("programme", {})
                image = programme.get("image", {})
                image_pid = image.get("pid", "p07my0ks")
                
                # Fetch detailed synopses
                synopsis = programme.get("long_synopsis") or programme.get("medium_synopsis") or programme.get("short_synopsis") or ""
                return {"description": synopsis.strip(), "imagePid": image_pid}
        except Exception as e:
            if attempt == 2:
                print(f"    [BBC API] Failed to fetch metadata for PID {pid}: {e}")
            time.sleep(0.5 + attempt)
            
    return {"description": "", "imagePid": "p07my0ks"}

# --- Main Ingestion Loop ---

def main():
    dry_run = True
    if "--run" in sys.argv:
        dry_run = False
        
    print("=" * 60)
    print("      BBC DESERT ISLAND DISCS - HISTORICAL ARCHIVE SCRAPER")
    print("=" * 60)
    
    # 1. Load existing database
    if not os.path.exists(DATABASE_FILE):
        print(f"Error: {DATABASE_FILE} not found. Please run parse_rss.py first.")
        return
        
    with open(DATABASE_FILE, "r", encoding="utf-8") as f:
        master_list = json.load(f)
    print(f"Loaded {len(master_list)} castaways from {DATABASE_FILE}.")
    
    # Store existing links, names, and IDs for deduplication
    existing_pids = set()
    existing_urls = set()
    existing_ids = set()
    
    for c in master_list:
        url = c.get("episodeUrl") or ""
        existing_urls.add(url.strip())
        pid_match = re.search(r'programmes/([a-z0-9]+)', url)
        if pid_match:
            existing_pids.add(pid_match.group(1))
        if c.get("id"):
            existing_ids.add(c["id"])
            
    # 2. Scrape Wikipedia list
    wiki_episodes = scrape_wikipedia_episodes()
    
    # 3. Detect gaps
    missing_episodes = []
    for ep in wiki_episodes:
        # Check if already in data.json by PID
        if ep["pid"] and ep["pid"] in existing_pids:
            continue
        # Check by link
        ep_url = f"https://www.bbc.co.uk/programmes/{ep['pid']}" if ep['pid'] else ""
        if ep_url and ep_url in existing_urls:
            continue
        # Check by ID slug
        guest_slug = ep["name"].lower().replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
        guest_slug = re.sub(r'[^a-z0-9_]', '', guest_slug)
        if guest_slug in existing_ids:
            continue
        missing_episodes.append(ep)
        
    print(f"Total missing pre-1978 episodes in database: {len(missing_episodes)}")
    
    if not missing_episodes:
        print("\n🎉 Database is fully complete with all historical pre-1978 episodes!")
        return
        
    if dry_run:
        print("\n" + "!" * 50)
        print("  DRY RUN MODE ACTIVE")
        print("  To run the full scraper, execute: python3 ingest_historical_archive.py --run")
        print("!" * 50 + "\n")
        
        print(f"Reviewing the first 5 missing historical episodes:")
        for idx, ep in enumerate(missing_episodes[:5], 1):
            print(f"  {idx}. {ep['name']} - Broadcast: {ep['broadcastDate']} (PID: {ep['pid']})")
        print("-" * 50)
        print("Dry run complete. No modifications were made.")
        return
        
    # Full Run Mode
    print("\n🚀 Beginning full historical database ingestion...")
    print("This will process missing episodes in reverse-chronological order and merge them.")
    
    cache = load_cache()
    checkpoint = []
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
            print(f"Loaded {len(checkpoint)} already processed entries from checkpoint file.")
        except Exception:
            checkpoint = []
            
    checkpoint_pids = {c["episodeUrl"].split("/")[-1] for c in checkpoint if c.get("episodeUrl")}
    
    # Process from newest to oldest to append cleanly
    ep_to_process = [ep for ep in missing_episodes if ep["pid"] not in checkpoint_pids]
    print(f"Total entries remaining to process: {len(ep_to_process)}")
    
    added_count = 0
    try:
        for idx, ep in enumerate(ep_to_process, 1):
            name = ep["name"]
            pid = ep["pid"]
            wiki_title = ep["wikiTitle"]
            
            print(f"\n[{idx}/{len(ep_to_process)}] Processing: '{name}' (Broadcast: {ep['broadcastDate']})...")
            
            # A. Resolve Birthplace & Coordinates
            wiki_url = None
            born_in = "Desert Island"
            lat = -14.0
            lng = -13.0
            
            if wiki_title:
                wiki_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(wiki_title)}"
                qid = get_wikidata_qid(wiki_title)
                if qid:
                    loc_data = get_birthplace_and_coords(qid, cache)
                    born_in = loc_data.get("bornIn", "Desert Island")
                    lat = loc_data.get("bornInLat", -14.0)
                    lng = loc_data.get("bornInLng", -13.0)
                    print(f"    -> Coordinates: {born_in} ({lat}, {lng})")
                else:
                    print("    -> No Wikidata QID found. Defaulting to Desert Island (-14, -13).")
            else:
                # No wiki page: Fall back to clean name search
                print(f"    -> No direct Wiki title found. Defaulting to Desert Island (-14, -13).")
                
            # B. Resolve BBC Sounds Synopses & Image PID
            bbc_url = f"https://www.bbc.co.uk/programmes/{pid}" if pid else "https://www.bbc.co.uk/programmes/b006qnmr"
            bbc_data = fetch_bbc_details(pid) if pid else {"description": "", "imagePid": "p07my0ks"}
            
            # C. Construct rich description
            bbc_synopsis = bbc_data["description"]
            p2_parts = []
            if ep["book"]:
                p2_parts.append(f"Book: {ep['book']}")
            if ep["luxury"]:
                p2_parts.append(f"Luxury: {ep['luxury']}")
                
            desc_html = ""
            if bbc_synopsis:
                desc_html = f"<p>{bbc_synopsis}</p>"
            else:
                desc_html = f"<p>Roy Plomley's castaway is {name}.</p>"
                
            if p2_parts:
                desc_html += f"<p>{'<br>'.join(p2_parts)}</p>"
                
            # D. Build complete JSON entry
            guest_slug = name.lower().replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
            guest_slug = re.sub(r'[^a-z0-9_]', '', guest_slug)
            
            record = {
                "id": guest_slug,
                "name": name,
                "broadcastDate": ep["broadcastDate"],
                "episodeUrl": bbc_url,
                "description": desc_html,
                "bornIn": born_in,
                "bornInLat": lat,
                "bornInLng": lng,
                "imagePid": bbc_data["imagePid"],
                "wikipediaUrl": wiki_url
            }
            
            checkpoint.append(record)
            added_count += 1
            
            # Save progress incrementally
            if idx % 10 == 0:
                print(f"\n  [Checkpoint] Saving {len(checkpoint)} processed items and coordinates cache...")
                save_cache(cache)
                with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cp_out:
                    json.dump(checkpoint, cp_out, indent=2, ensure_ascii=False)
                    
            time.sleep(0.3) # Polite rate limit
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user! Saving checkpoint and cache before exiting...")
        save_cache(cache)
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cp_out:
            json.dump(checkpoint, cp_out, indent=2, ensure_ascii=False)
        sys.exit(0)
        
    # C. Consolidation Phase
    print("\n🏁 Process complete! Consolidating database...")
    save_cache(cache)
    
    # Combine existing data and newly processed entries
    # Filter out duplicates by PID (if not generic show page b006qnmr) and guest slug ID
    final_list = list(master_list)
    existing_pids = {c["episodeUrl"].split("/")[-1] for c in final_list if c.get("episodeUrl") and c["episodeUrl"].split("/")[-1] != "b006qnmr"}
    existing_ids = {c["id"] for c in final_list if c.get("id")}
    
    for item in checkpoint:
        item_pid = item["episodeUrl"].split("/")[-1]
        item_id = item["id"]
        
        is_dup = False
        if item_id in existing_ids:
            is_dup = True
        elif item_pid != "b006qnmr" and item_pid in existing_pids:
            is_dup = True
            
        if not is_dup:
            final_list.append(item)
            if item_pid != "b006qnmr":
                existing_pids.add(item_pid)
            existing_ids.add(item_id)
            
    # Helper to parse display dates back to date objects for chronological sorting
    def get_sort_key(item):
        date_str = item.get("broadcastDate", "")
        dt = parse_broadcast_date(date_str)
        return dt if dt else datetime(1900, 1, 1)
        
    # Sort in reverse chronological order (newest first)
    final_list.sort(key=get_sort_key, reverse=True)
    
    # Save final database
    with open(DATABASE_FILE, "w", encoding="utf-8") as f_out:
        json.dump(final_list, f_out, indent=2, ensure_ascii=False)
        
    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        
    print(f"\n🎉 Successfully added {added_count} historical episodes!")
    print(f"Updated database: {DATABASE_FILE} has now {len(final_list)} total records.")
    print("Ready to preview in browser!")

if __name__ == "__main__":
    main()
