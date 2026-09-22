from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


device = Path(os.environ["KOBO_MOUNT"])
base_url = os.environ.get("KOBO_INSTALLER_URL", "http://127.0.0.1:8765")
request = urllib.request.Request(
    f"{base_url}/api/install",
    data=json.dumps({"components": ["fonts"]}).encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/json", "X-Kobo-Installer": "1"},
)
with urllib.request.urlopen(request, timeout=120) as response:
    payload = json.load(response)

assert payload["ok"], payload
assert payload["result"]["results"]["fonts"]["fonts"] == 20
assert (device / ".kobo" / "KoboRoot.tgz").is_file()
print("End-to-end API installation passed.")
