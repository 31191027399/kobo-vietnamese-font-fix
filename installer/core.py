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
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
BUILD = ROOT / "build"
BACKUPS = Path(os.environ.get("KOBO_INSTALLER_BACKUPS", str(ROOT / "backups"))).expanduser().resolve()
NICKELMENU_SOURCE = VENDOR / "nickelmenu"
VIETNAMESE_FONTS = VENDOR / "vietnamese-fonts"
VIETNAMESE_MONO_FONTS = VIETNAMESE_FONTS / "mono"
VIETNAMESE_LANGUAGE = VENDOR / "vietnamese-language"
NICKELMENU_PACKAGE = BUILD / "KoboRoot.tgz"
NICKELMENU_METADATA = BUILD / "nickelmenu-package.json"
NICKELMENU_CHECKSUM = BUILD / "KoboRoot.tgz.sha256"
KOREADER_PACKAGE = VENDOR / "koreader" / "koreader-kobo-v2026.07.1.zip"
SIMPLEUI_SOURCE = VENDOR / "simpleui" / "simpleui.koplugin"
NICKELTC_IMAGE = "ghcr.io/pgaskin/nickeltc:1.0"

DICTIONARY_RELEASE = "20260411"
DICTIONARY_CACHE = BUILD / "dictionary-cache"
KOBO_DICTIONARY = DICTIONARY_CACHE / f"tudien-kobo-en-vi-{DICTIONARY_RELEASE}.zip"
KOREADER_DICTIONARY = DICTIONARY_CACHE / f"tudien-stardict-en-vi-{DICTIONARY_RELEASE}.zip"
KOBO_DICTIONARY_URL = (
    "https://github.com/redphx/tudien/releases/download/v20260411/"
    f"tudien-kobo-en-vi-{DICTIONARY_RELEASE}.zip"
)
KOREADER_DICTIONARY_URL = (
    "https://github.com/redphx/tudien/releases/download/v20260411/"
    f"tudien-stardict-en-vi-{DICTIONARY_RELEASE}.zip"
)
KOBO_DICTIONARY_SHA256 = "3f6f9ea747540424a91d174d753d067581ce77c3e2f036c6432a746eb508a0ce"
KOREADER_DICTIONARY_SHA256 = "144f4e73639d9ec277ffc39e17d789d54434af484ca9092e31a694c1027fbe9a"
MAX_DICTIONARY_DOWNLOAD = 32 * 1024 * 1024

FONT_DESTINATION = "usr/local/Trolltech/QtEmbedded-4.6.2-arm/lib/fonts"
MONO_FONT_DESTINATION = "mnt/onboard/fonts"
LANGUAGE_ASSETS = {
    "usr/local/Kobo/imageformats/libtiengviet.so": VIETNAMESE_LANGUAGE / "libtiengviet.so",
    "usr/local/Kobo/translations/trans_vi.qm": VIETNAMESE_LANGUAGE / "trans_vi.qm",
    "etc/udev/rules.d/update_conf.rules": VIETNAMESE_LANGUAGE / "update_conf.rules",
    "root/update_conf.sh": VIETNAMESE_LANGUAGE / "update_conf.sh",
}
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


def _macos_volumes() -> list[Path]:
    volumes = Path("/Volumes")
    if not volumes.is_dir():
        return []
    return [candidate for candidate in volumes.iterdir() if candidate.is_dir()]


def _linux_volumes(roots: list[Path] | None = None) -> list[Path]:
    if roots is None:
        roots = [Path("/media"), Path("/run/media"), Path("/mnt")]
        user = os.environ.get("USER") or os.environ.get("LOGNAME")
        if user:
            roots += [Path("/media") / user, Path("/run/media") / user]
    volumes: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for candidate in [root, *(item for item in root.iterdir() if item.is_dir())]:
            volumes[str(candidate)] = candidate
    return list(volumes.values())


