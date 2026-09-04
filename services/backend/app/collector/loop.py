import time

import httpx


class Collector:
    def __init__(self, interval: int, api_url: str, storage):
        self.interval = interval
        self.api_url = api_url
        self.storage = storage
        self.count = 0

    def run(self):
        while True:
            self.count = self.count + 1
            print(f"Tic toutes les {self.interval} s, count {self.count}")
            list_sites = httpx.get(f"{self.api_url}/api/v1/sites", timeout=10)
            data_sites = list_sites.json()
            for site in data_sites:
                site_id = site["site_id"]
                site_info = httpx.get(f"{self.api_url}/api/v1/sites/{site_id}/current", timeout=10)
                self.storage.store_raw("api_current", site_info.text)
                print(f"stocké {site_id}")
            time.sleep(self.interval)
