import requests
import csv

INPUT_CSV = "tranco_daily_top20k.csv"
OUTPUT_CSV = "onion_locations_found.csv"
TIMEOUT = 10

def get_onion_header(domain):
    url = f"https://{domain.strip()}"
    try:
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
        onion_url = response.headers.get("Onion-Location")
        if onion_url and ".onion" in onion_url:
            return onion_url
    except Exception as e:
        print(f"[!] Error checking {url}: {e}")
    return None

def main():
    with open(INPUT_CSV, "r", encoding="utf-8") as infile, \
         open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        writer.writerow(["Clear Web Domain", "Onion Address"])
        
        for row in reader:
            domain = row[1].strip()
            if not domain:
                continue
            print(f"Checking {domain}")
            onion = get_onion_header(domain)
            if onion:
                print(f"{domain} → {onion}")
                writer.writerow([domain, onion])
            else:
                print(f"No Onion header for {domain}")

if __name__ == "__main__":
    main()
