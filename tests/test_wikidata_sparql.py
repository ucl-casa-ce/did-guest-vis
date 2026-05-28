import json
import urllib.request
import urllib.parse
import ssl

SPARQL_URL = "https://query.wikidata.org/sparql"
ssl_context = ssl._create_unverified_context()

def run_query():
    # We trace from episode -> castaway (P5030) -> birthplace (P19) -> coordinates (P625)
    # We remove the expensive label service to make this query execute instantly.
    query = """
    SELECT ?person ?bornIn ?coords WHERE {
      # Find episodes that are part of the Desert Island Discs series (Q1200587)
      ?episode wdt:P179 wd:Q1200587 .
      
      # Find the guest / castaway of that episode
      ?episode wdt:P5030 ?person .
      
      # Birthplace and its coordinates
      ?person wdt:P19 ?bornIn .
      ?bornIn wdt:P625 ?coords .
    }
    """
    
    print("Running Wikidata SPARQL query...")
    params = urllib.parse.urlencode({"query": query, "format": "json"})
    
    # Custom headers to identify request and avoid standard crawler blocks
    req = urllib.request.Request(
        f"{SPARQL_URL}?{params}",
        headers={"User-Agent": "DesertIslandDiscsExplorer/1.0 (contact: dunc@dropbox.antigrav)"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            result = json.loads(response.read().decode("utf-8"))
            bindings = result.get("results", {}).get("bindings", [])
            print(f"Query successful! Found {len(bindings)} castaway records on Wikidata with birth coordinates.")
            
            # Print a few samples
            print("\n--- Samples from Wikidata ---")
            for b in bindings[:10]:
                person_url = b.get("person", {}).get("value")
                born_in_url = b.get("bornIn", {}).get("value")
                coords = b.get("coords", {}).get("value")
                
                person_qid = person_url.split("/")[-1] if person_url else ""
                born_in_qid = born_in_url.split("/")[-1] if born_in_url else ""
                print(f"Person QID: {person_qid} | Born In QID: {born_in_qid} | Coords: {coords}")
                
    except Exception as e:
        print(f"Error running SPARQL query: {e}")

if __name__ == "__main__":
    run_query()
