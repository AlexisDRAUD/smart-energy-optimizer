import time
import requests

class Collector:

    def __init__(self, interval: int, api_url: str):
        self.interval = interval
        self.api_url = api_url
        self.count = 0


    def run(self):
        while True:
            self.count = self.count + 1
            print(f"Tic toutes les {self.interval} s, count {self.count}")
            list_sites = requests.get(f"{self.api_url}/api/v1/sites")
            data_sites = list_sites.json()
            for site in data_sites:
                site_id = site["site_id"]
                site_info = requests.get(f"{self.api_url}/api/v1/sites/{site_id}/current")
                data_site = site_info.json()
                print(data_site)
            time.sleep(self.interval)
