from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
BUILD = ROOT / "build"
BACKUPS = Path(os.environ.get("KOBO_INSTALLER_BACKUPS", str(ROOT / "backups"))).expanduser().resolve()
NICKELMENU_SOURCE = VENDOR / "nickelmenu"
VIETNAMESE_FONTS = VENDOR / "vietnamese-fonts"
NICKELMENU_PACKAGE = BUILD / "KoboRoot.tgz"
NICKELMENU_METADATA = BUILD / "nickelmenu-package.json"
NICKELMENU_CHECKSUM = BUILD / "KoboRoot.tgz.sha256"
KOREADER_PACKAGE = VENDOR / "koreader" / "koreader-kobo-v2026.07.1.zip"
SIMPLEUI_SOURCE = VENDOR / "simpleui" / "simpleui.koplugin"
NICKELTC_IMAGE = "ghcr.io/pgaskin/nickeltc:1.0"

FONT_DESTINATION = "usr/local/Trolltech/QtEmbedded-4.6.2-arm/lib/fonts"
FONT_RULE = (
    "\n# Vietnamese system-font overlay managed by kobo-vietnamese-installer.\n"
    "override KOBOROOT += $(foreach font,$(wildcard res/fonts/*.ttf),"
    "$(font):/usr/local/Trolltech/QtEmbedded-4.6.2-arm/lib/fonts/$(notdir $(font)))\n"
)


class InstallerError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _windows_volumes() -> list[Path]:
    import ctypes

    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    return [
        Path(f"{chr(ord('A') + index)}:\\")
        for index in range(26)
        if bitmask & (1 << index)
    ]


def _device_candidates() -> list[Path]:
    override = os.environ.get("KOBO_MOUNT")
    if override:
        return [Path(override).expanduser().resolve()]
    if os.name == "nt":
        return sorted(
            (candidate for candidate in _windows_volumes() if candidate.is_dir()),
            key=lambda item: str(item).lower(),
        )
    volumes = Path("/Volumes")
    if not volumes.is_dir():
        return []
    return sorted(
        (candidate for candidate in volumes.iterdir() if candidate.is_dir()),
        key=lambda item: item.name.lower(),
    )


def find_device() -> Path | None:
    devices = detected_devices()
    return Path(devices[0]["path"]) if devices else None


def detected_devices() -> list[dict]:
    devices = []
    for candidate in _device_candidates():
        if not (candidate / ".kobo" / "version").is_file():
            continue
        raw_version = (candidate / ".kobo" / "version").read_text(errors="replace")
        model = raw_version.split(",", 1)[0].strip() or "Kobo"
        version = firmware_version(candidate)
        devices.append({
            "path": str(candidate),
            "name": candidate.name,
            "model": model,
            "firmware": version,
            "firmwareSupported": firmware_supported(version),
        })
    return devices


def require_device(device_path: str | None = None) -> Path:
    devices = detected_devices()
    if not devices:
        raise InstallerError("No mounted Kobo was found. Connect the Kobo by USB and tap Connect.")
    if device_path:
        for item in devices:
            if item["path"] == device_path:
                return Path(item["path"])
        raise InstallerError("The selected Kobo is no longer connected. Choose a connected Kobo and try again.")
    if len(devices) > 1:
        raise InstallerError("More than one Kobo is connected. Choose the Kobo you want to change.")
    return Path(devices[0]["path"])


def firmware_version(device: Path) -> str | None:
    try:
        value = (device / ".kobo" / "version").read_text(errors="replace")
    except OSError:
        return None
    matches = re.findall(r"\b\d+\.\d+\.\d+\b", value)
    return matches[-1] if matches else None


def firmware_supported(version: str | None) -> bool:
    if not version:
        return False
    try:
        return int(version.split(".", 1)[0]) == 4
    except ValueError:
        return False


def _read_simpleui_version(path: Path) -> str | None:
    meta = path / "_meta.lua"
    if not meta.is_file():
        return None
    match = re.search(r'version\s*=\s*"([^"]+)"', meta.read_text(errors="replace"))
    return match.group(1) if match else None


