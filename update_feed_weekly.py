import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import ssl
import os
import re
import time
from datetime import datetime

# Configuration
RSS_FEED_URL = "https://podcasts.files.bbci.co.uk/b006qnmr.rss"
DATABASE_FILE = "data.json"
CACHE_FILE = "geocache.json"

ssl_context = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def clean_guest_name(name):
    # Remove "Classic " prefix
    name = re.sub(r'^(Classic\s+)', '', name, flags=re.IGNORECASE).strip()
    # Split by comma and take first part (removes roles)
    name = name.split(",")[0].strip()
    # Strip common prefix titles
    name = re.sub(r'^(Professor|Prof\b|Dr|Sir|Dame|Lady|Lord|Rt\s+Hon|Rt\.\s+Hon\.)\s+', '', name, flags=re.IGNORECASE).strip()
    # Strip common trailing titles
    name = re.sub(r'\s+(MP|CBE|OBE|MBE|KBE|DBE|FRS)$', '', name, flags=re.IGNORECASE).strip()
    return name

# --- Geocoding & Wiki Link Helpers ---

def search_wikipedia_title(name):
    clean_name = clean_guest_name(name)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(clean_name)}&srlimit=3&format=json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("query", {}).get("search", [])
            if results:
                return results[0]["title"]
    except Exception as e:
        print(f"  [Wikipedia] Search error: {e}")
    return None

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
        print(f"  [Wikidata] QID fetch error: {e}")
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

def get_birthplace_and_coords(qid, cache):
    if qid in cache:
        return cache[qid]
        
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get(qid, {})
        claims = entity.get("claims", {})
        
        born_in_name = None
        lat = None
        lng = None
        
        born_in_claims = claims.get("P19", [])
        if born_in_claims:
            born_in_qid = born_in_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if born_in_qid:
                born_in_name = get_label(born_in_qid)
                
                born_in_url = f"https://www.wikidata.org/wiki/Special:EntityData/{born_in_qid}.json"
                born_in_req = urllib.request.Request(born_in_url, headers=HEADERS)
                
                time.sleep(0.05)
                with urllib.request.urlopen(born_in_req, timeout=8, context=ssl_context) as b_resp:
                    b_data = json.loads(b_resp.read().decode("utf-8"))
                
                b_entity = b_data.get("entities", {}).get(born_in_qid, {})
                b_claims = b_entity.get("claims", {})
                
                coords_claims = b_claims.get("P625", [])
                if coords_claims:
                    val = coords_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    lat = val.get("latitude")
                    lng = val.get("longitude")
                    
        if born_in_name is None or lat is None or lng is None:
            result = {"bornIn": "Desert Island", "bornInLat": -14.0, "bornInLng": -13.0}
        else:
            result = {"bornIn": born_in_name, "bornInLat": lat, "bornInLng": lng}
        cache[qid] = result
        return result
    except Exception as e:
        print(f"  [Wikidata] Birthplace geocoding error for {qid}: {e}")
    return {"bornIn": "Desert Island", "bornInLat": -14.0, "bornInLng": -13.0}

# --- BBC Portrait Resolver ---

