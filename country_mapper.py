import csv
import requests
import time

INPUT_OUTPUT_CSV = "onion_vs_clearnet_comparison_with_relays copy.csv"
IPINFO_URL = "https://ipinfo.io/{}/country"
RATE_LIMIT_DELAY = 1  # seconds between requests to avoid rate-limits

def lookup_country(ip):
    try:
        resp = requests.get(IPINFO_URL.format(ip), timeout=5)
        if resp.status_code == 200:
            country = resp.text.strip()
            if country:
                return country
            else:
                print(f"[!] Empty country response for IP {ip}")
        else:
            print(f"[!] HTTP {resp.status_code} for IP {ip}: {resp.text.strip()}")
    except requests.exceptions.Timeout:
        print(f"[!] Timeout error for IP {ip}")
    except requests.exceptions.ConnectionError:
        print(f"[!] Connection error for IP {ip}")
    except Exception as e:
        print(f"[!] Unexpected error for IP {ip}: {e}")
    return None

def process_csv(file_path):
    updated_rows = []
    to_lookup = {}

    # 1. Read and parse existing CSV, identify relays with Unknown country
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row_num, row in enumerate(reader, start=2):  # start=2 to match actual CSV line number
            relays = row[9]  # "Circuit Relays (Onion only)"
            if relays:
                parts = [r.strip() for r in relays.split(';') if r.strip()]
                updated_parts = []
                for part in parts:
                    try:
                        fp, nick, ip, country = part.split(':')
                    except ValueError:
                        print(f"[!] Malformed relay entry in line {row_num}, skipped: '{part}'")
                        continue
                    ip = ip.strip()
                    country = country.strip()
                    if country.upper() == "UNKNOWN" and ip:
                        to_lookup[ip] = None
                    updated_parts.append([fp, nick, ip, country])
                row[9] = updated_parts
            updated_rows.append(row)

    # 2. Lookup missing country codes
    for ip in list(to_lookup):
        print(f"[*] Looking up IP {ip} ...")
        country = lookup_country(ip)
        if country:
            to_lookup[ip] = country
            print(f"[+] IP {ip} → {country}")
        else:
            print(f"[!] Could not look up country for IP {ip}")
        time.sleep(RATE_LIMIT_DELAY)

    # 3. Replace Unknown and reconstruct CSV rows
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in updated_rows:
            parts = row[9]
            if isinstance(parts, list):
                new_relays_str = "; ".join(
                    f"{fp}:{nick}:{ip}:{to_lookup[ip] if country.upper() == 'UNKNOWN' and to_lookup.get(ip) else country}"
                    for fp, nick, ip, country in parts
                )
                row[9] = new_relays_str
            writer.writerow(row)

if __name__ == "__main__":
    process_csv(INPUT_OUTPUT_CSV)
    print("✅ Country codes updated in place.")