def device_status(device_path: str | None = None) -> dict:
    devices = detected_devices()
    device = None
    selection_error = None
    if device_path:
        try:
            device = require_device(device_path)
        except InstallerError as exc:
            selection_error = str(exc)
    elif len(devices) == 1:
        device = Path(devices[0]["path"])
    package = None
    package_error = None
    if NICKELMENU_PACKAGE.is_file():
        try:
            package = validate_font_overlay_archive(NICKELMENU_PACKAGE)
        except Exception as exc:  # status must remain available when a build is bad
            package_error = str(exc)
    if device is None:
        return {
            "mounted": False,
            "path": None,
            "devices": devices,
            "selectionError": selection_error,
            "firmware": None,
            "firmwareSupported": False,
            "koreader": None,
            "simpleui": None,
            "nickelmenuPackage": package,
            "nickelmenuPackageError": package_error,
        }
    version = firmware_version(device)
    koreader_version = None
    git_rev = device / ".adds" / "koreader" / "git-rev"
    if git_rev.is_file():
        koreader_version = git_rev.read_text(errors="replace").strip() or "installed"
    return {
        "mounted": True,
        "path": str(device),
        "devices": devices,
        "selectionError": selection_error,
        "firmware": version,
        "firmwareSupported": firmware_supported(version),
        "koreader": koreader_version,
        "simpleui": _read_simpleui_version(device / ".adds" / "koreader" / "plugins" / "simpleui.koplugin"),
        "nickelmenuPackage": package,
        "nickelmenuPackageError": package_error,
    }


def validate_font_overlay_archive(path: Path, require_nickelmenu: bool = False) -> dict:
    if not path.is_file():
        raise InstallerError(f"NickelMenu package not found: {path}")
    expected_fonts = {font.name: sha256_file(font) for font in VIETNAMESE_FONTS.glob("*.ttf")}
    if len(expected_fonts) != 16:
        raise InstallerError(f"Expected 16 Vietnamese font files, found {len(expected_fonts)}.")
    found_fonts: dict[str, str] = {}
    found_library = False
    found_doc = False
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            clean = member.name.removeprefix("./")
            pure = PurePosixPath(clean)
            if pure.is_absolute() or ".." in pure.parts:
                raise InstallerError(f"Unsafe archive path: {member.name}")
            if clean == "usr/local/Kobo/imageformats/libnm.so":
                found_library = member.isfile() and member.size > 0
            if clean == "mnt/onboard/.adds/nm/doc":
                found_doc = member.isfile() and member.size > 0
            prefix = FONT_DESTINATION + "/"
            if clean.startswith(prefix) and member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise InstallerError(f"Could not read font entry: {member.name}")
                found_fonts[PurePosixPath(clean).name] = hashlib.sha256(extracted.read()).hexdigest()
    if require_nickelmenu and (not found_library or not found_doc):
        raise InstallerError("The package is missing NickelMenu's library or documentation.")
    if found_fonts != expected_fonts:
        raise InstallerError("The package font payload does not match the 16 Vietnamese source fonts.")
    return {
        "sha256": sha256_file(path),
        "fonts": len(found_fonts),
        "version": "0.6.0" if found_library and found_doc else "custom KoboRoot.tgz",
        "size": path.stat().st_size,
    }


def validate_nickelmenu_archive(path: Path) -> dict:
    return validate_font_overlay_archive(path, require_nickelmenu=True)


def _validate_uploaded_archive(archive: tarfile.TarFile, require_nickelmenu: bool) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    total_size = 0
    found_library = False
    found_doc = False
    for member in members:
        clean = member.name.removeprefix("./")
        pure = PurePosixPath(clean)
        if not clean or pure.is_absolute() or ".." in pure.parts:
            raise InstallerError(f"Unsafe archive path: {member.name}")
        if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
            raise InstallerError(f"Unsupported archive entry: {member.name}")
        if member.isfile():
            total_size += member.size
            if total_size > 64 * 1024 * 1024:
                raise InstallerError("The uploaded archive expands to more than 64 MB.")
        if clean == "usr/local/Kobo/imageformats/libnm.so":
            found_library = member.isfile() and member.size > 0
        elif clean == "mnt/onboard/.adds/nm/doc":
            found_doc = member.isfile() and member.size > 0
    if require_nickelmenu and (not found_library or not found_doc):
        raise InstallerError("The upload is not a NickelMenu KoboRoot.tgz package.")
    return members


