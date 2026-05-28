import json
import urllib.request
import urllib.parse
import ssl
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = "data.json"
ssl_context = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_image_pid(episode_url):
    if not episode_url:
        return None
    # Ensure url ends in .json
    url_json = episode_url.strip()
    if not url_json.endswith(".json"):
        # Remove trailing slash if any
        if url_json.endswith("/"):
            url_json = url_json[:-1]
        url_json += ".json"
    
    # Force HTTPS to be safe
    if url_json.startswith("http://"):
        url_json = "https://" + url_json[7:]
        
    req = urllib.request.Request(url_json, headers=HEADERS)
    
    # Retry up to 3 times to handle BBC rate-limiting or transient timeouts
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
                data = json.loads(response.read().decode("utf-8"))
                programme = data.get("programme", {})
                image = programme.get("image", {})
                return image.get("pid")
        except Exception as e:
            if attempt == 2:
                # Final attempt failed
                return None
            # Exponential backoff/wait
            time.sleep(1 + attempt)
    return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        castaways = json.load(f)
        
    print(f"Loaded {len(castaways)} castaways.")
    
    # Filter those that need image PIDs
    todo = []
    for idx, c in enumerate(castaways):
        if "imagePid" not in c or c["imagePid"] is None:
            # We also check if we can get it
            if c.get("episodeUrl"):
                todo.append((idx, c["episodeUrl"]))
                
    print(f"Found {len(todo)} castaways needing image PID enrichment.")
    
    if not todo:
        print("All castaways already enriched with image PIDs.")
        return
        
    # We will fetch them using a thread pool for speed
    max_workers = 15
    completed = 0
    
    print(f"Starting parallel fetch with {max_workers} threads...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks
        future_to_idx = {executor.submit(fetch_image_pid, url): idx for idx, url in todo}
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                pid = future.result()
                castaways[idx]["imagePid"] = pid
            except Exception as e:
                castaways[idx]["imagePid"] = None
                
            completed += 1
            if completed % 50 == 0 or completed == len(todo):
                print(f"Progress: {completed}/{len(todo)} enriched...")
                # Write backup incrementally
                with open(INPUT_FILE, "w", encoding="utf-8") as f_out:
                    json.dump(castaways, f_out, indent=2, ensure_ascii=False)
                    
    # Final save
    with open(INPUT_FILE, "w", encoding="utf-8") as f_out:
        json.dump(castaways, f_out, indent=2, ensure_ascii=False)
        
    print("Enrichment complete and saved successfully!")

if __name__ == "__main__":
    main()
