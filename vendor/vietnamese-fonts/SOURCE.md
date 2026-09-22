# Vietnamese font source

These 20 generated font files were copied without modification from the official [`redphx/kobo-tieng-viet`](https://github.com/redphx/kobo-tieng-viet) release `v20260319` (`KoboRoot.tgz`, SHA-256 `3854122f591d9038b8083d6af55796340ed4b0f5954ee43a7da83cbf1b7f683f`).

Original project and author: **Kobo Tiếng Việt by redphx**.

- The 16 top-level files are redphx's generated replacements for Kobo's Avenir, Georgia, Rakuten Sans, and Rakuten Serif system fonts.
- The four files in `mono/` are redphx's generated Courier-compatible fonts for Kobo's user-font directory.

This installer uses only that release's generated font files. It does not copy or enable the upstream Vietnamese translation, keyboard support, `libtiengviet.so`, locale-changing script, or auto-repair service. Users who want the complete upstream experience should install it directly from the original project.

The upstream build script identifies Roboto, Bitter, and Source Code Pro as the source families and rewrites their metadata for Kobo's expected family and style names. Refer to the original project for font-generation details, source-font terms, support, and updates.