def _repair_uploaded_archive(filename: str, archive_base64: str, version: str, require_nickelmenu: bool) -> dict:
    if not isinstance(filename, str) or Path(filename).name != "KoboRoot.tgz":
        raise InstallerError("Choose a file named KoboRoot.tgz.")
    if not isinstance(archive_base64, str):
        raise InstallerError("The uploaded archive is missing.")
    try:
        uploaded = base64.b64decode(archive_base64, validate=True)
    except (ValueError, TypeError):
        raise InstallerError("The uploaded archive could not be read.") from None
    if not uploaded or len(uploaded) > 16 * 1024 * 1024:
        raise InstallerError("The uploaded archive must be between 1 byte and 16 MB.")
    fonts = sorted(VIETNAMESE_FONTS.glob("*.ttf"))
    if len(fonts) != 16:
        raise InstallerError(f"Expected 16 Vietnamese fonts, found {len(fonts)}.")
    BUILD.mkdir(parents=True, exist_ok=True)
    temporary = NICKELMENU_PACKAGE.with_suffix(".tgz.installing")
    try:
        with tarfile.open(fileobj=io.BytesIO(uploaded), mode="r:gz") as source:
            members = _validate_uploaded_archive(source, require_nickelmenu)
            with tarfile.open(temporary, "w:gz") as destination:
                for member in members:
                    clean = member.name.removeprefix("./")
                    if clean.startswith(FONT_DESTINATION + "/"):
                        continue
                    info = tarfile.TarInfo(clean)
                    info.mode = member.mode
                    info.mtime = member.mtime
                    if member.isdir():
                        info.type = tarfile.DIRTYPE
                        destination.addfile(info)
                    else:
                        payload = source.extractfile(member)
                        if payload is None:
                            raise InstallerError(f"Could not read archive entry: {member.name}")
                        info.size = member.size
                        destination.addfile(info, payload)
                for font in fonts:
                    destination.add(font, arcname=f"{FONT_DESTINATION}/{font.name}", recursive=False)
    except tarfile.TarError as exc:
        raise InstallerError("The uploaded file is not a readable gzip tar archive.") from exc
    try:
        details = validate_font_overlay_archive(temporary, require_nickelmenu=require_nickelmenu)
        os.replace(temporary, NICKELMENU_PACKAGE)
    finally:
        if temporary.exists():
            temporary.unlink()
    selected_version = version.strip()[:64] if isinstance(version, str) else ""
    NICKELMENU_METADATA.write_text(json.dumps({
        "source": "uploaded-nickelmenu" if require_nickelmenu else "uploaded-koboroot",
        "filename": Path(filename).name,
        "version": selected_version or "unspecified",
    }, indent=2) + "\n")
    NICKELMENU_CHECKSUM.write_text(f"{details['sha256']}  KoboRoot.tgz\n")
    return {
        **details,
        "message": "The uploaded package now includes the 16 Vietnamese fonts.",
        "sourceFile": Path(filename).name,
        "sourceVersion": selected_version or "unspecified",
    }


def repair_uploaded_nickelmenu(filename: str, archive_base64: str, version: str = "") -> dict:
    return _repair_uploaded_archive(filename, archive_base64, version, require_nickelmenu=True)


def repair_uploaded_koboroot(filename: str, archive_base64: str, version: str = "") -> dict:
    return _repair_uploaded_archive(filename, archive_base64, version, require_nickelmenu=False)


