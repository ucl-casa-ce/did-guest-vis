import urllib.request
import urllib.parse
import json
import ssl

ssl_context = ssl._create_unverified_context()

def get_category_members():
    url = "https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Desert_Island_Discs&cmlimit=500&format=json"
    headers = {"User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"}
    
    req = urllib.request.Request(url, headers=headers)
    
    print("Connecting to Wikipedia API...")
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        members = data.get("query", {}).get("categorymembers", [])
        print(f"Successfully fetched {len(members)} category members in first request!")
        
        print("\n--- First 10 page titles ---")
        for m in members[:10]:
            print(f"Title: {m.get('title')} | PageID: {m.get('pageid')}")
            
    except Exception as e:
        print(f"Error fetching from Wikipedia API: {e}")

if __name__ == "__main__":
    get_category_members()
