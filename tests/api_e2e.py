from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


device = Path(os.environ["KOBO_MOUNT"])
base_url = os.environ.get("KOBO_INSTALLER_URL", "http://127.0.0.1:8765")
request = urllib.request.Request(
    f"{base_url}/api/install",
    data=json.dumps({"components": ["nickelmenu", "koreader", "simpleui"]}).encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/json", "X-Kobo-Installer": "1"},
)
with urllib.request.urlopen(request, timeout=120) as response:
    payload = json.load(response)

assert payload["ok"], payload
assert payload["result"]["results"]["nickelmenu"]["fonts"] == 16
assert payload["result"]["results"]["koreader"]["version"] == "v2026.07.1"
assert payload["result"]["results"]["simpleui"]["version"] == "2.7.1"
assert (device / ".kobo" / "KoboRoot.tgz").is_file()
assert (device / ".adds" / "koreader" / "git-rev").read_text().strip() == "v2026.07.1"
assert (device / ".adds" / "koreader" / "plugins" / "simpleui.koplugin" / "locale" / "vi.po").is_file()
assert "menu_item : main : KOReader" in (device / ".adds" / "nm" / "koreader").read_text()
assert "menu_item : main : Dark Mode" in (device / ".adds" / "nm" / "kobo-installer").read_text()
assert not list((device / ".adds" / "nm").glob("._*"))
print("End-to-end API installation passed.")
