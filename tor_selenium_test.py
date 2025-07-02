from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import time

def get_tor_driver():
    options = Options()
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.socks", "127.0.0.1")
    options.set_preference("network.proxy.socks_port", 9150)  
    options.set_preference("network.proxy.socks_version", 5)
    options.set_preference("network.proxy.socks_remote_dns", True)
    options.headless = False  

    return webdriver.Firefox(options=options)

def get_clear_driver():
    options = Options()
    options.headless = False  
    return webdriver.Firefox(options=options)


def measure_load_time(driver, url):
    try:
        start = time.time()
        driver.get(url)
        end = time.time()
        print(f"\nPage loaded: {url}")
        print(f"Load time: {round(end - start, 2)} seconds\n")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    onion_url = "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion"
    clear_url = "https://duckduckgo.com"

    print("\n--- Testing ONION version ---")
    tor_driver = get_tor_driver()
    measure_load_time(tor_driver, onion_url)

    print("\n--- Testing CLEAR WEB version ---")
    clear_driver = get_clear_driver()
    measure_load_time(clear_driver, clear_url)