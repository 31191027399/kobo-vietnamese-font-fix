from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import tarfile
import threading
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

import server

from installer import core


class ServerTests(unittest.TestCase):
    def test_action_status_endpoint_reports_live_phase(self):
        action_id = "test-progress"
        server._set_action(action_id, "downloading", 42, "Downloading the Kobo dictionary…")
        instance = server._bind_server("127.0.0.1", 0)
        threading.Thread(target=instance.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{instance.server_address[1]}/api/action-status?id={action_id}", timeout=30
            ) as response:
                payload = json.load(response)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"]["phase"], "downloading")
            self.assertEqual(payload["action"]["progress"], 42)
        finally:
            instance.shutdown()
            instance.server_close()

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

    def test_open_folder_endpoint_delegates_to_core(self):
        instance = server._bind_server("127.0.0.1", 0)
        threading.Thread(target=instance.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                server.core, "open_device_folder", return_value={"message": "opened", "path": "/tmp/Kobo"}
            ) as opened:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{instance.server_address[1]}/api/open-folder",
                    data=json.dumps({"devicePath": "/tmp/Kobo"}).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json", "X-Kobo-Installer": "1"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.load(response)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["result"]["path"], "/tmp/Kobo")
            opened.assert_called_once_with("/tmp/Kobo")
        finally:
            instance.shutdown()
            instance.server_close()

    def test_choose_folder_endpoint_delegates_to_core(self):
        instance = server._bind_server("127.0.0.1", 0)
        threading.Thread(target=instance.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                server.core, "choose_device_folder", return_value={"supported": True, "cancelled": True, "message": "none"}
            ) as chosen:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{instance.server_address[1]}/api/choose-folder",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json", "X-Kobo-Installer": "1"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.load(response)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["result"]["message"], "none")
            chosen.assert_called_once_with()
        finally:
            instance.shutdown()
            instance.server_close()


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

    def test_saved_font_only_package_contains_all_redphx_fonts(self):
        details = core.validate_font_overlay_archive(core.NICKELMENU_PACKAGE)
        self.assertEqual(details["fonts"], 20)
        self.assertEqual(details["version"], "custom KoboRoot.tgz")
        with self.assertRaises(core.InstallerError):
            core.validate_nickelmenu_archive(core.NICKELMENU_PACKAGE)
        with tarfile.open(core.NICKELMENU_PACKAGE, "r:gz") as archive:
            names = {member.name.removeprefix("./") for member in archive.getmembers() if member.isfile()}
        self.assertEqual(len(names), 20)
        self.assertTrue(all(
            name.startswith(core.FONT_DESTINATION + "/") or name.startswith(core.MONO_FONT_DESTINATION + "/")
            for name in names
        ))

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

    def test_status_detects_vietnamese_language_marker(self):
        with tempfile.TemporaryDirectory() as value:
            device = Path(value)
            config = device / ".kobo" / "Kobo"
            config.mkdir(parents=True)
            (config / "Kobo eReader.conf").write_text("[ApplicationPreferences]\nExtraLocales=en, vi\n")
            self.assertTrue(core._vietnamese_language_installed(device))

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
            self.assertEqual(result["fonts"], 20)
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
                self.assertEqual(core.validate_font_overlay_archive(package)["fonts"], 20)
                with self.assertRaises(core.InstallerError):
                    core.validate_nickelmenu_archive(package)
            self.assertEqual(result["version"], "custom KoboRoot.tgz")
            with tarfile.open(package, "r:gz") as archive:
                self.assertEqual(archive.extractfile("etc/custom-patch.conf").read(), b"custom-patch-content")

    def test_open_folder_targets_the_detected_device(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core, "detected_devices", return_value=[{"path": str(device)}]), mock.patch.object(
                core.subprocess, "Popen"
            ) as popen:
                result = core.open_device_folder(str(device))
            self.assertEqual(result["path"], str(device))
            command = popen.call_args.args[0]
            self.assertEqual(command[-1], str(device))
            self.assertIn(os.path.basename(command[0]), {"open", "explorer", "xdg-open"})

    def test_linux_volumes_lists_nested_mounts(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value) / "media" / "alice"
            device = self.make_device(root)
            self.assertIn(device, core._linux_volumes([root]))

    def test_linux_platform_selects_linux_candidates(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core.sys, "platform", "linux"), mock.patch.object(
                core, "_linux_volumes", return_value=[device]
            ):
                self.assertIn(str(device), [item["path"] for item in core.detected_devices()])

    def test_require_device_accepts_a_manually_chosen_kobo(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core, "detected_devices", return_value=[]):
                self.assertEqual(core.require_device(str(device)), device.resolve())

    def test_require_device_rejects_a_folder_that_is_not_a_kobo(self):
        with tempfile.TemporaryDirectory() as value:
            with mock.patch.object(core, "detected_devices", return_value=[]):
                with self.assertRaises(core.InstallerError):
                    core.require_device(value)

    def test_device_status_reports_a_manually_chosen_device(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core, "detected_devices", return_value=[]):
                status = core.device_status(str(device))
            self.assertTrue(status["mounted"])
            self.assertEqual(status["path"], str(device.resolve()))
            self.assertEqual(status["firmware"], "4.38.23697")

    def test_choose_folder_reports_when_no_dialog_exists(self):
        with mock.patch.object(core, "_folder_dialog_command", return_value=None):
            result = core.choose_device_folder()
        self.assertFalse(result["supported"])
        self.assertTrue(result["cancelled"])

    def test_choose_folder_validates_the_selected_folder(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            completed = mock.Mock(returncode=0, stdout=f"{device}\n")
            with mock.patch.object(core, "_folder_dialog_command", return_value=["dialog"]), mock.patch.object(
                core.subprocess, "run", return_value=completed
            ):
                result = core.choose_device_folder()
            self.assertFalse(result["cancelled"])
            self.assertEqual(result["path"], str(device.resolve()))

    def test_choose_folder_rejects_a_non_kobo_selection(self):
        with tempfile.TemporaryDirectory() as value:
            completed = mock.Mock(returncode=0, stdout=f"{value}\n")
            with mock.patch.object(core, "_folder_dialog_command", return_value=["dialog"]), mock.patch.object(
                core.subprocess, "run", return_value=completed
            ):
                with self.assertRaises(core.InstallerError):
                    core.choose_device_folder()

    def test_eject_on_linux_asks_for_manual_unmount(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core, "detected_devices", return_value=[]), mock.patch.object(
                core.sys, "platform", "linux"
            ):
                result = core.safely_eject(str(device))
            self.assertIn("Unmount", result["message"])

    def test_eject_on_macos_asks_user_to_eject(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core, "detected_devices", return_value=[]), mock.patch.object(
                core.sys, "platform", "darwin"
            ), mock.patch.object(core.subprocess, "run") as run:
                result = core.safely_eject(str(device))
            self.assertIn("eject the Kobo", result["message"])
            run.assert_not_called()

    def test_repair_keeps_everything_except_the_20_vietnamese_fonts(self):
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
            self.assertEqual(result["fonts"], 20)
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

                for font in core.VIETNAMESE_MONO_FONTS.glob("*.ttf"):
                    member, stored = found[core.MONO_FONT_DESTINATION + "/" + font.name]
                    self.assertEqual(stored, font.read_bytes())
                    self.assertEqual(member.mode, 0o644)

    def test_kobo_dictionary_install_writes_only_custom_dictionary(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            device = self.make_device(root)
            source = root / "kobo-dictionary.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("word.html", "xin chào")
            digest = core.sha256_file(source)
            with mock.patch.object(core, "KOBO_DICTIONARY", source), mock.patch.object(
                core, "KOBO_DICTIONARY_SHA256", digest
            ):
                result = core.install_kobo_dictionary(device)
            target = device / ".kobo" / "custom-dict" / "dicthtml-en-vi.zip"
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(result["version"], core.DICTIONARY_RELEASE)

    def test_koreader_dictionary_install_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            device = self.make_device(root)
            (device / ".adds" / "koreader").mkdir(parents=True)
            target = device / ".adds" / "koreader" / "data" / "dict" / "tudien-en-vi"
            target.mkdir(parents=True)
            (target / "notes.txt").write_text("keep")
            source = root / "stardict.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("release-name.dict.dz", b"dictionary")
                archive.writestr("release-name.idx", b"index")
                archive.writestr("release-name.ifo", b"metadata")
            digest = core.sha256_file(source)
            with mock.patch.object(core, "KOREADER_DICTIONARY", source), mock.patch.object(
                core, "KOREADER_DICTIONARY_SHA256", digest
            ):
                result = core.install_koreader_dictionary(device)
            self.assertEqual((target / "notes.txt").read_text(), "keep")
            self.assertEqual((target / "tudien.dict.dz").read_bytes(), b"dictionary")
            self.assertEqual((target / "tudien.idx").read_bytes(), b"index")
            self.assertEqual((target / "tudien.ifo").read_bytes(), b"metadata")
            self.assertEqual(result["files"], 3)

    def test_selected_install_preflights_missing_koreader_before_writes(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core, "detected_devices", return_value=[]):
                with self.assertRaisesRegex(core.InstallerError, "KOReader is not installed"):
                    core.install_selected(["fonts", "koreader_dictionary"], str(device))
            self.assertFalse((device / ".kobo" / "KoboRoot.tgz").exists())

    def test_language_can_be_installed_without_fonts(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            with mock.patch.object(core, "_prepare_dictionary_assets"), mock.patch.object(
                core, "build_font_package", return_value={"message": "language package"}
            ) as build, mock.patch.object(
                core, "install_language", return_value={"message": "language staged"}
            ) as install:
                result = core.install_selected(["language"], str(device))
            build.assert_called_once_with(progress=None, include_language=True, include_fonts=False)
            install.assert_called_once_with(device.resolve(), None)
            self.assertEqual(result["results"]["language"]["message"], "language staged")

    def test_language_only_package_stages_with_verified_checksum(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            device = self.make_device(root)
            package = root / "KoboRoot.tgz"
            checksum = root / "KoboRoot.tgz.sha256"
            metadata = root / "package.json"
            with mock.patch.object(core, "NICKELMENU_PACKAGE", package), mock.patch.object(
                core, "NICKELMENU_CHECKSUM", checksum
            ), mock.patch.object(core, "NICKELMENU_METADATA", metadata), mock.patch.object(
                core, "BACKUPS", root / "backups"
            ):
                result = core.install_selected(["language"], str(device))
            staged = device / ".kobo" / "KoboRoot.tgz"
            self.assertEqual(staged.read_bytes(), package.read_bytes())
            self.assertEqual(result["results"]["language"]["sha256"], core.sha256_file(staged))
            with tarfile.open(staged, "r:gz") as archive:
                names = {member.name for member in archive if member.isfile()}
            self.assertEqual(names, set(core.LANGUAGE_ASSETS))

    def test_install_progress_does_not_finish_during_package_build(self):
        with tempfile.TemporaryDirectory() as value:
            device = self.make_device(Path(value))
            phases = []

            def build(progress, **_kwargs):
                progress("complete", 100, "Package built")

            with mock.patch.object(core, "build_font_package", side_effect=build), mock.patch.object(
                core, "install_fonts", return_value={"message": "staged"}
            ), mock.patch.object(core, "_prepare_dictionary_assets"):
                core.install_selected(["fonts"], str(device), progress=lambda phase, *_args, **_details: phases.append(phase))
            self.assertNotIn("complete", phases)

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
