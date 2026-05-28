import json
import urllib.request
import urllib.parse
import ssl

SPARQL_URL = "https://query.wikidata.org/sparql"
ssl_context = ssl._create_unverified_context()

def run_query():
    # Fetch members of "Category:Desert_Island_Discs_castaways" from en.wikipedia.org
    # And join with their birthplace coordinates directly on Wikidata
    query = """
    SELECT ?item ?itemLabel ?bornInLabel ?coords WHERE {
      SERVICE wikibase:mwapi {
        bd:serviceParam wikibase:endpoint "en.wikipedia.org" .
        bd:serviceParam wikibase:api "Generator" .
        bd:serviceParam mwapi:generator "categorymembers" .
        bd:serviceParam mwapi:gcmtitle "Category:Desert_Island_Discs_castaways" .
        bd:serviceParam mwapi:gcmlimit "max" .
        
        ?item wikibase:apiOutputItem mwapi:item .
      }
      
      # Join with birthplace and birthplace coordinates on Wikidata
      ?item wdt:P19 ?bornIn .
      ?bornIn wdt:P625 ?coords .
      
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    """
    
    print("Running Wikidata category members SPARQL query...")
    params = urllib.parse.urlencode({"query": query, "format": "json"})
    
    req = urllib.request.Request(
        f"{SPARQL_URL}?{params}",
        headers={"User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45, context=ssl_context) as response:
            result = json.loads(response.read().decode("utf-8"))
            bindings = result.get("results", {}).get("bindings", [])
            print(f"Query successful! Found {len(bindings)} castaway records with coordinates.")
            
            # Print a few samples
            print("\n--- Samples from Category query ---")
            for b in bindings[:15]:
                name = b.get("itemLabel", {}).get("value")
                birthplace = b.get("bornInLabel", {}).get("value")
                coords = b.get("coords", {}).get("value")
                print(f"Name: {name} | Birthplace: {birthplace} | Coords: {coords}")
                
    except Exception as e:
        print(f"Error running category SPARQL: {e}")

if __name__ == "__main__":
    run_query()