def _device_candidates() -> list[Path]:
    override = os.environ.get("KOBO_MOUNT")
    if override:
        return [Path(override).expanduser().resolve()]
    if os.name == "nt":
        candidates = _windows_volumes()
    elif sys.platform == "darwin":
        candidates = _macos_volumes()
    elif sys.platform.startswith("linux"):
        candidates = _linux_volumes()
    else:
        candidates = []
    return sorted(
        (candidate for candidate in candidates if candidate.is_dir()),
        key=lambda item: str(item).lower(),
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


def _looks_like_kobo(path: Path) -> bool:
    try:
        return (path / ".kobo" / "version").is_file()
    except OSError:
        return False


def require_device(device_path: str | None = None) -> Path:
    devices = detected_devices()
    if device_path:
        for item in devices:
            if item["path"] == device_path:
                return Path(item["path"])
        manual = Path(device_path).expanduser()
        if _looks_like_kobo(manual):
            return manual.resolve()
        raise InstallerError("The selected folder is not a Kobo. Choose a folder that contains a .kobo folder.")
    if not devices:
        raise InstallerError("No mounted Kobo was found. Connect the Kobo by USB and tap Connect.")
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


def _vietnamese_language_installed(device: Path) -> bool:
    """Detect the locale marker written by the upstream Vietnamese package."""
    config = device / ".kobo" / "Kobo" / "Kobo eReader.conf"
    if not config.is_file():
        return False
    text = config.read_text(errors="replace")
    return bool(re.search(r"(?:^|\n)(?:ExtraLocales=.*(?:^|,\s*)vi(?:\s|,|$)|CurrentLocale=vi(?:\s|$))", text))


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
            "koboDictionary": False,
            "koreaderDictionary": False,
            "vietnameseLanguage": False,
            "nickelmenuPackage": package,
            "nickelmenuPackageError": package_error,
        }
    version = firmware_version(device)
    koreader_root = device / ".adds" / "koreader"
    koreader_version = "installed" if koreader_root.is_dir() else None
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
        "koboDictionary": (device / ".kobo" / "custom-dict" / "dicthtml-en-vi.zip").is_file(),
        "koreaderDictionary": any(
            (device / ".adds" / "koreader" / "data" / "dict" / "tudien-en-vi").glob("*.ifo")
        ),
        "vietnameseLanguage": _vietnamese_language_installed(device),
        "nickelmenuPackage": package,
        "nickelmenuPackageError": package_error,
    }


def validate_font_overlay_archive(path: Path, require_nickelmenu: bool = False) -> dict:
    if not path.is_file():
        raise InstallerError(f"Vietnamese font package not found: {path}")
    expected_fonts = {font.name: sha256_file(font) for font in VIETNAMESE_FONTS.glob("*.ttf")}
    if len(expected_fonts) != 16:
        raise InstallerError(f"Expected 16 Vietnamese font files, found {len(expected_fonts)}.")
    expected_mono = {font.name: sha256_file(font) for font in VIETNAMESE_MONO_FONTS.glob("*.ttf")}
    if len(expected_mono) != 4:
        raise InstallerError(f"Expected 4 Vietnamese monospace font files, found {len(expected_mono)}.")
    found_fonts: dict[str, str] = {}
    found_mono: dict[str, str] = {}
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
            if clean.startswith(prefix) and member.isfile() and pure.name in expected_fonts:
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise InstallerError(f"Could not read font entry: {member.name}")
                found_fonts[pure.name] = hashlib.sha256(extracted.read()).hexdigest()
            mono_prefix = MONO_FONT_DESTINATION + "/"
            if clean.startswith(mono_prefix) and member.isfile() and pure.name in expected_mono:
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise InstallerError(f"Could not read font entry: {member.name}")
                found_mono[pure.name] = hashlib.sha256(extracted.read()).hexdigest()
    if require_nickelmenu and (not found_library or not found_doc):
        raise InstallerError("The package is missing NickelMenu's library or documentation.")
    missing = sorted(set(expected_fonts) - set(found_fonts))
    if missing:
        raise InstallerError(f"The package is missing {len(missing)} of the 16 Vietnamese source fonts.")
    if found_fonts != expected_fonts:
        raise InstallerError("The package font payload does not match the 16 Vietnamese source fonts.")
    if found_mono != expected_mono:
        raise InstallerError("The package monospace payload does not match the 4 Vietnamese source fonts.")
    return {
        "sha256": sha256_file(path),
        "fonts": len(found_fonts) + len(found_mono),
        "version": "0.6.0" if found_library and found_doc else "custom KoboRoot.tgz",
        "size": path.stat().st_size,
    }


