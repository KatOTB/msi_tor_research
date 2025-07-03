import csv
import time
import logging
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from stem.control import Controller
from stem import StreamStatus
from urllib.parse import urlparse
import requests

INPUT_CSV = "onion_locations_found_testset.csv"
OUTPUT_CSV = "onion_vs_clearnet_comparison_with_relays.csv"
NUM_RUNS = 2
DELAY_BETWEEN_RUNS = 10  # 10 seconds for testing, change to 600 for 10 minutes

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


def get_tor_controller():
    try:
        # Changed to default control port 9051
        controller = Controller.from_port(port=9151)
        controller.authenticate()  # Add password if set in torrc
        logging.info("Successfully connected to Tor controller")
        return controller
    except Exception as e:
        logging.error(f"Failed to connect to Tor controller: {e}")
        return None


def get_circuit_relays(controller, circuit_id):
    try:
        circuit = controller.get_circuit(circuit_id)
        if circuit:
            relays_info = []
            for entry in circuit.path:
                fingerprint, nickname = entry  # unpack tuple
                ip = None
                country = "Unknown"
                try:
                    ns = controller.get_network_status(fingerprint)
                    if ns:
                        ip = getattr(ns, 'address', None)  # safer access
                        if ip:
                            country = get_country_online(ip)
                except Exception as e:
                    logging.warning(f"Failed to get IP/country for {fingerprint}: {e}")
                relays_info.append((fingerprint, nickname, ip, country))
            return relays_info
    except Exception as e:
        logging.error(f"Error getting circuit relays for {circuit_id}: {e}")
    return []


def get_circuit_for_stream(controller, target_url, retries=5, delay=0.5):
    parsed = urlparse(target_url)
    hostname = parsed.hostname.replace("www.", "") if parsed.hostname else None

    for attempt in range(1, retries + 1):
        streams = controller.get_streams()
        logging.info(f"Attempt {attempt}/{retries}: Checking {len(streams)} streams for hostname '{hostname}'")

        for stream in streams:
            stream_info = (f"Stream ID: {stream.id}, Status: {stream.status}, "
                           f"Target: {stream.target}, Circuit ID: {stream.circ_id}")
            logging.debug(stream_info)

            if stream.status in [StreamStatus.NEW, StreamStatus.SUCCEEDED] and stream.target:
                stream_host = stream.target.split(':')[0].replace("www.", "")
                if stream_host == hostname:
                    logging.info(f"Matched stream {stream.id} with circuit ID {stream.circ_id}")
                    return stream.circ_id

        logging.info(f"No matching stream found on attempt {attempt}, retrying after {delay}s...")
        time.sleep(delay)

    logging.warning(f"Could not find circuit ID for {target_url} after {retries} attempts")
    return None


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
        time.sleep(5)  # Wait to allow stream registration
        timing = driver.execute_script("return window.performance.timing")

        get = lambda key: timing.get(key, 0)
        navigation_start = get("navigationStart")
        domain_lookup = get("domainLookupEnd") - get("domainLookupStart")
        connect = get("connectEnd") - get("connectStart")
        tls = get("requestStart") - get("connectEnd") if "https" in url else None
        dom = get("domContentLoadedEventEnd") - navigation_start
        page_load = get("loadEventEnd") - navigation_start
        total = get("loadEventEnd") - navigation_start

        return {
            "dns": domain_lookup if domain_lookup >= 0 else None,
            "tcp": connect if connect >= 0 else None,
            "tls": tls if tls and tls >= 0 else None,
            "dom": dom if dom >= 0 else None,
            "page_load": page_load if page_load >= 0 else None,
            "total_time": total if total >= 0 else None
        }

    except Exception as e:
        logging.warning(f"Error measuring {url}: {e}")
        return None


def clean_url(url):
    return url.strip().split("#")[0].split("?")[0]


def write_raw_data_to_csv(data_rows, mode="a"):
    """Write raw timing and circuit data rows to CSV."""
    with open(OUTPUT_CSV, mode, newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        if mode == "w":
            writer.writerow([
                "Clear Domain", "Type", "URL",
                "DNS Lookup (ms)", "TCP Connect (ms)", "TLS Handshake (ms)",
                "DOMContentLoaded (ms)", "Page Load (ms)", "Total Time (ms)",
                "Circuit Relays (Onion only)"
            ])
        for row in data_rows:
            writer.writerow(row)


def get_country_online(ip):
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data.get("country", "Unknown")
    except Exception:
        pass
    return "Unknown"


def main():
    controller = get_tor_controller()
    if not controller:
        logging.warning("Tor controller not available, relay info will not be logged.")

    with open(INPUT_CSV, "r", encoding="utf-8") as infile:
        reader = list(csv.DictReader(infile))

    # Open output file once, write header
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow([
            "Clear Domain", "Type", "URL",
            "DNS Lookup (ms)", "TCP Connect (ms)", "TLS Handshake (ms)",
            "DOMContentLoaded (ms)", "Page Load (ms)", "Total Time (ms)",
            "Circuit Relays (Onion only)"
        ])

        for run in range(1, NUM_RUNS + 1):
            logging.info(f"Starting measurement run {run} of {NUM_RUNS}")

            for row in reader:
                clear_domain = row["Clear Web Domain"]
                onion_url = clean_url(row["Onion Address"])
                clear_url = f"https://{clear_domain}"

                # Measure onion
                try:
                    logging.info(f"Measuring ONION for {clear_domain}")
                    tor_driver = get_tor_driver()
                    onion_metrics = measure_timings(tor_driver, onion_url)

                    circuit_relays_str = ""
                    if onion_metrics:
                        if controller:
                            circuit_id = get_circuit_for_stream(controller, onion_url)
                            if circuit_id:
                                circuit_relays = get_circuit_relays(controller, circuit_id)
                                if circuit_relays:
                                    circuit_relays_str = "; ".join([
                                        f"{fp}:{nick}:{ip if ip else 'Unknown'}:{country}"
                                        for fp, nick, ip, country in circuit_relays
                                    ])
                                logging.info(f"Circuit used for {onion_url}: {circuit_relays_str}")
                            else:
                                logging.warning(f"Could not find circuit ID for {onion_url}")

                        writer.writerow([
                            clear_domain, "onion", onion_url,
                            onion_metrics["dns"], onion_metrics["tcp"], onion_metrics["tls"],
                            onion_metrics["dom"], onion_metrics["page_load"], onion_metrics["total_time"],
                            circuit_relays_str
                        ])
                        outfile.flush()
                    tor_driver.quit()
                except Exception as e:
                    logging.error(f"Error during ONION measurement for {clear_domain}: {e}")

                # Measure clear web
                try:
                    logging.info(f"Measuring CLEAR WEB for {clear_domain}")
                    clear_driver = get_clear_driver()
                    clear_metrics = measure_timings(clear_driver, clear_url)
                    if clear_metrics:
                        writer.writerow([
                            clear_domain, "clear", clear_url,
                            clear_metrics["dns"], clear_metrics["tcp"], clear_metrics["tls"],
                            clear_metrics["dom"], clear_metrics["page_load"], clear_metrics["total_time"],
                            ""  # no circuit info for clear web
                        ])
                        outfile.flush()
                    clear_driver.quit()
                except Exception as e:
                    logging.error(f"Error during CLEAR WEB measurement for {clear_domain}: {e}")

            if run < NUM_RUNS:
                logging.info(f"Waiting {DELAY_BETWEEN_RUNS}s before next run")
                time.sleep(DELAY_BETWEEN_RUNS)

    logging.info("All runs completed.")


if __name__ == "__main__":
    main()
