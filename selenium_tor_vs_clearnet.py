import csv
import time
import logging
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

INPUT_CSV = "onion_locations_found copy.csv"
OUTPUT_CSV = "performance_comparison.csv"
NUM_RUNS = 5
DELAY_BETWEEN_RUNS = 600  # 10 minutes

# Set up logging
logging.basicConfig(
    filename='performance_measurements.log',
    filemode='a',
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

def get_tor_driver():
    options = Options()
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.socks", "127.0.0.1")
    options.set_preference("network.proxy.socks_port", 9150)
    options.set_preference("network.proxy.socks_version", 5)
    options.set_preference("network.proxy.socks_remote_dns", True)
    options.headless = True
    return webdriver.Firefox(options=options)

def get_clear_driver():
    options = Options()
    options.headless = True
    return webdriver.Firefox(options=options)

def measure_timings(driver, url):
    try:
        driver.get(url)
        time.sleep(2)
        timing = driver.execute_script("return window.performance.timing")

        navigation_start = timing["navigationStart"]
        domain_lookup_start = timing["domainLookupStart"]
        domain_lookup_end = timing["domainLookupEnd"]
        connect_start = timing["connectStart"]
        connect_end = timing["connectEnd"]
        request_start = timing["requestStart"]
        response_start = timing["responseStart"]
        dom_content_loaded = timing["domContentLoadedEventEnd"]
        load_event_end = timing["loadEventEnd"]

        dns = domain_lookup_end - domain_lookup_start
        tcp = connect_end - connect_start
        tls = request_start - connect_end if "https" in url else None
        dom = dom_content_loaded - navigation_start
        page_load = load_event_end - navigation_start
        total_time = load_event_end - navigation_start

        return {
            "dns": dns,
            "tcp": tcp,
            "tls": tls,
            "dom": dom,
            "page_load": page_load,
            "total_time": total_time
        }

    except Exception as e:
        print(f"[!] Error measuring {url}: {e}")
        logging.warning(f"Error measuring {url}: {e}")
        return None
    finally:
        driver.quit()

def clean_url(url):
    return url.strip().split("#")[0].split("?")[0]

def average_metrics(metrics_list):
    avg = {}
    count = len(metrics_list)
    if count == 0:
        return None
    for key in metrics_list[0]:
        values = [m[key] for m in metrics_list if m[key] is not None]
        avg[key] = round(sum(values) / len(values), 2) if values else None
    return avg

def write_averages_to_csv(all_results, mode="w"):
    """Writes averages of collected metrics to CSV.
    mode='w' overwrites, mode='a' appends."""
    with open(OUTPUT_CSV, mode, newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        if mode == "w":
            writer.writerow([
                "Clear Domain", "Type", "URL",
                "DNS Lookup (ms)", "TCP Connect (ms)", "TLS Handshake (ms)",
                "DOMContentLoaded (ms)", "Page Load (ms)", "Total Time (ms)"
            ])

        for clear_domain, data in all_results.items():
            avg_onion = average_metrics(data['onion'])
            avg_clear = average_metrics(data['clear'])

            if avg_onion:
                writer.writerow([
                    clear_domain, "onion", data['onion_url'],
                    avg_onion["dns"], avg_onion["tcp"], avg_onion["tls"],
                    avg_onion["dom"], avg_onion["page_load"], avg_onion["total_time"]
                ])

            if avg_clear:
                writer.writerow([
                    clear_domain, "clear", data['clear_url'],
                    avg_clear["dns"], avg_clear["tcp"], avg_clear["tls"],
                    avg_clear["dom"], avg_clear["page_load"], avg_clear["total_time"]
                ])

def main():
    # Read all rows once
    with open(INPUT_CSV, "r", encoding="utf-8") as infile:
        reader = list(csv.DictReader(infile))

    # Initialize results dictionary
    all_results = {}
    for row in reader:
        clear_domain = row["Clear Web Domain"]
        all_results[clear_domain] = {
            'onion': [],
            'clear': [],
            'onion_url': clean_url(row["Onion Address"]),
            'clear_url': f"https://{clear_domain}"
        }

    # Write CSV header first (overwrite if exists)
    write_averages_to_csv(all_results, mode="w")

    for run in range(NUM_RUNS):
        print(f"\n=== Starting measurement run {run + 1} of {NUM_RUNS} ===")
        logging.info(f"Starting measurement run {run + 1} of {NUM_RUNS}")

        for clear_domain, data in all_results.items():
            onion_url = data['onion_url']
            clear_url = data['clear_url']

            # Measure onion
            print(f"\n--- Measuring ONION for {clear_domain} ---")
            logging.info(f"Measuring ONION for {clear_domain}")
            tor_driver = get_tor_driver()
            onion_metrics = measure_timings(tor_driver, onion_url)
            if onion_metrics:
                data['onion'].append(onion_metrics)

            # Measure clear web
            print(f"--- Measuring CLEAR WEB for {clear_domain} ---")
            logging.info(f"Measuring CLEAR WEB for {clear_domain}")
            clear_driver = get_clear_driver()
            clear_metrics = measure_timings(clear_driver, clear_url)
            if clear_metrics:
                data['clear'].append(clear_metrics)

        # After each run, update CSV with current averages (append mode)
        print(f"\nSaving intermediate averages to CSV after run {run + 1}...\n")
        logging.info(f"Saving intermediate averages to CSV after run {run + 1}")
        write_averages_to_csv(all_results, mode="a")

        # Wait before next run except after last run
        if run < NUM_RUNS - 1:
            print(f"\nWaiting {DELAY_BETWEEN_RUNS//60} minutes before next run...\n")
            logging.info(f"Waiting {DELAY_BETWEEN_RUNS//60} minutes before next run...")
            time.sleep(DELAY_BETWEEN_RUNS)

if __name__ == "__main__":
    main()
