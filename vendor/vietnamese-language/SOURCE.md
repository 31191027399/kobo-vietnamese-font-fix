# Vietnamese language source

These files were copied without modification from the official [`redphx/kobo-tieng-viet`](https://github.com/redphx/kobo-tieng-viet) release `v20260319` (`KoboRoot.tgz`, SHA-256 `3854122f591d9038b8083d6af55796340ed4b0f5954ee43a7da83cbf1b7f683f`).

Original project and author: **Kobo Tiếng Việt by redphx**.

- `trans_vi.qm` provides the Vietnamese Kobo interface translation.
- `libtiengviet.so` provides the Vietnamese Kobo image/font support used by the upstream package.
- `update_conf.sh` and `update_conf.rules` add `vi` to Kobo's `ExtraLocales` and select it as the current locale during installation.

The language pack is optional in this installer and is selected together with the Vietnamese font fix. It does not install NickelMenu, KOReader, or the upstream keyboard/auto-repair features.
