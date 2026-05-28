import urllib.request
import json
import ssl

ssl_context = ssl._create_unverified_context()

def explore():
    # Fetch David Attenborough's Wikidata JSON data
    url = "https://www.wikidata.org/wiki/Special:EntityData/Q183337.json"
    headers = {"User-Agent": "DesertIslandDiscsExplorer/1.0"}
    req = urllib.request.Request(url, headers=headers)
    
    print("Fetching David Attenborough's Wikidata JSON...")
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        entity = data.get("entities", {}).get("Q183337", {})
        claims = entity.get("claims", {})
        
        print(f"Total claims found: {len(claims)}")
        
        # Search for any references to Desert Island Discs (Q1200587) in the claims
        found = False
        for prop_id, statements in claims.items():
            for stmt in statements:
                # Check main value
                datavalue = stmt.get("mainsnak", {}).get("datavalue", {})
                if datavalue.get("type") == "wikibase-entityid":
                    target_qid = datavalue.get("value", {}).get("id")
                    if target_qid == "Q1200587":
                        print(f"-> Found direct link to Q1200587 via Property {prop_id}!")
                        found = True
                        
                # Check qualifiers
                qualifiers = stmt.get("qualifiers", {})
                for qual_prop_id, qual_list in qualifiers.items():
                    for qual in qual_list:
                        qual_val = qual.get("datavalue", {})
                        if qual_val.get("type") == "wikibase-entityid":
                            target_qid = qual_val.get("value", {}).get("id")
                            if target_qid == "Q1200587":
                                print(f"-> Found qualifier link to Q1200587 in Property {prop_id} via Qualifier {qual_prop_id}!")
                                found = True
                                
        if not found:
            print("No direct statement linking David Attenborough (Q183337) to Desert Island Discs (Q1200587) found on his main item page.")
            print("Checking a few common properties...")
            # Let's inspect "present in work" (P1441)
            if "P1441" in claims:
                print("Present in work (P1441) statement values:")
                for stmt in claims["P1441"]:
                    val = stmt.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    print(f"  - {val}")
            # Let's inspect "participant in" (P1344)
            if "P1344" in claims:
                print("Participant in (P1344) statement values:")
                for stmt in claims["P1344"]:
                    val = stmt.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    print(f"  - {val}")
                    
    except Exception as e:
        print(f"Error exploring Wikidata: {e}")

if __name__ == "__main__":
    explore()
