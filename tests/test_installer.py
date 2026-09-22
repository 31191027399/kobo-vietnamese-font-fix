from __future__ import annotations

import base64
import io
import tempfile
import tarfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import server

from installer import core


class ServerTests(unittest.TestCase):
    def test_bind_falls_back_when_port_is_in_use(self):
        blocker = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        used = blocker.server_address[1]
        try:
            bound = server._bind_server("127.0.0.1", used)
            try:
                self.assertNotEqual(bound.server_address[1], used)
                self.assertGreater(bound.server_address[1], used)
            finally:
                bound.server_close()
        finally:
            blocker.server_close()

    def test_bind_uses_requested_port_when_free(self):
        bound = server._bind_server("127.0.0.1", 0)
        try:
            self.assertGreater(bound.server_address[1], 0)
        finally:
            bound.server_close()


class InstallerTests(unittest.TestCase):
    def make_device(self, root: Path) -> Path:
        device = root / "KOBOeReader"
        (device / ".kobo").mkdir(parents=True)
        (device / ".kobo" / "version").write_text("N250,4.38.23697,4.38.23697")
        return device

    def make_koreader_zip(self, root: Path) -> Path:
        package = root / "koreader.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("koreader/git-rev", "v-test\n")
            archive.writestr("koreader/koreader.sh", "#!/bin/sh\n")
            archive.writestr("koreader/reader.lua", "return true\n")
            archive.writestr("koreader.png", b"icon")
        return package

    def make_simpleui(self, root: Path) -> Path:
        plugin = root / "simpleui.koplugin"
        (plugin / "locale").mkdir(parents=True)
        (plugin / "_meta.lua").write_text('return { version = "2.7.1" }\n')
        (plugin / "main.lua").write_text("return {}\n")
        (plugin / "locale" / "vi.po").write_text('msgid "Home"\nmsgstr "Trang chủ"\n')
        return plugin

    def test_saved_nickelmenu_package_contains_all_fonts(self):
        details = core.validate_nickelmenu_archive(core.NICKELMENU_PACKAGE)
        self.assertEqual(details["fonts"], 16)
        self.assertEqual(details["version"], "0.6.0")

    def test_multiple_kobos_require_an_explicit_device_choice(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            first = root / "Kobo One"
            second = root / "Kobo Two"
            for device, model, version in ((first, "N250", "4.38.23697"), (second, "N905", "4.41.23145")):
                (device / ".kobo").mkdir(parents=True)
                (device / ".kobo" / "version").write_text(f"{model},{version},{version}\n")
            with mock.patch.object(core, "_device_candidates", return_value=[first, second]):
                devices = core.detected_devices()
                self.assertEqual([item["name"] for item in devices], ["Kobo One", "Kobo Two"])
                with self.assertRaisesRegex(core.InstallerError, "More than one Kobo"):
                    core.require_device()
                self.assertEqual(core.require_device(str(second)), second)
                status = core.device_status(str(second))
            self.assertEqual(status["path"], str(second))
            self.assertEqual(len(status["devices"]), 2)

    def test_uploaded_nickelmenu_is_preserved_and_gets_vietnamese_fonts(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            source = root / "KoboRoot.tgz"
            with tarfile.open(source, "w:gz") as archive:
                for name, payload in {
                    "usr/local/Kobo/imageformats/libnm.so": b"uploaded-nickelmenu-library",
                    "mnt/onboard/.adds/nm/doc": b"uploaded documentation",
                    "mnt/onboard/.adds/nm/old-font.txt": b"kept",
                }.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
            package = root / "repaired-KoboRoot.tgz"
            metadata = root / "nickelmenu-package.json"
            checksum = root / "KoboRoot.tgz.sha256"
            with mock.patch.object(core, "NICKELMENU_PACKAGE", package), mock.patch.object(
                core, "NICKELMENU_METADATA", metadata
            ), mock.patch.object(
                core, "NICKELMENU_CHECKSUM", checksum
            ):
                result = core.repair_uploaded_nickelmenu(
                    "KoboRoot.tgz",
                    base64.b64encode(source.read_bytes()).decode("ascii"),
                    "v-test",
                )
            self.assertEqual(result["fonts"], 16)
            with tarfile.open(package, "r:gz") as archive:
                self.assertEqual(archive.extractfile("usr/local/Kobo/imageformats/libnm.so").read(), b"uploaded-nickelmenu-library")
                self.assertEqual(archive.extractfile("mnt/onboard/.adds/nm/old-font.txt").read(), b"kept")
            self.assertEqual(__import__("json").loads(metadata.read_text())["version"], "v-test")

    def test_uploaded_custom_koboroot_gets_fonts_without_nickelmenu(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            source = root / "KoboRoot.tgz"
            with tarfile.open(source, "w:gz") as archive:
                payload = b"custom-patch-content"
                info = tarfile.TarInfo("etc/custom-patch.conf")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            package = root / "repaired-KoboRoot.tgz"
            metadata = root / "koboroot-package.json"
            checksum = root / "KoboRoot.tgz.sha256"
            with mock.patch.object(core, "NICKELMENU_PACKAGE", package), mock.patch.object(
                core, "NICKELMENU_METADATA", metadata
            ), mock.patch.object(
                core, "NICKELMENU_CHECKSUM", checksum
            ):
                result = core.repair_uploaded_koboroot(
                    "KoboRoot.tgz", base64.b64encode(source.read_bytes()).decode("ascii"), "custom patch"
                )
                self.assertEqual(core.validate_font_overlay_archive(package)["fonts"], 16)
                with self.assertRaises(core.InstallerError):
                    core.validate_nickelmenu_archive(package)
            self.assertEqual(result["version"], "custom KoboRoot.tgz")
            with tarfile.open(package, "r:gz") as archive:
                self.assertEqual(archive.extractfile("etc/custom-patch.conf").read(), b"custom-patch-content")

    def test_repair_keeps_everything_except_the_16_vietnamese_fonts(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            source = root / "KoboRoot.tgz"
            entries = {
                "usr/local/Kobo/imageformats/libnm.so": b"libnm",
                "mnt/onboard/.adds/nm/doc": b"doc",
                "usr/local/Kobo/custom-patch.conf": b"custom",
                core.FONT_DESTINATION + "/Kobo-Nickel.ttf": b"unrelated-font",
                core.FONT_DESTINATION + "/notes.txt": b"notes",
                core.FONT_DESTINATION + "/Avenir.ttf": b"stale-vietnamese-font",
            }
            with tarfile.open(source, "w:gz") as archive:
                for name, payload in entries.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    info.mode = 0o600
                    info.uid = info.gid = 7
                    info.uname = info.gname = "root"
                    info.mtime = 123456789
                    archive.addfile(info, io.BytesIO(payload))
            package = root / "repaired-KoboRoot.tgz"
            with mock.patch.object(core, "NICKELMENU_PACKAGE", package), mock.patch.object(
                core, "NICKELMENU_METADATA", root / "meta.json"
            ), mock.patch.object(core, "NICKELMENU_CHECKSUM", root / "sum"):
                result = core.repair_uploaded_koboroot(
                    "KoboRoot.tgz", base64.b64encode(source.read_bytes()).decode("ascii"), "custom"
                )
            self.assertEqual(result["fonts"], 16)
            expected_fonts = {font.name: font.read_bytes() for font in core.VIETNAMESE_FONTS.glob("*.ttf")}
            preserved = {name: payload for name, payload in entries.items() if name not in
                         {core.FONT_DESTINATION + "/" + font for font in expected_fonts}}
            with tarfile.open(package, "r:gz") as archive:
                found = {}
                for member in archive.getmembers():
                    clean = member.name.removeprefix("./")
                    found[clean] = (member, archive.extractfile(member).read() if member.isfile() else None)
                for name, payload in preserved.items():
                    self.assertIn(name, found)
                    member, stored = found[name]
                    self.assertEqual(stored, payload)
                    self.assertEqual(
                        (member.mode, member.uid, member.gid, member.uname, member.gname, member.mtime),
                        (0o600, 7, 7, "root", "root", 123456789),
                    )
                for name, payload in expected_fonts.items():
                    member, stored = found[core.FONT_DESTINATION + "/" + name]
                    self.assertEqual(stored, payload)
                    self.assertEqual(
                        (member.uid, member.gid, member.uname, member.gname, member.mode),
                        (0, 0, "root", "root", 0o644),
                    )

    def test_existing_device_install_flow(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            device = self.make_device(root)
            (device / ".adds" / "koreader" / "settings").mkdir(parents=True)
            settings = device / ".adds" / "koreader" / "settings.reader.lua"
            settings.write_text('font = "/mnt/onboard/.adds/koreader/plugins/zenos.koplugin/fonts/demo.ttf"\n')
            history = device / ".adds" / "koreader" / "history.lua"
            history.write_text("return { preserved = true }\n")
            nm = device / ".adds" / "nm"
            nm.mkdir(parents=True)
            (nm / "kfmon").write_text("generator : main : kfmon\n")
            (nm / "._config").write_bytes(b"metadata")
            package = self.make_koreader_zip(root)
            simpleui = self.make_simpleui(root)
            backup_dir = root / "backups"
            with mock.patch.object(core, "KOREADER_PACKAGE", package), mock.patch.object(
                core, "SIMPLEUI_SOURCE", simpleui
            ), mock.patch.object(core, "BACKUPS", backup_dir):
                koreader_result = core.install_koreader(device)
                simpleui_result = core.install_simpleui(device)
            self.assertEqual(koreader_result["version"], "v-test")
            self.assertEqual(simpleui_result["version"], "2.7.1")
            self.assertEqual(history.read_text(), "return { preserved = true }\n")
            self.assertIn("KOReader", (nm / "koreader").read_text())
            shortcuts = (nm / "kobo-installer").read_text()
            self.assertIn("menu_item : main : Dark Mode", shortcuts)
            self.assertIn("menu_item : main : Rescan Books", shortcuts)
            self.assertNotRegex((nm / "kfmon").read_text(), r"(?m)^\s*generator")
            self.assertFalse((nm / "._config").exists())
            self.assertIn("NotoSans-Regular.ttf", settings.read_text())
            self.assertTrue((device / ".adds" / "koreader" / "plugins" / "simpleui.koplugin" / "locale" / "vi.po").is_file())
            self.assertTrue(list(backup_dir.glob("*.tar.gz")))

    def test_nickelmenu_staging_rejects_firmware_five(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            device = self.make_device(root)
            (device / ".kobo" / "version").write_text("N250,5.0.0,5.0.0")
            with self.assertRaises(core.InstallerError):
                core.install_nickelmenu(device)


if __name__ == "__main__":
    unittest.main()
