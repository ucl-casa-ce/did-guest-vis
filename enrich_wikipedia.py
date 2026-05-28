import json
import urllib.request
import urllib.parse
import ssl
import time
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = "data.json"
ssl_context = ssl._create_unverified_context()
HEADERS = {"User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"}

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

def search_wikipedia_url(name):
    clean_name = clean_guest_name(name)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(clean_name)}&srlimit=3&format=json"
    
    req = urllib.request.Request(url, headers=HEADERS)
    
    # Polite sleep delay to respect Wikipedia crawler guidelines
    time.sleep(0.1)
    
    # Retry up to 3 times with progressive backoff to handle transient HTTP 429s or timeouts
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
                data = json.loads(response.read().decode("utf-8"))
                results = data.get("query", {}).get("search", [])
                if results:
                    title = results[0]["title"]
                    # Return standard Wikipedia URL formatted cleanly
                    return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                return None
        except Exception as e:
            if attempt == 2:
                print(f"Error searching Wikipedia for '{name}': {e}")
                return None
            # Progressive backoff delay
            time.sleep(2 + attempt * 2)
    return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        castaways = json.load(f)
        
    print(f"Loaded {len(castaways)} castaways.")
    
    # Filter those that need Wikipedia URLs
    todo = []
    for idx, c in enumerate(castaways):
        if "wikipediaUrl" not in c or c["wikipediaUrl"] is None:
            todo.append((idx, c["name"]))
                
    print(f"Found {len(todo)} castaways needing Wikipedia URL enrichment.")
    
    if not todo:
        print("All castaways already enriched with Wikipedia URLs.")
        return
        
    max_workers = 2
    completed = 0
    
    print(f"Starting parallel fetch with {max_workers} threads...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(search_wikipedia_url, name): idx for idx, name in todo}
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                wiki_url = future.result()
                castaways[idx]["wikipediaUrl"] = wiki_url
            except Exception:
                castaways[idx]["wikipediaUrl"] = None
                
            completed += 1
            if completed % 100 == 0 or completed == len(todo):
                print(f"Progress: {completed}/{len(todo)} enriched...")
                # Write backup incrementally
                with open(INPUT_FILE, "w", encoding="utf-8") as f_out:
                    json.dump(castaways, f_out, indent=2, ensure_ascii=False)
                    
    # Final save
    with open(INPUT_FILE, "w", encoding="utf-8") as f_out:
        json.dump(castaways, f_out, indent=2, ensure_ascii=False)
        
    print("Wikipedia URL enrichment complete and saved successfully!")

if __name__ == "__main__":
    main()
