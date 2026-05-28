import json
import urllib.request
import urllib.parse
import time
import os
import ssl

INPUT_FILE = "data.json"
CACHE_FILE = "geocache.json"

# Configure standard SSL context bypass for macOS certificate issues
ssl_context = ssl._create_unverified_context()

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

def geocode_location(loc_name, cache):
    if not loc_name:
        return None
        
    # Standardize name for cache lookup
    loc_clean = loc_name.strip()
    if loc_clean in cache:
        return cache[loc_clean]
        
    print(f"Geocoding online: '{loc_clean}'...")
    
    # OpenStreetMap Nominatim Search URL
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(loc_clean)}&format=json&limit=1"
    
    # OSM Nominatim requires a distinct, descriptive User-Agent
    headers = {
        "User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data:
                    lat = float(data[0]["lat"])
                    lng = float(data[0]["lon"])
                    result = {"lat": lat, "lng": lng}
                    cache[loc_clean] = result
                    save_cache(cache)
                    print(f"  -> Found: {lat}, {lng}")
                    return result
                else:
                    print(f"  -> Location not found in geocoder.")
                    cache[loc_clean] = None
                    save_cache(cache)
                    return None
    except Exception as e:
        print(f"  -> Error geocoding '{loc_clean}': {e}")
        return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        castaways = json.load(f)
        
    print(f"Loaded {len(castaways)} castaways.")
    
    # 1. Collect all unique locations
    unique_locations = set()
    for c in castaways:
        if c.get("bornIn"):
            unique_locations.add(c["bornIn"].strip())
        if c.get("livesIn"):
            unique_locations.add(c["livesIn"].strip())
            
    print(f"Found {len(unique_locations)} unique location names to geocode.")
    
    # Load cache to minimize network requests
    cache = load_cache()
    print(f"Loaded {len(cache)} cached locations.")
    
    # 2. Geocode only locations not in cache or missing
    newly_geocoded = 0
    for idx, loc in enumerate(sorted(list(unique_locations)), 1):
        if loc not in cache:
            # Respect OSM Nominatim Usage Policy (max 1 request per second)
            time.sleep(1.5)
            geocode_location(loc, cache)
            newly_geocoded += 1
            if newly_geocoded >= 35: # Batching limit to keep the turn fast
                print(f"Reached batch limit of 35 new API requests in this run. We will save current progress and you can re-run.")
                break
                
    # 3. Restructure database: keep ONLY bornIn, livesIn and their lat/lng
    simplified_castaways = []
    
    geocoded_lives_count = 0
    geocoded_born_count = 0
    
    for c in castaways:
        born_in = c.get("bornIn")
        lives_in = c.get("livesIn")
        
        born_coords = cache.get(born_in) if born_in else None
        lives_coords = cache.get(lives_in) if lives_in else None
        
        born_lat = born_coords["lat"] if born_coords else None
        born_lng = born_coords["lng"] if born_coords else None
        
        lives_lat = lives_coords["lat"] if lives_coords else None
        lives_lng = lives_coords["lng"] if lives_coords else None
        
        if born_lat is not None:
            geocoded_born_count += 1
        if lives_lat is not None:
            geocoded_lives_count += 1
            
        record = {
            "id": c.get("id"),
            "name": c.get("name"),
            "broadcastDate": c.get("broadcastDate"),
            "episodeUrl": c.get("episodeUrl"),
            "description": c.get("description"),
            "bornIn": born_in,
            "bornInLat": born_lat,
            "bornInLng": born_lng,
            "livesIn": lives_in,
            "livesInLat": lives_lat,
            "livesInLng": lives_lng
        }
        simplified_castaways.append(record)
        
    # Write simplified and enriched database
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(simplified_castaways, f, indent=2, ensure_ascii=False)
        
    print("\n--- SIMPLIFICATION SUMMARY ---")
    print(f"Saved restructured database with kept fields (bornIn, livesIn).")
    print(f"Total entries: {len(simplified_castaways)}")
    print(f"Castaways with geocoded Birthplace ('bornIn'): {geocoded_born_count}")
    print(f"Castaways with geocoded Residence ('livesIn'): {geocoded_lives_count}")

if __name__ == "__main__":
    main()