def validate_language_overlay_archive(path: Path) -> dict:
    expected = {target: sha256_file(source) for target, source in LANGUAGE_ASSETS.items()}
    found: dict[str, str] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            clean = member.name.removeprefix("./")
            if clean not in expected or not member.isfile():
                continue
            payload = archive.extractfile(member)
            if payload is None:
                raise InstallerError(f"Could not read Vietnamese language entry: {member.name}")
            found[clean] = hashlib.sha256(payload.read()).hexdigest()
    missing = sorted(set(expected) - set(found))
    if missing:
        raise InstallerError(f"The Vietnamese language package is missing: {', '.join(missing)}")
    if found != expected:
        raise InstallerError("The Vietnamese language payload does not match redphx's verified release.")
    return {"languageFiles": len(found)}


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
    mono_fonts = sorted(VIETNAMESE_MONO_FONTS.glob("*.ttf"))
    if len(fonts) != 16:
        raise InstallerError(f"Expected 16 Vietnamese fonts, found {len(fonts)}.")
    if len(mono_fonts) != 4:
        raise InstallerError(f"Expected 4 Vietnamese monospace fonts, found {len(mono_fonts)}.")
    font_payload = [
        *((font, f"{FONT_DESTINATION}/{font.name}") for font in fonts),
        *((font, f"{MONO_FONT_DESTINATION}/{font.name}") for font in mono_fonts),
    ]
    font_targets = {target for _font, target in font_payload}
    BUILD.mkdir(parents=True, exist_ok=True)
    temporary = NICKELMENU_PACKAGE.with_suffix(".tgz.installing")
    try:
        with tarfile.open(fileobj=io.BytesIO(uploaded), mode="r:gz") as source:
            members = _validate_uploaded_archive(source, require_nickelmenu)
            with tarfile.open(temporary, "w:gz") as destination:
                for member in members:
                    clean = member.name.removeprefix("./")
                    if clean in font_targets:
                        continue
                    if member.isdir():
                        destination.addfile(member)
                        continue
                    payload = source.extractfile(member)
                    if payload is None:
                        raise InstallerError(f"Could not read archive entry: {member.name}")
                    destination.addfile(member, payload)
                for font, target in font_payload:
                    info = tarfile.TarInfo(target)
                    info.size = font.stat().st_size
                    info.mode = 0o644
                    info.mtime = int(font.stat().st_mtime)
                    info.uname = "root"
                    info.gname = "root"
                    with font.open("rb") as handle:
                        destination.addfile(info, handle)
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
        "message": "The uploaded package now includes the 20 Vietnamese fonts from redphx/kobo-tieng-viet.",
        "sourceFile": Path(filename).name,
        "sourceVersion": selected_version or "unspecified",
    }


def repair_uploaded_nickelmenu(filename: str, archive_base64: str, version: str = "") -> dict:
    return _repair_uploaded_archive(filename, archive_base64, version, require_nickelmenu=True)


def repair_uploaded_koboroot(filename: str, archive_base64: str, version: str = "") -> dict:
    return _repair_uploaded_archive(filename, archive_base64, version, require_nickelmenu=False)


