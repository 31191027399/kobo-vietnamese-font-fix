# Technical notes

## Included sources

- NickelMenu is an exact recursive checkout of tag `v0.6.0` (`15a95f7`), including pinned NickelHook commit `3b1b655`.
- The 16 Vietnamese fonts come unchanged from `lelinhtinh/kobo-tieng-viet` 1.0.0.
- KOReader is the Kobo `v2026.07.1` release payload.
- SimpleUI is `v2.7.1`, including its upstream license, documentation, and Vietnamese translation.

## Vietnamese font package

The builder makes a temporary copy of NickelMenu, adds a packaging-only Makefile rule for the font files, then builds with the official `ghcr.io/pgaskin/nickeltc:1.0` Docker image. It validates that `KoboRoot.tgz` contains NickelMenu, its documentation, and all 16 fonts before replacing `build/KoboRoot.tgz`.

No NickelMenu runtime code is changed. The added fonts are placed in Kobo’s Qt font directory. The installer accepts firmware 4.x and refuses firmware 5.x for this package.

The Advanced upload control can repair a supplied NickelMenu `KoboRoot.tgz` without Docker. It accepts only a gzip tar archive containing NickelMenu’s library and documentation, refuses unsafe paths, links, and oversized extracted payloads, copies the original regular files unchanged, then replaces only the Qt font entries with the verified Vietnamese font set.

## Installation behavior

- NickelMenu backs up the existing `KoboRoot.tgz`, then stages the verified font package in `.kobo/`.
- KOReader updates `.adds/koreader` while preserving settings, history, plugins, and book data; configures the direct launcher plus a separate `kobo-installer` NickelMenu file with Dark Mode, Wi-Fi, rescan, and reboot shortcuts; and removes the stale KFMon generator configuration that causes `/tmp/kfmon-ipc.ctl` errors.
- SimpleUI backs up an existing UI plugin, disables conflicting ZenOS or ProjectTitle folders, installs SimpleUI, verifies its version and Vietnamese translation, and replaces stale ZenOS font references with KOReader’s bundled Noto Sans.

`backups/legacy/` contains retained recovery archives from the original manual setup. Backups can include book names, reading history, and device settings; keep them private.

## Checks

```sh
cd "/Users/finn/Desktop/Fix kobo/kobo-vietnamese-installer"
python3 -m py_compile server.py installer/core.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

The runtime uses only Python’s standard library. Playwright is used for browser testing.
