# Kobo Vietnamese Installer

This local tool sets up an existing Kobo with the Vietnamese font fix, KOReader, and SimpleUI. It runs only on your Mac and does not upload anything from the Kobo.

## Install in three steps

1. Double-click [start.command](start.command). Your browser should open the installer. If it does not, open <http://127.0.0.1:8765>.
2. Plug in the Kobo by USB and tap **Connect** on its screen. In the browser, choose **Check Kobo**, then **Install everything**.
3. When the installer says it is complete, choose **Safely eject Kobo**. Unplug the cable and wait for the Kobo to restart.

The installer creates a recovery backup before changing the device. Your books, reading progress, KOReader settings, and plugins are preserved.

## What gets installed

- **Vietnamese font fix** — NickelMenu 0.6.0 with 16 Vietnamese-compatible Kobo system fonts. It works with Kobo firmware 4.x and leaves NickelMenu’s own behavior unchanged.
- **KOReader** — version 2026.07.1, with a direct NickelMenu launcher, standard shortcuts for Dark Mode, Wi-Fi, book rescanning, and rebooting, plus a repair for the KFMon generator error.
- **SimpleUI** — version 2.7.1 with Vietnamese translation.

## If you need only one item

Open **Advanced options** in the website and select the item to repair or update. The normal **Install everything** button is the recommended choice for a first setup.

Use **Rebuild KoboRoot.tgz** only if you changed the included font or NickelMenu source. It needs Docker Desktop.

To use another NickelMenu release, open **Advanced options**, choose that release’s `KoboRoot.tgz` in **Repair another NickelMenu version**, and optionally enter its version number. The tool verifies the archive, preserves its NickelMenu files, and adds the Vietnamese fonts. Then use **Install everything**.

## Common questions

**Will this change Kobo’s normal reader?** No. NickelMenu adds a menu entry and the font package adds system fonts. Kobo’s normal home screen and reader remain available.

**When do Vietnamese fonts appear?** The font package is applied when the Kobo restarts after ejecting. Leave it unplugged until that restart has finished.

**Where are backups?** They are saved in `backups/`. They may contain reading data or book names, so keep them private.

For source versions and developer checks, see [TECHNICAL-NOTES.md](TECHNICAL-NOTES.md).
