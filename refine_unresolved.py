import json
import urllib.request
import urllib.parse
import ssl
import time
import os
import re
import sys

DATABASE_FILE = "data.json"
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
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving cache: {e}")

def build_lowercase_index(cache):
    index = {}
    for k, v in cache.items():
        if not isinstance(v, dict):
            continue
        # Case 1: k is a place name with lat/lng
        if "lat" in v and "lng" in v and v["lat"] is not None:
            index[k.lower()] = {"lat": v["lat"], "lng": v["lng"]}
        # Case 2: k is a QID containing bornIn and bornInLat/Lng
        if "bornIn" in v and v.get("bornInLat") is not None and v["bornInLat"] != -14.0:
            name = v["bornIn"]
            if name:
                index[name.lower()] = {"lat": v["bornInLat"], "lng": v["bornInLng"]}
    return index

def clean_tags(text):
    if not text:
        return ""
    clean = re.sub(r'<.*?>', '', text)
    clean = re.sub(r'\s+', ' ', clean)
    clean = re.sub(r'\[.*?\]', '', clean)
    return clean.strip()

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
        print(f"    [Error] QID fetch error for {page_title}: {e}")
    return None

def resolve_place_coords(place_qid, cache):
    if place_qid in cache:
        entry = cache[place_qid]
        if isinstance(entry, dict) and "lat" in entry:
            return {"bornInLat": entry["lat"], "bornInLng": entry["lng"]}
        elif isinstance(entry, dict) and "bornInLat" in entry:
            return {"bornInLat": entry["bornInLat"], "bornInLng": entry["bornInLng"]}
        
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{place_qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get(place_qid, {})
        place_name = entity.get("labels", {}).get("en", {}).get("value")
        
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
                cache[place_name] = {"lat": lat, "lng": lng}
                return result
    except Exception as e:
        print(f"    [Error] Place coords fetch error for {place_qid}: {e}")
        
    return None

def get_person_birthplace_coords(person_qid, cache):
    if person_qid in cache:
        entry = cache[person_qid]
        if isinstance(entry, dict) and entry.get("bornInLat") is not None and entry.get("bornInLat") != -14.0:
            return entry
            
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{person_qid}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get(person_qid, {})
        claims = entity.get("claims", {})
        
        for prop in ["P19", "P740", "P937"]:
            prop_claims = claims.get(prop, [])
            if prop_claims:
                place_qid = prop_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                if place_qid:
                    time.sleep(0.05)
                    coords_data = resolve_place_coords(place_qid, cache)
                    if coords_data:
                        cache[person_qid] = coords_data
                        return coords_data
    except Exception as e:
        print(f"    [Error] Person birthplace resolution error for {person_qid}: {e}")
    return None

def fetch_wikipedia_birthplace(wiki_title, cache):
    url = f"https://en.wikipedia.org/w/api.php?action=parse&page={urllib.parse.quote(wiki_title)}&prop=text&section=0&format=json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            html = data.get("parse", {}).get("text", {}).get("*", "")
            
            # Find class="birthplace" inside infobox
            bp_match = re.search(r'<(div|span)[^>]*class="birthplace"[^>]*>(.*?)</\1>', html, re.DOTALL | re.IGNORECASE)
            if bp_match:
                bp_html = bp_match.group(2)
                clean_name = clean_tags(bp_html)
                
                # Check for first link title inside the birthplace HTML
                link_match = re.search(r'href="/wiki/([^"#\s]+)"', bp_html)
                link_title = None
                if link_match:
                    link_title = urllib.parse.unquote(link_match.group(1)).replace("_", " ")
                    
                return {"cleanName": clean_name, "linkTitle": link_title}
                
            # Fallback: search for "Born</th>" cell and try to find a link after dates
            born_match = re.search(r'<th[^>]*>Born</th>\s*<td[^>]*>(.*?)</td>', html, re.DOTALL | re.IGNORECASE)
            if born_match:
                born_html = born_match.group(1)
                # Find all links
                links = re.findall(r'href="/wiki/([^"#\s]+)"', born_html)
                for l in links:
                    l_unquoted = urllib.parse.unquote(l).replace("_", " ")
                    # Skip common biographical links that aren't places
                    if any(skip in l_unquoted.lower() for skip in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "baptis", "citation", "birth", "christen"]):
                        continue
                    clean_name = clean_tags(born_html)
                    # Use the first valid place-like link
                    return {"cleanName": clean_name, "linkTitle": l_unquoted}
                    
    except Exception as e:
        print(f"    [Error] Wikipedia parse error for {wiki_title}: {e}")
    return None