def build_nickelmenu() -> dict:
    if shutil.which("docker") is None:
        raise InstallerError("Docker is required to compile NickelMenu with the official NickelTC toolchain.")
    if not (NICKELMENU_SOURCE / "NickelHook" / "NickelHook.mk").is_file():
        raise InstallerError("The pinned NickelHook submodule is missing.")
    fonts = sorted(VIETNAMESE_FONTS.glob("*.ttf"))
    if len(fonts) != 16:
        raise InstallerError(f"Expected 16 Vietnamese fonts, found {len(fonts)}.")
    BUILD.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nickelmenu-build-", dir=BUILD) as temp_value:
        temp = Path(temp_value)
        source = temp / "NickelMenu"
        shutil.copytree(NICKELMENU_SOURCE, source, symlinks=True)
        font_dir = source / "res" / "fonts"
        font_dir.mkdir(parents=True, exist_ok=True)
        for font in fonts:
            shutil.copy2(font, font_dir / font.name)
        makefile = source / "Makefile"
        text = makefile.read_text()
        marker = "override KOBOROOT += res/doc:$(NM_CONFIG_DIR)/doc\n"
        if text.count(marker) != 1:
            raise InstallerError("Could not locate the NickelMenu package rule in Makefile.")
        makefile.write_text(text.replace(marker, marker + FONT_RULE, 1))
        command = [
            "docker", "run", "--rm",
            f"--volume={source}:{source}",
            f"--user={os.getuid()}:{os.getgid()}",
            f"--workdir={source}",
            "--env=HOME=/tmp",
            "--entrypoint=make",
            NICKELTC_IMAGE,
            "VERSION=v0.6.0-vietnamese",
            "all", "koboroot",
        ]
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15 * 60,
            check=False,
        )
        if completed.returncode != 0:
            tail = "\n".join(completed.stdout.splitlines()[-30:])
            raise InstallerError(f"NickelTC build failed.\n{tail}")
        generated = source / "KoboRoot.tgz"
        details = validate_nickelmenu_archive(generated)
        destination = NICKELMENU_PACKAGE
        temporary = destination.with_suffix(".tgz.installing")
        shutil.copy2(generated, temporary)
        os.replace(temporary, destination)
        details = validate_nickelmenu_archive(destination)
        NICKELMENU_CHECKSUM.write_text(f"{details['sha256']}  KoboRoot.tgz\n")
        if NICKELMENU_METADATA.exists():
            NICKELMENU_METADATA.unlink()
        return {
            **details,
            "message": "Built NickelMenu 0.6.0 from source with 16 Vietnamese system fonts.",
            "log": "\n".join(completed.stdout.splitlines()[-20:]),
        }


