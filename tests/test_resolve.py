import urllib.request
import urllib.parse
import json
import ssl
import re

ssl_context = ssl._create_unverified_context()
HEADERS = {"User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"}

def clean_guest_name(name):
    # 1. Remove "Classic " prefix
    name = re.sub(r'^(Classic\s+)', '', name, flags=re.IGNORECASE).strip()
    # 2. Split by comma and take first part (removes suffixes like ", cook")
    name = name.split(",")[0].strip()
    # 3. Strip common prefix titles
    name = re.sub(r'^(Professor|Prof\b|Dr|Sir|Dame|Lady|Lord|Rt\s+Hon|Rt\.\s+Hon\.)\s+', '', name, flags=re.IGNORECASE).strip()
    # 4. Strip common trailing titles
    name = re.sub(r'\s+(MP|CBE|OBE|MBE|KBE|DBE|FRS)$', '', name, flags=re.IGNORECASE).strip()
    return name

def search_wikipedia(name):
    clean_name = clean_guest_name(name)
    print(f"  -> Cleaned Name: '{clean_name}'")
    
    # Search for the person directly
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(clean_name)}&srlimit=3&format=json"
    
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("query", {}).get("search", [])
            if results:
                # We return the first result
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

def get_birthplace_and_coords(qid):
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
                    
        return born_in_name, lat, lng
    except Exception as e:
        print(f"Error fetching coordinates for QID '{qid}': {e}")
    return None, None, None

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

def test():
    test_guests = [
        "Classic  Arsène Wenger",
        "Classic  Dame Donna Langley",
        "Classic  Thom Yorke",
        "Classic  Dr Jane Goodall"
    ]
    
    print("--- DEMO WIKIPEDIA/WIKIDATA HYBRID RESOLVER ---")
    for guest in test_guests:
        print(f"\nResolving guest: '{guest}'")
        title = search_wikipedia(guest)
        if not title:
            print("  -> Could not find Wikipedia article.")
            continue
        print(f"  -> Found Wikipedia article: '{title}'")
        
        qid = get_wikidata_qid(title)
        if not qid:
            print("  -> Could not find Wikidata QID.")
            continue
        print(f"  -> Wikidata QID: {qid}")
        
        born_in, lat, lng = get_birthplace_and_coords(qid)
        print(f"  -> Result: Birthplace: {born_in} | Lat: {lat} | Lng: {lng}")

if __name__ == "__main__":
    test()
