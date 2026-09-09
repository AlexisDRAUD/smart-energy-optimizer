import json

import httpx
from app.collector.loop import Collector


class Storage:
    def __init__(self):
        self.snapshots = []
        self.readings = []

    def store_snapshot(self, source, payload):
        self.snapshots.append((source, json.loads(payload)))

    def store_raw_many(self, source, payloads):
        self.readings.extend((source, json.loads(payload)) for payload in payloads)
        return len(payloads)


def client(alert_status=200):
    def handler(request):
        payloads = {
            "/api/v1/sites": [{"site_id": "SITE001"}],
            "/api/v1/sensors/status": {},
            "/api/v1/alerts": [{"site_id": "SITE001", "message": "Source"}],
            "/api/v1/sites/SITE001/current": {"site_id": "SITE001"},
        }
        status = alert_status if request.url.path == "/api/v1/alerts" else 200
        return httpx.Response(status, json=payloads.get(request.url.path, {}))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_collector_captures_source_alerts_and_keeps_measurements_flowing():
    storage = Storage()
    Collector(60, "http://source", storage, client()).run_once()

    assert ("api_alerts", [{"site_id": "SITE001", "message": "Source"}]) in storage.snapshots
    assert storage.readings == [("api_current", {"site_id": "SITE001"})]


def test_alert_endpoint_failure_does_not_block_current_readings():
    storage = Storage()
    Collector(60, "http://source", storage, client(503)).run_once()

    assert all(source != "api_alerts" for source, _ in storage.snapshots)
    assert storage.readings == [("api_current", {"site_id": "SITE001"})]
