# Vercel deployment

The `vercel` branch contains a static, bilingual download site in `vercel-site/`. The Kobo installer itself runs on the user's computer; a hosted Vercel function cannot access a Kobo connected by USB to a visitor's computer.

## Deploy

1. Push the `vercel` branch to GitHub.
2. Import `finnhuynh65/kobo-vietnamese-installer` in Vercel, or select the existing project.
3. Set the production branch to `vercel` if this site should be production. A branch preview also works.
4. Keep the repository root as the Root Directory. `vercel.json` selects the **Other** framework and serves `vercel-site/` directly. No build command, environment variables, or serverless functions are needed.
5. Check `/` and `/vi.html` on the preview URL. The download buttons link to the GitHub ZIP for the `vercel` branch, so the branch must be pushed before those links work.

Only `vercel-site/` is published. `.vercelignore` excludes installer code, font assets, dictionary cache, and local backups from the Vercel upload. Users download the complete installer from GitHub and run `start.command`, `start.bat`, or `server.py` on their own computer.

To preview the public site locally:

```sh
python3 -m http.server 8766 --directory vercel-site
```

Open <http://127.0.0.1:8766/> and <http://127.0.0.1:8766/vi.html>.
