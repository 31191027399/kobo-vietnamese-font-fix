# Kobo Vietnamese Installer

[Hướng dẫn tiếng Việt](README.vi.md)

A focused local installer for Vietnamese support on Kobo:

- 20 Kobo-compatible fonts and an optional Vietnamese language pack from [Kobo Tiếng Việt](https://github.com/redphx/kobo-tieng-viet) by redphx
- English–Vietnamese dictionary for Kobo's built-in reader
- English–Vietnamese StarDict dictionary for an existing KOReader installation

It does **not** install or update NickelMenu, KOReader, SimpleUI, or other tools. It does not upload anything from the Kobo. Existing books, reading progress, settings, plugins, and unrelated files are left alone.

## Recommended order

1. If you want NickelMenu or KOReader, install them first with [KoboPatch Web UI](https://kp.nicoverbruggen.be) by Nico Verbruggen.
2. Safely eject the Kobo and wait for its installation/restart to finish. Do not run both installers during the same USB session because each may stage a `.kobo/KoboRoot.tgz`.
3. Reconnect the Kobo, start this installer, and choose **Install Vietnamese support**.
4. Wait for **Complete** in the installer. Close open Kobo files, eject the device in Finder or your file manager, wait for it to disappear, then unplug it. Let Kobo finish restarting to apply the fonts and language pack.

KOReader is optional. When it is detected, the main action installs its Vietnamese dictionary too. Otherwise it installs the font fix, Vietnamese language pack, and Kobo dictionary.

## Start the installer

Python 3 is the only runtime requirement.

### macOS

Double-click `start.command`, or run:

```sh
./start.command
```

### Windows

Install [Python 3](https://www.python.org/downloads/) with **Add python.exe to PATH** enabled, then double-click `start.bat` or run:

```bat
start.bat
```

### Linux

```sh
python3 server.py
```

The browser opens at <http://127.0.0.1:8765>. Connect the Kobo by USB and tap **Connect** on its screen. Wait for **Kobo ready** and check the firmware shown in the device card. If the Kobo is not found, use **Check Kobo** or **Choose Kobo folder**. For multiple devices, select the intended Kobo before installing.

## Exactly what changes

### Vietnamese fonts and language pack

The advanced font rebuild contains 16 system-font replacements plus four Courier-compatible user fonts. The normal **Install Vietnamese support** action additionally includes the optional language payload from redphx's verified `v20260319` release: `trans_vi.qm`, `libtiengviet.so`, and a small configuration hook that adds `Extra: vi` to Kobo's language list. It has no NickelMenu or KOReader payload.

Fonts and language support require firmware 4.x. The installer backs up an existing staged `.kobo/KoboRoot.tgz` before replacing it. After reboot, choose **More → Settings → Language and dictionaries → Select your Language → Extra: vi** if Kobo does not select it automatically. The advanced **Rebuild KoboRoot.tgz** action remains font-only; the normal install action creates a combined font + language package, or a language-only package when only the language pack is selected.

For the complete Vietnamese interface, keyboard, and automatic repair behavior beyond this focused language pack, use the original [Kobo Tiếng Việt](https://github.com/redphx/kobo-tieng-viet) project by redphx.

### Kobo dictionary

The installer downloads the official `redphx/tudien` Kobo release, verifies its published SHA-256 hash, and copies it to:

```text
.kobo/custom-dict/dicthtml-en-vi.zip
```

### KOReader dictionary

If `.adds/koreader` exists, the installer downloads and verifies the official StarDict release, then writes its three dictionary files to:

```text
.adds/koreader/data/dict/tudien-en-vi/
```

It does not modify KOReader settings, plugins, history, or application files. If KOReader is missing, install it with KoboPatch Web UI first.

Dictionary downloads are pinned to `redphx/tudien` release `v20260411` and cached locally after checksum verification. Existing dictionary targets are backed up before updates.

### Independent advanced installs

Open **Advanced options** to install any one of these components independently, or select several at once:

- **Vietnamese font fix** — requires Kobo firmware 4.x.
- **Vietnamese language pack** — can be installed without the font fix.
- **Kobo dictionary** — for Kobo's built-in reader.
- **KOReader dictionary** — requires an existing `.adds/koreader` directory.

The advanced selection starts empty. Select the components you want and choose **Install selected items**. Keep the USB cable connected until the installer shows **Complete**. A firmware 4.x device is required for fonts and language support; dictionaries can be installed separately. The source projects are linked directly in the interface and documented in [Credits and provenance](#credits-and-provenance).

## Advanced archive repair

The **Repair a KoboRoot.tgz only** action overlays the 20 fonts onto a supplied archive while preserving every non-font regular file. It rejects unsafe paths, links, and oversized input. This is for developers who already have a custom package; normal users should use the bundled font-only package.

Recovery backups are stored in `backups/`. They may contain device data, so keep them private.

## Credits and provenance

- Font payload and Kobo font-fix behavior: [Kobo Tiếng Việt](https://github.com/redphx/kobo-tieng-viet) by **redphx**, release `v20260319`. Exact provenance is recorded in [`vendor/vietnamese-fonts/SOURCE.md`](vendor/vietnamese-fonts/SOURCE.md).
- Kobo and KOReader dictionaries: [redphx/tudien](https://github.com/redphx/tudien) by **redphx**. Archives are downloaded directly from the original releases and are not redistributed here.
- Optional prerequisite tools: [KoboPatch Web UI](https://github.com/nicoverbruggen/kobopatch-webui) by **Nico Verbruggen**. Use it to install NickelMenu, KOReader, and other tools before returning here.

This project is independent of those upstream projects. Their work remains theirs and is subject to their respective terms.

Developer details and verification commands are in [TECHNICAL-NOTES.md](TECHNICAL-NOTES.md).

The static download site for Vercel is documented in [VERCEL.md](VERCEL.md). Installation still runs locally on the user's computer.
