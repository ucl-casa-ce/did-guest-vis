import json
import re
import os

INPUT_FILE = "data.json"
OUTPUT_FILE = "data.json"

def clean_html(text):
    if not text:
        return ""
    # Strip HTML tags
    clean = re.compile('<.*?>')
    return re.sub(clean, ' ', text)

def extract_locations(description):
    if not description:
        return {"livesIn": None, "bornIn": None, "grewUpIn": None}
        
    # Clean tags and normalize spaces
    text = clean_html(description)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Split into sentences using punctuation followed by spaces and capital letters
    sentences = re.split(r'\. |\? |\! ', text)
    
    lives_in = None
    born_in = None
    grew_up_in = None
    
    # Helper to clean extracted location names
    def clean_location(loc):
        if not loc:
            return None
        # Remove common trailing noise words or connectors that slip into capital letter groups
        noise_split = re.split(r'\b(with|and|his|her|their|divided|divides|for|where|since|after|as|who|to|at|on|when|in|during|she|he|they|the|from|but|before|until|while|by|into)\b', loc, flags=re.IGNORECASE)
        loc = noise_split[0].strip()
        # Remove trailing punctuation or symbols
        loc = re.sub(r'[\.,;:\-\s]+$', '', loc).strip()
        loc = re.sub(r'^[\.,;:\-\s]+', '', loc).strip()
        # Ensure it starts with an uppercase letter and is at least 2 chars long
        if loc and len(loc) >= 2 and loc[0].isupper():
            return loc
        return None

    for sentence in sentences:
        sentence_clean = sentence.strip()
        
        # 1. Match current residence: "lives in [Location]" or "lives with ... in [Location]"
        # Matches "lives in London", "lives with her family in Sussex", "lives in the Lake District"
        # We capture capitalized words (which represent proper nouns of cities, towns, counties, or countries)
        match_lives = re.search(
            r'\blives\b.*?\bin\s+(?:the\s+)?([A-Z][A-Za-z\s\-]+(?:\b[A-Z][A-Za-z\s\-]+)*)', 
            sentence_clean
        )
        if match_lives and not lives_in:
            candidate = clean_location(match_lives.group(1))
            if candidate:
                lives_in = candidate
                
        # 2. Match birthplace: "born in [Location]"
        match_born = re.search(
            r'\bborn\b.*?\bin\s+(?:the\s+)?([A-Z][A-Za-z\s\-]+(?:\b[A-Z][A-Za-z\s\-]+)*)', 
            sentence_clean
        )
        if match_born and not born_in:
            candidate = clean_location(match_born.group(1))
            if candidate:
                born_in = candidate

        # 3. Match where they grew up / were brought up
        match_grew = re.search(
            r'\b(?:grew|brought)\s+up\b.*?\bin\s+(?:the\s+)?([A-Z][A-Za-z\s\-]+(?:\b[A-Z][A-Za-z\s\-]+)*)', 
            sentence_clean
        )
        if match_grew and not grew_up_in:
            candidate = clean_location(match_grew.group(1))
            if candidate:
                grew_up_in = candidate

    return {
        "livesIn": lives_in,
        "bornIn": born_in,
        "grewUpIn": grew_up_in
    }

def process_database(dry_run=True):
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found!")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        castaways = json.load(f)
        
    print(f"Loaded {len(castaways)} castaways from {INPUT_FILE}.")
    
    enriched_count = 0
    has_lives = 0
    has_born = 0
    has_grew = 0
    
    sample_outputs = []
    
    for i, c in enumerate(castaways):
        locs = extract_locations(c.get("description", ""))
        
        # Decide hometown: grewUpIn preferred, then bornIn
        hometown = locs["grewUpIn"] if locs["grewUpIn"] else locs["bornIn"]
        
        # Enriched indicator
        if locs["livesIn"] or hometown:
            enriched_count += 1
            if locs["livesIn"]:
                has_lives += 1
            if locs["bornIn"]:
                has_born += 1
            if locs["grewUpIn"]:
                has_grew += 1
                
        # Update record with new fields
        c["livesIn"] = locs["livesIn"]
        c["bornIn"] = locs["bornIn"]
        c["grewUpIn"] = locs["grewUpIn"]
        c["hometown"] = hometown
        
        # Keep a few samples to print
        if (locs["livesIn"] or hometown) and len(sample_outputs) < 25:
            sample_outputs.append({
                "name": c["name"],
                "bornIn": c["bornIn"],
                "grewUpIn": c["grewUpIn"],
                "livesIn": c["livesIn"],
                "hometown": c["hometown"]
            })
            
    print("\n--- SAMPLE EXTRACTED LOCATIONS ---")
    for s in sample_outputs:
        print(f"Guest: {s['name']}")
        print(f"  Born in:    {s['bornIn']}")
        print(f"  Grew up in: {s['grewUpIn']}")
        print(f"  Lives in:   {s['livesIn']}")
        print(f"  Hometown:   {s['hometown']}")
        print("-" * 40)
        
    print("\n--- STATISTICS ---")
    print(f"Total castaways processed: {len(castaways)}")
    print(f"Castaways with any location info: {enriched_count} ({enriched_count/len(castaways)*100:.1f}%)")
    print(f"  - Has 'livesIn':  {has_lives}")
    print(f"  - Has 'bornIn':   {has_born}")
    print(f"  - Has 'grewUpIn': {has_grew}")
    
    if not dry_run:
        print(f"\nSaving enriched database back to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(castaways, f, indent=2, ensure_ascii=False)
        print("Save completed successfully!")

if __name__ == "__main__":
    # Run dry run first to see statistics and verify results
    import sys
    dry = "--save" not in sys.argv
    if dry:
        print("Running in DRY RUN mode. Pass '--save' argument to update the file.")
    process_database(dry_run=dry)
