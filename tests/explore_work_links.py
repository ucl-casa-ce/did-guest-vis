import json
import urllib.request
import urllib.parse
import ssl

SPARQL_URL = "https://query.wikidata.org/sparql"
ssl_context = ssl._create_unverified_context()

def run_query():
    # Find any item in Wikidata that points to Desert Island Discs (Q1200587) using any property
    query = """
    SELECT ?item ?itemLabel ?property ?propertyLabel WHERE {
      ?item ?property wd:Q1200587 .
      
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    LIMIT 20
    """
    
    print("Running exploratory SPARQL query on Q1200587...")
    params = urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(
        f"{SPARQL_URL}?{params}",
        headers={"User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            result = json.loads(response.read().decode("utf-8"))
            bindings = result.get("results", {}).get("bindings", [])
            print(f"Found {len(bindings)} incoming links to Desert Island Discs (Q1200587):")
            
            print("\n--- Links found ---")
            for b in bindings:
                item_url = b.get("item", {}).get("value")
                item_lbl = b.get("itemLabel", {}).get("value")
                prop_url = b.get("property", {}).get("value")
                
                # Extract simple property name or QID
                prop_id = prop_url.split("/")[-1] if prop_url else ""
                item_id = item_url.split("/")[-1] if item_url else ""
                
                print(f"Item: {item_lbl} ({item_id}) | Property: {prop_id}")
                
    except Exception as e:
        print(f"Error exploring SPARQL: {e}")

if __name__ == "__main__":
    run_query()
