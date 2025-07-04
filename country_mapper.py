import csv

input_file = 'onion_vs_clearnet_comparison_with_relays.csv'
output_file = 'tor_relays_filled.csv'

ip_to_country = {}

def parse_relay_entry(entry):
    parts = entry.strip().split(':')
    if len(parts) == 4:
        return {
            "fingerprint": parts[0],
            "nickname": parts[1],
            "ip": parts[2],
            "country": parts[3]
        }
    return None

def reconstruct_entry(relay):
    return f"{relay['fingerprint']}:{relay['nickname']}:{relay['ip']}:{relay['country']}"

# Step 1: Load and map known IP → Country
with open(input_file, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    rows = list(reader)

    for row in rows:
        relays = row.get("Circuit Relays (Onion only)", "")
        for relay_entry in relays.split(";"):
            relay = parse_relay_entry(relay_entry)
            if relay and relay["country"] and relay["country"].lower() != "unknown":
                ip_to_country[relay["ip"]] = relay["country"]

# Step 2: Fill in Unknown entries
for row in rows:
    relays = row.get("Circuit Relays (Onion only)", "")
    new_relays = []
    for relay_entry in relays.split(";"):
        relay = parse_relay_entry(relay_entry)
        if relay:
            if not relay["country"] or relay["country"].lower() == "unknown":
                if relay["ip"] in ip_to_country:
                    relay["country"] = ip_to_country[relay["ip"]]
            new_relays.append(reconstruct_entry(relay))
    row["Circuit Relays (Onion only)"] = "; ".join(new_relays)

# Step 3: Write updated data
with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Relay countries filled and saved to: {output_file}")