def _timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _backup_paths(device: Path, label: str, relative_paths: list[str]) -> Path | None:
    existing = [(relative, device / relative) for relative in relative_paths if (device / relative).exists()]
    if not existing:
        return None
    BACKUPS.mkdir(parents=True, exist_ok=True)
    destination = BACKUPS / f"{_timestamp()}-{label}.tar.gz"
    with tarfile.open(destination, "w:gz") as archive:
        for relative, path in existing:
            archive.add(path, arcname=relative, recursive=True)
    return destination


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".installing")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def _clean_macos_metadata(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    removed = 0
    for entry in folder.iterdir():
        if entry.is_file() and (entry.name.startswith("._") or entry.name in {".DS_Store", "DG1__DS_DIR_HDR"}):
            entry.unlink()
            removed += 1
    return removed


def install_nickelmenu(device: Path | None = None) -> dict:
    device = device or require_device()
    version = firmware_version(device)
    if not firmware_supported(version):
        raise InstallerError(f"Vietnamese NickelMenu supports Kobo firmware 4.x; detected {version or 'unknown'}.")
    details = validate_font_overlay_archive(NICKELMENU_PACKAGE)
    backup = _backup_paths(device, "before-nickelmenu", [".kobo/KoboRoot.tgz", ".adds/nm"])
    target = device / ".kobo" / "KoboRoot.tgz"
    _atomic_copy(NICKELMENU_PACKAGE, target)
    sidecar = target.with_name("._" + target.name)
    if sidecar.exists():
        sidecar.unlink()
    if sha256_file(target) != details["sha256"]:
        raise InstallerError("The staged NickelMenu package failed checksum verification.")
    os.sync()
    return {
        "message": "Vietnamese NickelMenu package staged. It will install after safe eject.",
        "backup": str(backup) if backup else None,
        **details,
    }


def _validate_koreader_package(path: Path) -> tuple[str, list[zipfile.ZipInfo]]:
    if not path.is_file():
        raise InstallerError(f"KOReader package not found: {path}")
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise InstallerError(f"KOReader ZIP failed validation at {bad}.")
        entries = []
        for entry in archive.infolist():
            pure = PurePosixPath(entry.filename)
            if pure.is_absolute() or ".." in pure.parts:
                raise InstallerError(f"Unsafe KOReader ZIP path: {entry.filename}")
            if entry.filename == "koreader.png" or entry.is_dir():
                continue
            if not pure.parts or pure.parts[0] != "koreader":
                raise InstallerError(f"Unexpected KOReader ZIP path: {entry.filename}")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise InstallerError(f"KOReader ZIP contains a symbolic link: {entry.filename}")
            entries.append(entry)
        version = archive.read("koreader/git-rev").decode("utf-8").strip()
    return version, entries


def _configure_direct_koreader_launcher(device: Path) -> None:
    nm = device / ".adds" / "nm"
    nm.mkdir(parents=True, exist_ok=True)
    launcher = nm / "koreader"
    launcher.write_text(
        "# KOReader launcher managed by Kobo Vietnamese Installer\n"
        "menu_item : main : KOReader : cmd_spawn : quiet : exec /mnt/onboard/.adds/koreader/koreader.sh\n"
    )
    shortcuts = nm / "kobo-installer"
    shortcuts.write_text(
        "# Standard NickelMenu shortcuts managed by Kobo Vietnamese Installer\n"
        "# This file is separate from your own .adds/nm/config file.\n"
        "menu_item : main : Dark Mode : nickel_setting : toggle : dark_mode\n"
        "menu_item : main : Wi-Fi : nickel_wifi : toggle\n"
        "menu_item : main : Rescan Books : nickel_misc : rescan_books_full\n"
        "menu_item : main : Reboot Kobo : power : reboot\n"
    )
    kfmon = nm / "kfmon"
    if kfmon.is_file():
        value = kfmon.read_text(errors="replace")
        value = re.sub(
            r"(?m)^(\s*generator\s*:\s*main\s*:\s*kfmon(?:\s*:\s*\w+)?\s*)$",
            "# Disabled: KOReader uses the direct launcher; KFMon may not be running.\n# \\1",
            value,
        )
        kfmon.write_text(value)
    _clean_macos_metadata(nm)


def install_koreader(device: Path | None = None) -> dict:
    device = device or require_device()
    version, entries = _validate_koreader_package(KOREADER_PACKAGE)
    backup = _backup_paths(
        device,
        "before-koreader",
        [
            ".adds/koreader/settings.reader.lua",
            ".adds/koreader/history.lua",
            ".adds/koreader/defaults.custom.lua",
            ".adds/koreader/settings",
            ".adds/nm",
        ],
    )
    with zipfile.ZipFile(KOREADER_PACKAGE) as archive:
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            target = device / ".adds" / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".installing")
            temporary.write_bytes(archive.read(entry))
            os.replace(temporary, target)
        installed_rev = device / ".adds" / "koreader" / "git-rev"
        if installed_rev.read_text(errors="replace").strip() != version:
            raise InstallerError("KOReader version verification failed after copying files.")
        for entry in entries:
            target = device / ".adds" / Path(*PurePosixPath(entry.filename).parts)
            if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(archive.read(entry)).digest():
                raise InstallerError(f"KOReader file verification failed: {entry.filename}")
    _configure_direct_koreader_launcher(device)
    os.sync()
    return {
        "message": f"KOReader {version} installed or updated; user settings were preserved.",
        "version": version,
        "files": len(entries),
        "backup": str(backup) if backup else None,
    }


def _copytree_clean(source: Path, destination: Path) -> None:
    def ignore(_folder: str, names: list[str]) -> set[str]:
        return {name for name in names if name == ".DS_Store" or name.startswith("._")}
    shutil.copytree(source, destination, ignore=ignore)


def _replace_stale_zenos_font(settings_file: Path) -> bool:
    if not settings_file.is_file():
        return False
    value = settings_file.read_text(errors="replace")
    updated = re.sub(
        r'/mnt/onboard/\.adds/koreader/plugins/(?:zenos|zen_ui)\.koplugin/fonts/[^"\n]+',
        "/mnt/onboard/.adds/koreader/fonts/noto/NotoSans-Regular.ttf",
        value,
    )
    if updated == value:
        return False
    settings_file.write_text(updated)
    return True