def build_font_package(progress=None, include_language=False, include_fonts=True) -> dict:
    if not include_fonts and not include_language:
        raise InstallerError("The package must contain fonts or the Vietnamese language payload.")
    if progress:
        progress("preparing", 5, "Checking the selected Vietnamese package contents…")
    fonts = sorted(VIETNAMESE_FONTS.glob("*.ttf")) if include_fonts else []
    mono_fonts = sorted(VIETNAMESE_MONO_FONTS.glob("*.ttf")) if include_fonts else []
    if include_fonts and len(fonts) != 16:
        raise InstallerError(f"Expected 16 Vietnamese fonts, found {len(fonts)}.")
    if include_fonts and len(mono_fonts) != 4:
        raise InstallerError(f"Expected 4 Vietnamese monospace fonts, found {len(mono_fonts)}.")
    BUILD.mkdir(parents=True, exist_ok=True)
    temporary = NICKELMENU_PACKAGE.with_suffix(".tgz.installing")
    with tarfile.open(temporary, "w:gz") as archive:
        for font in [*fonts, *mono_fonts]:
            destination = FONT_DESTINATION if font in fonts else MONO_FONT_DESTINATION
            info = tarfile.TarInfo(f"{FONT_DESTINATION}/{font.name}")
            info.name = f"{destination}/{font.name}"
            info.size = font.stat().st_size
            info.mode = 0o644
            info.mtime = int(font.stat().st_mtime)
            info.uname = "root"
            info.gname = "root"
            with font.open("rb") as handle:
                archive.addfile(info, handle)
        if include_language:
            for target, source in LANGUAGE_ASSETS.items():
                info = tarfile.TarInfo(target)
                info.size = source.stat().st_size
                info.mode = 0o755 if target.endswith((".sh", ".rules")) else 0o644
                info.mtime = int(source.stat().st_mtime)
                info.uname = "root"
                info.gname = "root"
                with source.open("rb") as handle:
                    archive.addfile(info, handle)
    if progress:
        progress("validating", 85, "Validating the generated KoboRoot.tgz…")
    details = validate_font_overlay_archive(temporary) if include_fonts else validate_language_overlay_archive(temporary)
    if include_language:
        details.update(validate_language_overlay_archive(temporary))
    os.replace(temporary, NICKELMENU_PACKAGE)
    details = validate_font_overlay_archive(NICKELMENU_PACKAGE) if include_fonts else validate_language_overlay_archive(NICKELMENU_PACKAGE)
    if include_language:
        details.update(validate_language_overlay_archive(NICKELMENU_PACKAGE))
    NICKELMENU_CHECKSUM.write_text(f"{details['sha256']}  KoboRoot.tgz\n")
    if NICKELMENU_METADATA.exists():
        NICKELMENU_METADATA.unlink()
    result = {
        **details,
        "message": (
            "Built a Vietnamese support KoboRoot.tgz with 20 fonts and the language pack."
            if include_fonts and include_language else
            "Built a language-only Vietnamese KoboRoot.tgz."
            if include_language else
            "Built a font-only KoboRoot.tgz with 20 fonts sourced from redphx/kobo-tieng-viet."
        ),
    }
    if progress:
        progress("complete", 100, result["message"])
    return result


def build_nickelmenu() -> dict:
    """Backward-compatible API name for older callers."""
    return build_font_package()


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


def install_fonts(device: Path | None = None, progress=None, include_language=False) -> dict:
    device = device or require_device()
    version = firmware_version(device)
    if not firmware_supported(version):
        raise InstallerError(f"The Vietnamese font fix supports Kobo firmware 4.x; detected {version or 'unknown'}.")
    details = validate_font_overlay_archive(NICKELMENU_PACKAGE)
    if include_language:
        details.update(validate_language_overlay_archive(NICKELMENU_PACKAGE))
    if progress:
        progress("backing_up", 45, "Backing up the existing staged KoboRoot.tgz…")
    backup = _backup_paths(device, "before-vietnamese-fonts", [".kobo/KoboRoot.tgz"])
    target = device / ".kobo" / "KoboRoot.tgz"
    _atomic_copy(NICKELMENU_PACKAGE, target)
    sidecar = target.with_name("._" + target.name)
    if sidecar.exists():
        sidecar.unlink()
    if sha256_file(target) != details["sha256"]:
        raise InstallerError("The staged Vietnamese font package failed checksum verification.")
    if progress:
        progress("verifying", 85, "Verified the staged Vietnamese font package.")
    os.sync()
    return {
        "message": (
            "The Vietnamese font and language package is staged. It will install after safe eject."
            if include_language else
            "The font-only Vietnamese package is staged. It will install after safe eject."
        ),
        "backup": str(backup) if backup else None,
        **details,
    }