def main():
    print("=" * 60)
    print("      BBC DESERT ISLAND DISCS - UNRESOLVED REFINEMENT PIPELINE")
    print("=" * 60)
    
    if not os.path.exists(DATABASE_FILE):
        print(f"Error: {DATABASE_FILE} not found.")
        return
        
    with open(DATABASE_FILE, "r", encoding="utf-8") as f:
        castaways = json.load(f)
        
    cache = load_cache()
    lowercase_index = build_lowercase_index(cache)
    print(f"Loaded {len(castaways)} castaways.")
    print(f"Loaded {len(cache)} entries from geocache. Built lowercase place name index of {len(lowercase_index)} entries.")
    
    unresolved_entries = [c for c in castaways if c.get("bornInLat") == -14.0 and c.get("bornInLng") == -13.0]
    print(f"\nFound {len(unresolved_entries)} unresolved \"Desert Island\" entries in the database.")
    
    if not unresolved_entries:
        print("🎉 No unresolved entries to process!")
        return
        
    resolved_count = 0
    saved_count = 0
    
    for idx, c in enumerate(unresolved_entries, 1):
        name = c["name"]
        wiki_url = c.get("wikipediaUrl")
        
        print(f"\n[{idx}/{len(unresolved_entries)}] Refining: '{name}'...")
        
        success = False
        born_in = "Desert Island"
        lat = -14.0
        lng = -13.0
        
        # 1. Extraction from Wikipedia Infobox
        if wiki_url:
            wiki_title = urllib.parse.unquote(wiki_url.split("/wiki/")[-1])
            print(f"  -> Fetching Wikipedia birthplace details for: {wiki_title}...")
            bp_info = fetch_wikipedia_birthplace(wiki_title, cache)
            
            if bp_info:
                clean_name = bp_info["cleanName"]
                link_title = bp_info["linkTitle"]
                print(f"    * Extracted birthplace: \"{clean_name}\" | Link: \"{link_title}\"")
                
                # A. Try to find in cache directly by Link Title or Full Name or their lowercase segments
                geo_data = None
                
                # Check link title directly in lowercase index
                if link_title:
                    lt_clean = link_title.strip().lower()
                    if lt_clean in lowercase_index:
                        geo_data = {"bornIn": clean_name, "bornInLat": lowercase_index[lt_clean]["lat"], "bornInLng": lowercase_index[lt_clean]["lng"]}
                
                # Check clean name directly in lowercase index
                if not geo_data and clean_name:
                    cn_clean = clean_name.strip().lower()
                    if cn_clean in lowercase_index:
                        geo_data = {"bornIn": clean_name, "bornInLat": lowercase_index[cn_clean]["lat"], "bornInLng": lowercase_index[cn_clean]["lng"]}
                
                # Check comma-separated parts of clean name in lowercase index
                if not geo_data and clean_name:
                    parts = [p.strip().lower() for p in clean_name.split(",")]
                    for p in parts:
                        if p and p in lowercase_index:
                            geo_data = {"bornIn": clean_name, "bornInLat": lowercase_index[p]["lat"], "bornInLng": lowercase_index[p]["lng"]}
                            break
                            
                # Fallback to direct keys in original cache
                if not geo_data:
                    for key in [link_title, clean_name]:
                        if key and key in cache:
                            entry = cache[key]
                            if isinstance(entry, dict) and "lat" in entry:
                                geo_data = {"bornIn": clean_name, "bornInLat": entry["lat"], "bornInLng": entry["lng"]}
                                break
                            elif isinstance(entry, dict) and "bornInLat" in entry:
                                geo_data = {"bornIn": clean_name, "bornInLat": entry["bornInLat"], "bornInLng": entry["bornInLng"]}
                                break
                            
                if geo_data:
                    born_in = geo_data["bornIn"]
                    lat = geo_data["bornInLat"]
                    lng = geo_data["bornInLng"]
                    success = True
                    print(f"    [Cache Hit] Coordinates: {born_in} ({lat}, {lng})")
                else:
                    # B. Fetch from Wikidata using Link Title
                    if link_title:
                        time.sleep(0.1)
                        link_qid = get_wikidata_qid(link_title)
                        if link_qid:
                            time.sleep(0.1)
                            place_data = resolve_place_coords(link_qid, cache)
                            if place_data:
                                born_in = clean_name
                                lat = place_data["bornInLat"]
                                lng = place_data["bornInLng"]
                                success = True
                                print(f"    [Wikidata Place Hit] Coordinates: {born_in} ({lat}, {lng})")
                                
        # 2. Fallback to direct Wikidata QID check for Person (in case rate limit had blocked it last time)
        if not success and wiki_url:
            wiki_title = urllib.parse.unquote(wiki_url.split("/wiki/")[-1])
            time.sleep(0.1)
            person_qid = get_wikidata_qid(wiki_title)
            if person_qid:
                time.sleep(0.1)
                loc_data = get_person_birthplace_coords(person_qid, cache)
                if loc_data:
                    born_in = loc_data.get("bornIn", "Desert Island")
                    lat = loc_data.get("bornInLat", -14.0)
                    lng = loc_data.get("bornInLng", -13.0)
                    if lat != -14.0:
                        success = True
                        print(f"    [Wikidata Person Hit] Coordinates: {born_in} ({lat}, {lng})")
                        
        if success:
            c["bornIn"] = born_in
            c["bornInLat"] = lat
            c["bornInLng"] = lng
            resolved_count += 1
            print(f"  -> SUCCESS! Mapped '{name}' to {born_in} ({lat}, {lng})")
        else:
            print(f"  -> Unresolved birthplace for '{name}'. Remaining at Desert Island (-14, -13).")
            
        # Save progress incrementally
        if resolved_count > 0 and resolved_count % 10 == 0:
            print(f"\n  [Checkpoint] Saving updated database and cache...")
            save_cache(cache)
            with open(DATABASE_FILE, "w", encoding="utf-8") as f_out:
                json.dump(castaways, f_out, indent=2, ensure_ascii=False)
                
        # Small delay to respect server
        time.sleep(0.1)
        
    # Final Save
    save_cache(cache)
    with open(DATABASE_FILE, "w", encoding="utf-8") as f_out:
        json.dump(castaways, f_out, indent=2, ensure_ascii=False)
        
    print("\n--- PIPELINE RESOLUTION SUMMARY ---")
    print(f"Total processed unresolved entries: {len(unresolved_entries)}")
    print(f"Successfully refined & geocoded: {resolved_count} ({resolved_count/len(unresolved_entries)*100:.1f}%)")
    print(f"Remaining unresolved: {len(unresolved_entries) - resolved_count}")
    print("Database data.json updated successfully!")

if __name__ == "__main__":
    main()
