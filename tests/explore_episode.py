import urllib.request
import json
import ssl

ssl_context = ssl._create_unverified_context()

def explore():
    # Fetch the episode's Wikidata JSON data
    url = "https://www.wikidata.org/wiki/Special:EntityData/Q114717235.json"
    headers = {"User-Agent": "DesertIslandDiscsExplorer/1.0"}
    req = urllib.request.Request(url, headers=headers)
    
    print("Fetching Desert Island Discs Episode Q114717235 JSON...")
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get("Q114717235", {})
        claims = entity.get("claims", {})
        
        print(f"Total claims found on episode: {len(claims)}")
        
        # Print all statements and properties
        for prop_id, statements in claims.items():
            for stmt in statements:
                datavalue = stmt.get("mainsnak", {}).get("datavalue", {})
                val_type = datavalue.get("type")
                if val_type == "wikibase-entityid":
                    target_qid = datavalue.get("value", {}).get("id")
                    print(f"  - Property {prop_id} links to QID {target_qid}")
                elif val_type == "string":
                    target_str = datavalue.get("value")
                    print(f"  - Property {prop_id} has string value: '{target_str}'")
                    
    except Exception as e:
        print(f"Error exploring Wikidata: {e}")

if __name__ == "__main__":
    explore()