def install_simpleui(device: Path | None = None) -> dict:
    device = device or require_device()
    if not (device / ".adds" / "koreader").is_dir():
        raise InstallerError("Install KOReader before installing SimpleUI.")
    source_version = _read_simpleui_version(SIMPLEUI_SOURCE)
    if source_version != "2.7.1" or not (SIMPLEUI_SOURCE / "locale" / "vi.po").is_file():
        raise InstallerError("The bundled SimpleUI 2.7.1 payload is incomplete.")
    plugins = device / ".adds" / "koreader" / "plugins"
    target = plugins / "simpleui.koplugin"
    backup = _backup_paths(
        device,
        "before-simpleui",
        [
            ".adds/koreader/plugins/simpleui.koplugin",
            ".adds/koreader/plugins/zenos.koplugin",
            ".adds/koreader/plugins/zen_ui.koplugin",
            ".adds/koreader/plugins/projecttitle.koplugin",
            ".adds/koreader/settings.reader.lua",
        ],
    )
    plugins.mkdir(parents=True, exist_ok=True)
    for name in ("zenos.koplugin", "zen_ui.koplugin", "projecttitle.koplugin"):
        conflict = plugins / name
        if conflict.exists():
            disabled = plugins / (name + ".disabled-by-installer")
            if disabled.exists():
                if disabled.is_dir():
                    shutil.rmtree(disabled)
                else:
                    disabled.unlink()
            os.replace(conflict, disabled)
    temporary = plugins / "simpleui.koplugin.installing"
    if temporary.exists():
        shutil.rmtree(temporary)
    _copytree_clean(SIMPLEUI_SOURCE, temporary)
    if target.exists():
        shutil.rmtree(target)
    os.replace(temporary, target)
    changed_font = False
    for name in ("settings.reader.lua", "settings.reader.lua.old"):
        changed_font = _replace_stale_zenos_font(device / ".adds" / "koreader" / name) or changed_font
    if _read_simpleui_version(target) != source_version:
        raise InstallerError("SimpleUI version verification failed after copying files.")
    if list(target.rglob("._*")):
        raise InstallerError("macOS metadata files were found in the SimpleUI installation.")
    os.sync()
    return {
        "message": f"SimpleUI {source_version} installed with Vietnamese translation.",
        "version": source_version,
        "fontReferenceUpdated": changed_font,
        "backup": str(backup) if backup else None,
    }


def install_selected(components: list[str], device_path: str | None = None) -> dict:
    allowed = {"nickelmenu", "koreader", "simpleui"}
    if not components or any(component not in allowed for component in components):
        raise InstallerError("Select at least one valid component.")
    device = require_device(device_path)
    results = {}
    for component in ("nickelmenu", "koreader", "simpleui"):
        if component not in components:
            continue
        if component == "nickelmenu":
            results[component] = install_nickelmenu(device)
        elif component == "koreader":
            results[component] = install_koreader(device)
        else:
            results[component] = install_simpleui(device)
    return {"message": "Selected components installed successfully.", "results": results}


def safely_eject(device_path: str | None = None) -> dict:
    device = require_device(device_path)
    if os.name == "nt":
        return {
            "message": "Close any open files, then use Windows' Safely Remove Hardware to eject the Kobo.",
            "path": str(device),
        }
    if os.environ.get("KOBO_MOUNT") or device.parent != Path("/Volumes"):
        return {"message": "Simulated Kobo released.", "path": str(device)}
    completed = subprocess.run(
        ["diskutil", "eject", str(device)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise InstallerError(completed.stdout.strip() or "Could not eject the Kobo.")
    return {"message": completed.stdout.strip(), "path": str(device)}


def write_manifest() -> dict:
    files = [NICKELMENU_PACKAGE, KOREADER_PACKAGE]
    files.extend(sorted(VIETNAMESE_FONTS.glob("*.ttf")))
    files.extend(
        [
            SIMPLEUI_SOURCE / "main.lua",
            SIMPLEUI_SOURCE / "_meta.lua",
            SIMPLEUI_SOURCE / "locale" / "vi.po",
        ]
    )
    manifest = {str(path.relative_to(ROOT)): sha256_file(path) for path in files if path.is_file()}
    destination = ROOT / "ASSET-MANIFEST.json"
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