def install_language(device: Path | None = None, progress=None) -> dict:
    device = device or require_device()
    details = validate_language_overlay_archive(NICKELMENU_PACKAGE)
    if progress:
        progress("backing_up", 45, "Backing up the existing staged KoboRoot.tgz…")
    backup = _backup_paths(device, "before-vietnamese-language", [".kobo/KoboRoot.tgz"])
    target = device / ".kobo" / "KoboRoot.tgz"
    _atomic_copy(NICKELMENU_PACKAGE, target)
    sidecar = target.with_name("._" + target.name)
    if sidecar.exists():
        sidecar.unlink()
    if sha256_file(target) != details["sha256"]:
        raise InstallerError("The staged Vietnamese language package failed checksum verification.")
    if progress:
        progress("verifying", 85, "Verified the staged Vietnamese language package.")
    os.sync()
    return {"message": "The Vietnamese language package is staged. It will install after safe eject.", "backup": str(backup) if backup else None, **details}


def install_nickelmenu(device: Path | None = None) -> dict:
    """Backward-compatible API name; this no longer installs or changes NickelMenu."""
    return install_fonts(device)


def _download_dictionary(url: str, destination: Path, expected_sha256: str, progress=None, label="dictionary") -> Path:
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        if progress:
            progress("cached", 35, f"Using the verified {label} already cached on this computer.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".downloading")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Kobo-Vietnamese-Installer/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            total = 0
            expected_size = int(response.headers.get("Content-Length", "0") or 0)
            if progress:
                progress("downloading", 10, f"Downloading the {label}…", total=expected_size)
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DICTIONARY_DOWNLOAD:
                    raise InstallerError("The dictionary download is larger than expected.")
                output.write(chunk)
                if progress and expected_size:
                    progress("downloading", min(65, 10 + int(total * 55 / expected_size)), f"Downloading the {label}…", total=expected_size, completed=total)
    except (OSError, urllib.error.URLError) as exc:
        raise InstallerError(
            "Could not download the Vietnamese dictionary from redphx/tudien. "
            "Check your internet connection and try again."
        ) from exc
    if sha256_file(temporary) != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise InstallerError("The downloaded Vietnamese dictionary failed SHA-256 verification.")
    os.replace(temporary, destination)
    if progress:
        progress("validating", 70, f"Verified the {label} download.")
    return destination


def _prepare_dictionary_assets(components: list[str], progress=None) -> None:
    if "kobo_dictionary" in components:
        _download_dictionary(KOBO_DICTIONARY_URL, KOBO_DICTIONARY, KOBO_DICTIONARY_SHA256, progress, "Kobo dictionary")
    if "koreader_dictionary" in components:
        _download_dictionary(KOREADER_DICTIONARY_URL, KOREADER_DICTIONARY, KOREADER_DICTIONARY_SHA256, progress, "KOReader dictionary")


def install_kobo_dictionary(device: Path | None = None, progress=None) -> dict:
    device = device or require_device()
    source = _download_dictionary(KOBO_DICTIONARY_URL, KOBO_DICTIONARY, KOBO_DICTIONARY_SHA256, progress, "Kobo dictionary")
    try:
        with zipfile.ZipFile(source) as archive:
            if archive.testzip() or not any(name.endswith(".html") for name in archive.namelist()):
                raise InstallerError("The Kobo dictionary archive is invalid.")
    except zipfile.BadZipFile as exc:
        raise InstallerError("The Kobo dictionary archive is invalid.") from exc
    relative = ".kobo/custom-dict/dicthtml-en-vi.zip"
    backup = _backup_paths(device, "before-kobo-vietnamese-dictionary", [relative])
    if progress:
        progress("copying", 80, "Copying the Kobo dictionary to the device…")
    target = device / relative
    _atomic_copy(source, target)
    if sha256_file(target) != KOBO_DICTIONARY_SHA256:
        raise InstallerError("The Kobo dictionary failed verification after copying.")
    os.sync()
    return {
        "message": "Installed the Vietnamese dictionary for Kobo's built-in reader.",
        "version": DICTIONARY_RELEASE,
        "backup": str(backup) if backup else None,
    }


def _stardict_members(path: Path) -> dict[str, zipfile.ZipInfo]:
    wanted = {".dict.dz", ".idx", ".ifo"}
    found: dict[str, zipfile.ZipInfo] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip():
                raise InstallerError("The KOReader dictionary archive is invalid.")
            for entry in archive.infolist():
                pure = PurePosixPath(entry.filename)
                if entry.is_dir():
                    continue
                if pure.is_absolute() or ".." in pure.parts or stat.S_ISLNK(entry.external_attr >> 16):
                    raise InstallerError(f"Unsafe KOReader dictionary path: {entry.filename}")
                suffix = ".dict.dz" if entry.filename.endswith(".dict.dz") else pure.suffix
                if suffix in wanted:
                    if suffix in found:
                        raise InstallerError("The KOReader dictionary archive contains duplicate StarDict files.")
                    found[suffix] = entry
    except zipfile.BadZipFile as exc:
        raise InstallerError("The KOReader dictionary archive is invalid.") from exc
    if set(found) != wanted:
        raise InstallerError("The KOReader dictionary must contain one .dict.dz, .idx, and .ifo file.")
    return found


def install_koreader_dictionary(device: Path | None = None, progress=None) -> dict:
    device = device or require_device()
    if not (device / ".adds" / "koreader").is_dir():
        raise InstallerError(
            "KOReader is not installed. Install it first with KoboPatch Web UI, then run this installer again."
        )
    source = _download_dictionary(KOREADER_DICTIONARY_URL, KOREADER_DICTIONARY, KOREADER_DICTIONARY_SHA256, progress, "KOReader dictionary")
    members = _stardict_members(source)
    relative = ".adds/koreader/data/dict/tudien-en-vi"
    backup = _backup_paths(device, "before-koreader-vietnamese-dictionary", [relative])
    if progress:
        progress("copying", 80, "Copying the KOReader dictionary to the device…")
    target = device / relative
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        for suffix, entry in members.items():
            destination = target / f"tudien{suffix}"
            temporary = destination.with_name(destination.name + ".installing")
            temporary.write_bytes(archive.read(entry))
            os.replace(temporary, destination)
    os.sync()
    return {
        "message": "Installed the Vietnamese StarDict dictionary for KOReader.",
        "version": DICTIONARY_RELEASE,
        "files": 3,
        "backup": str(backup) if backup else None,
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


def install_selected(components: list[str], device_path: str | None = None, progress=None) -> dict:
    allowed = {"fonts", "language", "kobo_dictionary", "koreader_dictionary"}
    if not components or any(component not in allowed for component in components):
        raise InstallerError("Select at least one valid component.")
    device = require_device(device_path)
    if "koreader_dictionary" in components and not (device / ".adds" / "koreader").is_dir():
        raise InstallerError(
            "KOReader is not installed. Install it first with KoboPatch Web UI, then run this installer again."
        )
    if progress:
        progress("preparing", 5, "Checking the selected Vietnamese components…")
    _prepare_dictionary_assets(components, progress)
    if "fonts" in components or "language" in components:
        build_font_package(
            progress=progress,
            include_language="language" in components,
            include_fonts="fonts" in components,
        )
    results = {}
    for component in ("fonts", "language", "kobo_dictionary", "koreader_dictionary"):
        if component not in components:
            continue
        if component == "fonts":
            results[component] = install_fonts(device, progress, include_language="language" in components)
        elif component == "language":
            if "fonts" in components:
                results[component] = {"message": "Vietnamese language pack included with the staged font package."}
            else:
                results[component] = install_language(device, progress)
        elif component == "kobo_dictionary":
            results[component] = install_kobo_dictionary(device, progress)
        else:
            results[component] = install_koreader_dictionary(device, progress)
    return {"message": "Selected components installed successfully.", "results": results}


def safely_eject(device_path: str | None = None) -> dict:
    device = require_device(device_path)
    if os.name == "nt":
        return {
            "message": "Close any open files, then use Windows' Safely Remove Hardware to eject the Kobo.",
            "path": str(device),
        }
    if sys.platform.startswith("linux"):
        return {
            "message": "Unmount the Kobo from your file manager, then unplug it.",
            "path": str(device),
        }
    if sys.platform == "darwin":
        return {
            "message": "Close any open files, then eject the Kobo from Finder. After it disappears, unplug it and wait for the Kobo to restart.",
            "path": str(device),
        }
    if os.environ.get("KOBO_MOUNT") or device.parent != Path("/Volumes"):
        return {"message": "Simulated Kobo released.", "path": str(device)}
    return {
        "message": "Close any open files, then eject the Kobo using your system's file manager. After it disappears, unplug it and wait for the Kobo to restart.",
        "path": str(device),
    }


def _folder_dialog_command() -> list[str] | None:
    if os.name == "nt":
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$d.Description = 'Choose your Kobo folder';"
            "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
        )
        return ["powershell", "-NoProfile", "-STA", "-Command", script]
    if sys.platform == "darwin":
        return ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choose your Kobo folder")']
    if sys.platform.startswith("linux"):
        if shutil.which("zenity"):
            return ["zenity", "--file-selection", "--directory", "--title=Choose your Kobo folder"]
        if shutil.which("kdialog"):
            return ["kdialog", "--getexistingdirectory", os.path.expanduser("~")]
    return None


def choose_device_folder() -> dict:
    command = _folder_dialog_command()
    if command is None:
        return {
            "supported": False,
            "cancelled": True,
            "message": "No folder dialog is available on this system. Type the folder path instead.",
        }
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallerError(f"Could not open the folder dialog: {exc}") from exc
    chosen = completed.stdout.strip()
    if completed.returncode != 0 or not chosen:
        return {"supported": True, "cancelled": True, "message": "No folder was chosen."}
    path = Path(chosen).expanduser()
    if not _looks_like_kobo(path):
        raise InstallerError("That folder is not a Kobo. Choose the folder that contains a .kobo folder.")
    resolved = path.resolve()
    return {"supported": True, "cancelled": False, "path": str(resolved), "message": f"Selected {resolved}."}


def open_device_folder(device_path: str | None = None) -> dict:
    device = require_device(device_path)
    if os.name == "nt":
        command = ["explorer", str(device)]
    elif sys.platform == "darwin":
        command = ["open", str(device)]
    else:
        command = ["xdg-open", str(device)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise InstallerError(f"Could not open the Kobo folder: {exc}") from exc
    return {"message": f"Opened {device} in your file manager.", "path": str(device)}


def write_manifest() -> dict:
    files = [NICKELMENU_PACKAGE]
    files.extend(sorted(VIETNAMESE_FONTS.glob("*.ttf")))
    files.extend(sorted(VIETNAMESE_MONO_FONTS.glob("*.ttf")))
    manifest = {str(path.relative_to(ROOT)): sha256_file(path) for path in files if path.is_file()}
    destination = ROOT / "ASSET-MANIFEST.json"
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
