# Technical notes

## Scope

The active install API accepts `fonts`, `language`, `kobo_dictionary`, and `koreader_dictionary`. Fonts and language support may be selected separately or together. It never installs or updates NickelMenu, KOReader, SimpleUI, keyboard support, or unrelated tools.

Legacy helper functions and vendored sources remain temporarily for backward compatibility and repository history, but the browser flow cannot invoke them.

## Font provenance and package

All 20 generated fonts are copied unchanged from [redphx/kobo-tieng-viet](https://github.com/redphx/kobo-tieng-viet) release `v20260319`. Its official `KoboRoot.tgz` has SHA-256 `3854122f591d9038b8083d6af55796340ed4b0f5954ee43a7da83cbf1b7f683f`.

`build_font_package()` creates `build/KoboRoot.tgz` with Python's `tarfile` module. The package contains:

- 16 Avenir, Georgia, Rakuten Sans, and Rakuten Serif replacements under `usr/local/Trolltech/QtEmbedded-4.6.2-arm/lib/fonts/`.
- 4 Courier-compatible fonts under `mnt/onboard/fonts/` for correct monospace rendering.

The standalone rebuild is font-only. During installation, the selected language option adds `libtiengviet.so`, `trans_vi.qm`, `update_conf.sh`, and its udev rule to the staged package. A language-only selection contains those files without fonts.

The validator checks each source and archive font by SHA-256. Installation is limited to firmware 4.x, backs up an existing staged `.kobo/KoboRoot.tgz`, atomically copies the archive, and verifies the copied hash. No compiler or container is involved.

The generic archive-repair endpoint preserves safe non-font regular files and overlays only these 20 font entries. It rejects absolute/traversal paths, links, special entries, inputs over 16 MB, and expanded data over 64 MB.

## Dictionaries

Dictionary artifacts are fetched directly from [redphx/tudien](https://github.com/redphx/tudien) release `v20260411` and cached in `build/dictionary-cache/`:

| Target | Upstream asset | SHA-256 |
| --- | --- | --- |
| Kobo | `tudien-kobo-en-vi-20260411.zip` | `3f6f9ea747540424a91d174d753d067581ce77c3e2f036c6432a746eb508a0ce` |
| KOReader | `tudien-stardict-en-vi-20260411.zip` | `144f4e73639d9ec277ffc39e17d789d54434af484ca9092e31a694c1027fbe9a` |

Downloads are capped at 32 MB and verified before entering the cache. The Kobo ZIP is integrity-tested. The KOReader ZIP must contain exactly one `.dict.dz`, `.idx`, and `.ifo` payload; those files are flattened to stable `tudien.*` names in `.adds/koreader/data/dict/tudien-en-vi/`.

All selected dictionary downloads are prepared before any device write. KOReader presence is also checked before writes, preventing a partial install when that prerequisite is missing.

## Device handling

Devices are identified by `.kobo/version`. Detection scans `/Volumes` on macOS, drive letters on Windows, and `/media`, `/run/media`, and `/mnt` on Linux. `KOBO_MOUNT` can override detection for testing. Manual folder selection is accepted only when `.kobo/version` exists.

Eject is user-guided on macOS, Windows, and Linux so file-manager processes cannot block or invalidate the operation. Folder reveal uses `open`, `explorer`, or `xdg-open`.

## Checks

```sh
PYTHONPYCACHEPREFIX=/tmp/kobo-installer-pycache python3 -m py_compile server.py installer/core.py
PYTHONPYCACHEPREFIX=/tmp/kobo-installer-pycache python3 -m unittest discover -s tests -p 'test_*.py'
```

The runtime uses only Python's standard library.