def fetch_bbc_image_pid(episode_url):
    url_json = episode_url.strip()
    if not url_json.endswith(".json"):
        if url_json.endswith("/"):
            url_json = url_json[:-1]
        url_json += ".json"
    
    if url_json.startswith("http://"):
        url_json = "https://" + url_json[7:]
        
    req = urllib.request.Request(url_json, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
                data = json.loads(response.read().decode("utf-8"))
                programme = data.get("programme", {})
                image = programme.get("image", {})
                return image.get("pid")
        except Exception as e:
            if attempt == 2:
                print(f"  [BBC Sounds] Portrait fetch failed: {e}")
                return None
            time.sleep(1 + attempt)
    return None

# --- Main Weekly Update Loop ---

def main():
    if not os.path.exists(DATABASE_FILE):
        print(f"Error: {DATABASE_FILE} not found. Please construct the initial database first.")
        return
        
    with open(DATABASE_FILE, "r", encoding="utf-8") as f:
        castaways = json.load(f)
        
    print(f"Loaded {len(castaways)} castaways from local database.")
    
    # Store existing links for deduplication check
    existing_urls = {c["episodeUrl"] for c in castaways if c.get("episodeUrl")}
    
    # Fetch live RSS feed
    print(f"Downloading BBC RSS feed...")
    req = urllib.request.Request(RSS_FEED_URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            xml_data = response.read()
        print(f"Downloaded RSS feed successfully ({len(xml_data)/1024/1024:.2f} MB).")
    except Exception as e:
        print(f"Error fetching the RSS feed: {e}")
        return
        
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        print(f"Error parsing XML content: {e}")
        return
        
    items = root.findall(".//item")
    print(f"Found {len(items)} episodes in live RSS feed. checking for new entries...")
    
    new_episodes = []
    
    for item in items:
        link_el = item.find("link")
        episode_url = link_el.text.strip() if link_el is not None else ""
        
        if not episode_url:
            continue
            
        # Deduplication check
        if episode_url in existing_urls:
            continue
            
        title_el = item.find("title")
        pub_date_el = item.find("pubDate")
        desc_el = item.find("description")
        
        title = title_el.text if title_el is not None else ""
        pub_date_str = pub_date_el.text if pub_date_el is not None else ""
        description = desc_el.text if desc_el is not None else ""
        
        guest_name = title.replace("Desert Island Discs:", "")
        guest_name = guest_name.replace("Desert Island Discs -", "")
        guest_name = guest_name.replace("Desert Island Discs", "").strip()
        
        # Skip compilations/highlights
        if not guest_name or any(kw in guest_name.lower() for kw in ["compilation", "anniversary", "intro", "selection", "highlight", "special", "episode"]):
            continue
            
        # Format Date
        broadcast_date = pub_date_str
        if pub_date_str:
            try:
                clean_date = pub_date_str[:25].strip()
                dt = datetime.strptime(clean_date, "%a, %d %b %Y %H:%M:%S")
                months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                broadcast_date = f"{dt.day} {months[dt.month-1]} {dt.year}"
            except Exception:
                pass
                
        new_episodes.append({
            "name": guest_name,
            "broadcastDate": broadcast_date,
            "episodeUrl": episode_url,
            "description": description.strip()
        })
        
    if not new_episodes:
        print("\n🎉 No new episodes found. The database is fully up to date!")
        return
        
    print(f"\n✨ Detected {len(new_episodes)} new episode(s) to add!")
    
    cache = load_cache()
    added_count = 0
    
    for c in reversed(new_episodes): # Process in chronological order (oldest to newest) to append correctly
        name = c["name"]
        print(f"\nProcessing new castaway: '{name}'...")
        
        # 1. Resolve Wikipedia & Wikidata Coordinates
        wiki_url = None
        born_in = "Desert Island"
        lat = -14.0
        lng = -13.0
        
        wiki_title = search_wikipedia_title(name)
        if wiki_title:
            wiki_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(wiki_title.replace(' ', '_'))}"
            qid = get_wikidata_qid(wiki_title)
            if qid:
                loc_data = get_birthplace_and_coords(qid, cache)
                born_in = loc_data.get("bornIn", "Desert Island")
                lat = loc_data.get("bornInLat", -14.0)
                lng = loc_data.get("bornInLng", -13.0)
                print(f"  -> Coordinates found: {born_in} ({lat}, {lng})")
            else:
                print("  -> Wikidata QID not found. Defaulting to Desert Island (-14, -13).")
        else:
            print("  -> Wikipedia article not found. Defaulting to Desert Island (-14, -13).")
            
        # 2. Resolve BBC imagePid
        image_pid = fetch_bbc_image_pid(c["episodeUrl"])
        if image_pid:
            print(f"  -> BBC sounds image resolved: {image_pid}")
        else:
            print("  -> BBC sounds image not found.")
            
        # 3. Create full database record
        guest_slug = name.lower().replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
        
        record = {
            "id": guest_slug,
            "name": name,
            "broadcastDate": c["broadcastDate"],
            "episodeUrl": c["episodeUrl"],
            "description": c["description"],
            "bornIn": born_in,
            "bornInLat": lat,
            "bornInLng": lng,
            "imagePid": image_pid,
            "wikipediaUrl": wiki_url
        }
        
        # Prepend to the top of the array so it remains reverse-chronological
        castaways.insert(0, record)
        added_count += 1
        
        time.sleep(0.5) # Dynamic sleep between lookups to be extremely polite
        
    # Save cache & database
    save_cache(cache)
    with open(DATABASE_FILE, "w", encoding="utf-8") as f_out:
        json.dump(castaways, f_out, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 Successfully added and geocoded {added_count} new castaway(s)!")
    print(f"Updated database: {DATABASE_FILE} has now {len(castaways)} total records.")

if __name__ == "__main__":
    main()
