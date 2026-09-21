# Kobo Vietnamese Installer

This local tool sets up an existing Kobo with the Vietnamese font fix, KOReader, and SimpleUI. It runs only on your Mac and does not upload anything from the Kobo.

## Install in three steps

1. Double-click [start.command](start.command). Your browser should open the installer. If it does not, open <http://127.0.0.1:8765>.
2. Plug in the Kobo by USB and tap **Connect** on its screen. In the browser, choose **Check Kobo**, then **Install everything**.
3. When the installer says it is complete, choose **Safely eject Kobo**. Unplug the cable and wait for the Kobo to restart.

The installer creates a recovery backup before changing the device. Your books, reading progress, KOReader settings, and plugins are preserved.

## More than one Kobo

The website detects every mounted Kobo by its `.kobo/version` file. If more than one Kobo is connected, choose the device from the **Choose Kobo** list before installing or ejecting. The installer will not write to a device until one is selected.

## What gets installed

- **Vietnamese font fix** — NickelMenu 0.6.0 with 16 Vietnamese-compatible Kobo system fonts. It works with Kobo firmware 4.x and leaves NickelMenu’s own behavior unchanged.
- **KOReader** — version 2026.07.1, with a direct NickelMenu launcher, standard shortcuts for Dark Mode, Wi-Fi, book rescanning, and rebooting, plus a repair for the KFMon generator error.
- **SimpleUI** — version 2.7.1 with Vietnamese translation.

## If you need only one item

Open **Advanced options** in the website and select the item to repair or update. The normal **Install everything** button is the recommended choice for a first setup.

Use **Rebuild KoboRoot.tgz** only if you changed the included font or NickelMenu source. It needs Docker Desktop.

## Repair an uploaded KoboRoot.tgz

Use this when you already have a `KoboRoot.tgz` and want to add the Vietnamese fonts to it. Uploading prepares a repaired package on this Mac; it does not change the Kobo until you install it.

### NickelMenu package

1. Open **Advanced options** and choose **Repair another NickelMenu version**.
2. Select that release’s file named `KoboRoot.tgz`. You can enter its version number for your reference.
3. Choose **Repair uploaded package**. The tool keeps the NickelMenu files and adds the Vietnamese fonts.
4. Choose **Install everything**, or select only **Vietnamese font fix** and choose **Install selected items**.

### Custom package without NickelMenu

1. Open **Advanced options** and choose **Repair a KoboRoot.tgz only**.
2. Select your custom file named `KoboRoot.tgz` and choose **Repair KoboRoot.tgz only**.
3. The tool preserves every non-font entry. It does not add, update, or configure NickelMenu.
4. Select only **Vietnamese font fix**, choose **Install selected items**, then safely eject the Kobo.

The archive must be a gzip `KoboRoot.tgz` no larger than 16 MB. The installer rejects unsafe archive paths and links.

## Common questions

**Will this change Kobo’s normal reader?** No. NickelMenu adds a menu entry and the font package adds system fonts. Kobo’s normal home screen and reader remain available.

**When do Vietnamese fonts appear?** The font package is applied when the Kobo restarts after ejecting. Leave it unplugged until that restart has finished.

**Where are backups?** They are saved in `backups/`. They may contain reading data or book names, so keep them private.

For source versions and developer checks, see [TECHNICAL-NOTES.md](TECHNICAL-NOTES.md).
