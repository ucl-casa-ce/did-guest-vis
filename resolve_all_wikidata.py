import json
import urllib.request
import urllib.parse
import ssl
import time
import os
import re

INPUT_FILE = "data.json"
CACHE_FILE = "geocache.json"

ssl_context = ssl._create_unverified_context()
HEADERS = {"User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"}

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

def search_wikipedia(name):
    clean_name = clean_guest_name(name)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(clean_name)}&srlimit=3&format=json"
    
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("query", {}).get("search", [])
            if results:
                return results[0]["title"]
    except Exception as e:
        print(f"Error searching Wikipedia for '{name}': {e}")
    return None

def get_wikidata_qid(page_title):
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=pageprops&titles={urllib.parse.quote(page_title)}&format=json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_info in pages.items():
                pageprops = page_info.get("pageprops", {})
                if "wikibase_item" in pageprops:
                    return pageprops["wikibase_item"]
    except Exception as e:
        print(f"Error fetching QID for '{page_title}': {e}")
    return None

def get_birthplace_and_coords(qid, cache):
    # Check cache first
    if qid in cache:
        return cache[qid]
        
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get(qid, {})
        claims = entity.get("claims", {})
        
        born_in_name = None
        lat = None
        lng = None
        
        # 1. Get birthplace (P19) QID
        born_in_claims = claims.get("P19", [])
        if born_in_claims:
            born_in_qid = born_in_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if born_in_qid:
                # Fetch birthplace name in English
                born_in_name = get_label(born_in_qid)
                
                # Fetch birthplace coordinates (P625)
                born_in_url = f"https://www.wikidata.org/wiki/Special:EntityData/{born_in_qid}.json"
                born_in_req = urllib.request.Request(born_in_url, headers=HEADERS)
                
                # Tiny sleep to respect Wikidata
                time.sleep(0.05)
                with urllib.request.urlopen(born_in_req, timeout=10, context=ssl_context) as b_resp:
                    b_data = json.loads(b_resp.read().decode("utf-8"))
                
                b_entity = b_data.get("entities", {}).get(born_in_qid, {})
                b_claims = b_entity.get("claims", {})
                
                # Get P625 (coordinate location)
                coords_claims = b_claims.get("P625", [])
                if coords_claims:
                    val = coords_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    lat = val.get("latitude")
                    lng = val.get("longitude")
                    
        result = {"bornIn": born_in_name, "bornInLat": lat, "bornInLng": lng}
        cache[qid] = result
        return result
    except Exception as e:
        print(f"Error fetching coordinates for QID '{qid}': {e}")
    return {"bornIn": None, "bornInLat": None, "bornInLng": None}

def get_label(qid):
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
        entity = data.get("entities", {}).get(qid, {})
        labels = entity.get("labels", {})
        return labels.get("en", {}).get("value")
    except Exception:
        return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        castaways = json.load(f)
        
    print(f"Loaded {len(castaways)} castaways.")
    cache = load_cache()
    print(f"Loaded {len(cache)} entries from geocache.")
    
    unresolved_count = 0
    resolved_count = 0
    
    # We will limit our online lookup rate to avoid hitting MediaWiki API rate thresholds
    # We will check if the castaway already has bornInLat coordinate, if so we don't query
    for idx, c in enumerate(castaways, 1):
        if c.get("bornInLat") is not None:
            resolved_count += 1
            continue
            
        name = c["name"]
        print(f"[{idx}/{len(castaways)}] Resolving online: '{name}'...")
        
        # Search Wikipedia
        title = search_wikipedia(name)
        if not title:
            print("  -> Wikipedia article not found.")
            c["bornInLat"] = None
            c["bornInLng"] = None
            unresolved_count += 1
            continue
            
        # Get QID
        time.sleep(0.05)
        qid = get_wikidata_qid(title)
        if not qid:
            print(f"  -> QID not found for title '{title}'.")
            c["bornInLat"] = None
            c["bornInLng"] = None
            unresolved_count += 1
            continue
            
        # Get birthplace and coordinates
        time.sleep(0.05)
        loc_data = get_birthplace_and_coords(qid, cache)
        
        # Populate coordinates and birthplace name
        c["bornIn"] = loc_data.get("bornIn")
        c["bornInLat"] = loc_data.get("bornInLat")
        c["bornInLng"] = loc_data.get("bornInLng")
        
        # Clean up legacy location fields to keep ONLY birthplace coordinates
        for key in ["livesIn", "livesInLat", "livesInLng", "grewUpIn", "hometown"]:
            if key in c:
                del c[key]
        
        if c["bornInLat"] is not None:
            print(f"  -> Success: Birthplace: {c['bornIn']} | Lat: {c['bornInLat']} | Lng: {c['bornInLng']}")
            resolved_count += 1
        else:
            print("  -> Could not extract birth coordinates from Wikidata.")
            unresolved_count += 1
            
        # Save cache and data incrementally every 10 queries
        if idx % 10 == 0:
            save_cache(cache)
            with open(INPUT_FILE, "w", encoding="utf-8") as f_out:
                json.dump(castaways, f_out, indent=2, ensure_ascii=False)
                
    # Final save
    save_cache(cache)
    with open(INPUT_FILE, "w", encoding="utf-8") as f_out:
        json.dump(castaways, f_out, indent=2, ensure_ascii=False)
        
    print("\n--- FINAL RESOLUTION SUMMARY ---")
    print(f"Total processed: {len(castaways)}")
    print(f"Successfully geocoded castaways: {resolved_count} ({resolved_count/len(castaways)*100:.1f}%)")
    print(f"Castaways without birth coordinates: {unresolved_count}")

if __name__ == "__main__":
    main()
