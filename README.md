# AW Jobs Hub — automatic daily job board

Every morning at 7:00 AM IST, this project scans public career pages (Greenhouse, Lever, Ashby — no API keys),
keeps India early-career roles, sorts them into career tracks, and rebuilds your website. You don't touch code.

## One-time setup (about 15 minutes, all clicking)

1. **Create a free GitHub account** at github.com/signup.
2. **Make a new repository.** Click the **+** (top right) → *New repository*. Name it `aw-jobs-hub`, choose **Public**, click *Create repository*.
3. **Upload the files.** On the new page click *uploading an existing file*. Unzip the folder you downloaded and drag in
   `build.py`, `companies.json`, `manual_jobs.json`, `template.html`, `index.html`, `jobs.json`, `whatsapp_post.txt`, `README.md`. Click *Commit changes*.
4. **Add the daily timer file** (it sits in a hidden folder, so add it by hand):
   *Add file* → *Create new file*. In the name box type exactly `.github/workflows/daily.yml`.
   Open `daily.yml` from the unzipped folder in Notepad/TextEdit, copy everything, paste it in. Click *Commit changes*.
5. **Allow the robot to save updates:** *Settings* → *Actions* → *General* → scroll to *Workflow permissions* →
   choose **Read and write permissions** → *Save*.
6. **Turn on the website:** *Settings* → *Pages* → under *Branch* pick **main** and **/(root)** → *Save*.
   After 1–2 minutes your board is live at `https://YOUR-USERNAME.github.io/aw-jobs-hub/`
7. **Test it:** *Actions* tab → *Daily job refresh* → *Run workflow*. A green tick means it worked.

Optional later: use your own address such as `jobs.analyticswallah.com` (Settings → Pages → Custom domain,
plus one DNS entry at your domain provider).

## Everyday use

- **Nothing to do.** It refreshes itself every morning.
- **Refresh right now:** Actions → Daily job refresh → Run workflow.
- **Add a company:** open `companies.json` → pencil icon → add a line in the same style → Commit.
  Not sure of a company's code name? Ask Claude to check it.
- **Pin a hand-picked role (AW pick):** open `manual_jobs.json` and add an entry in the same style, or ask Claude
  to "refresh jobs" and paste the updated `manual_jobs.json` it gives you.

## Settings you can change (bottom of `companies.json`)

| Setting | Now | What it does |
|---|---|---|
| `max_years` | 2 | Hides roles asking for more experience than this. 3 gives about 40% more roles. |
| `max_age_days` | 90 | Hides listings older than this. Old postings rarely get replies. |
| `max_per_company` | 15 | Stops one big company from flooding the board. |
| `curated_expiry_days` | 30 | AW picks drop off automatically after this many days. |

**Daily WhatsApp post:** open `whatsapp_post.txt` on GitHub each morning, copy, paste into The AW Club.

**If GitHub ever emails that the schedule was paused**, open Actions and click *Enable workflow*.

## Files at a glance

| File | What it is |
|---|---|
| `companies.json` | The list of companies to scan |
| `manual_jobs.json` | Your hand-picked "AW pick" roles (Workday, Microsoft, etc.) |
| `template.html` | The page design |
| `build.py` | The engine that fetches, filters and builds the page |
| `index.html`, `jobs.json` | The finished board (rebuilt automatically) |
| `whatsapp_post.txt` | Today's ready-to-paste WhatsApp post |
| `.github/workflows/daily.yml` | The 7 AM daily timer |
