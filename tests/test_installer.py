from __future__ import annotations

import base64
import io
import tempfile
import tarfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from installer import core


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
            with mock.patch.object(core, "NICKELMENU_PACKAGE", package), mock.patch.object(
                core, "NICKELMENU_METADATA", metadata
            ):
                result = core.repair_uploaded_nickelmenu(
                    "NickelMenu-v-test.KoboRoot.tgz",
                    base64.b64encode(source.read_bytes()).decode("ascii"),
                    "v-test",
                )
            self.assertEqual(result["fonts"], 16)
            with tarfile.open(package, "r:gz") as archive:
                self.assertEqual(archive.extractfile("usr/local/Kobo/imageformats/libnm.so").read(), b"uploaded-nickelmenu-library")
                self.assertEqual(archive.extractfile("mnt/onboard/.adds/nm/old-font.txt").read(), b"kept")
            self.assertEqual(__import__("json").loads(metadata.read_text())["version"], "v-test")

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
