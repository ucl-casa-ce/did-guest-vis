import json
import urllib.request
import xml.etree.ElementTree as ET
import ssl
import re
from datetime import datetime

RSS_FEED_URL = "https://podcasts.files.bbci.co.uk/b006qnmr.rss"
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
    
    # Split into sentences using punctuation followed by spaces
    sentences = re.split(r'\. |\? |\! ', text)
    
    lives_in = None
    born_in = None
    grew_up_in = None
    
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
        
        # 1. Match current residence
        match_lives = re.search(
            r'\blives\b.*?\bin\s+(?:the\s+)?([A-Z][A-Za-z\s\-]+(?:\b[A-Z][A-Za-z\s\-]+)*)', 
            sentence_clean
        )
        if match_lives and not lives_in:
            candidate = clean_location(match_lives.group(1))
            if candidate:
                lives_in = candidate
                
        # 2. Match birthplace
        match_born = re.search(
            r'\bborn\b.*?\bin\s+(?:the\s+)?([A-Z][A-Za-z\s\-]+(?:\b[A-Z][A-Za-z\s\-]+)*)', 
            sentence_clean
        )
        if match_born and not born_in:
            candidate = clean_location(match_born.group(1))
            if candidate:
                born_in = candidate

        # 3. Match grew up
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

def parse_rss_feed():
    print(f"Connecting to BBC Desert Island Discs RSS feed...")
    print(f"URL: {RSS_FEED_URL}")
    
    # Configure request with a standard browser User-Agent
    # (BBC servers may block or rate-limit default Python headers)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(RSS_FEED_URL, headers=headers)
    
    # Bypass macOS default SSL certificate verification issues
    context = ssl._create_unverified_context()
    
    try:
        print("Downloading RSS XML feed (this can be several megabytes, please wait)...")
        with urllib.request.urlopen(req, timeout=60, context=context) as response:
            xml_data = response.read()
        print(f"Download complete. Received {len(xml_data) / 1024 / 1024:.2f} MB of data.")
    except Exception as e:
        print(f"Error downloading the RSS feed: {e}")
        return

    print("Parsing XML structure...")
    try:
        # Standard XML parser
        root = ET.fromstring(xml_data)
    except Exception as e:
        print(f"Error parsing XML content: {e}")
        return

    # Find all <item> tags representing episodes
    items = root.findall(".//item")
    print(f"Found {len(items)} raw episodes in RSS feed. Processing...")

    castaways = []
    skipped_count = 0

    for index, item in enumerate(items, 1):
        try:
            # Extract basic tags
            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")
            desc_el = item.find("description")
            
            title = title_el.text if title_el is not None else ""
            episode_url = link_el.text if link_el is not None else ""
            pub_date_str = pub_date_el.text if pub_date_el is not None else ""
            description = desc_el.text if desc_el is not None else ""
            
            # 1. Clean the guest name from the episode title
            # Titles are usually "Desert Island Discs: David Beckham" or "Desert Island Discs - David Beckham"
            guest_name = title.replace("Desert Island Discs:", "")
            guest_name = guest_name.replace("Desert Island Discs -", "")
            guest_name = guest_name.replace("Desert Island Discs", "")
            guest_name = guest_name.strip()
            
            # Skip placeholders, highlights, compilations, or promotional entries
            if not guest_name or any(kw in guest_name.lower() for kw in ["compilation", "anniversary", "intro", "selection", "highlight", "special", "episode"]):
                skipped_count += 1
                continue

            # 2. Format the publication date into a clean string (e.g. "29 Jan 2017")
            # Typical pubDate format: "Sun, 29 Jan 2017 12:00:00 GMT" or "Sun, 29 Jan 2017 12:00:00 +0000"
            broadcast_date = pub_date_str
            if pub_date_str:
                try:
                    # Parse the first 25 characters to ignore timezone offsets
                    clean_date = pub_date_str[:25].strip()
                    dt = datetime.strptime(clean_date, "%a, %d %b %Y %H:%M:%S")
                    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    broadcast_date = f"{dt.day} {months[dt.month-1]} {dt.year}"
                except Exception:
                    pass

            # 3. Clean and shorten the description if necessary
            clean_desc = description.strip() if description else ""

            # 4. Construct a unique ID slug
            guest_slug = guest_name.lower().replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")

            # Extract location details
            locs = extract_locations(clean_desc)

            castaway_record = {
                "id": guest_slug,
                "name": guest_name,
                "broadcastDate": broadcast_date,
                "episodeUrl": episode_url,
                "description": clean_desc,
                "bornIn": locs["bornIn"],
                "bornInLat": None,
                "bornInLng": None
            }

            castaways.append(castaway_record)

            if index % 200 == 0:
                print(f"  Processed {index}/{len(items)} episodes...")

        except Exception as e:
            print(f"  Error processing item #{index}: {e}")
            continue

    print(f"\nProcessing complete!")
    print(f"Total processed castaways: {len(castaways)}")
    print(f"Skipped compilation/special items: {skipped_count}")

    # Write out as JSON data
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(castaways, f, indent=2, ensure_ascii=False)
        print(f"Successfully generated database: {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving data.json: {e}")

if __name__ == "__main__":
    parse_rss_feed()
