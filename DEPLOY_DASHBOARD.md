# Deploying the Team Dashboard to Streamlit Cloud

The dashboard (`dashboard.py`) has NO browser or Instagram login — it's pure
Supabase reads/writes, so it deploys cleanly to Streamlit Cloud (free tier).

---

## Step 1 — Push only the dashboard files to a GitHub repo

Create a **new, private** GitHub repo (e.g. `creator-scout-dashboard`).

Files to include (copy these from this folder):
```
dashboard.py
db.py
requirements-dashboard.txt   ← use THIS, not requirements.txt
```

Rename it to `requirements.txt` when pushing, OR tell Streamlit Cloud to use
`requirements-dashboard.txt` in the advanced settings.

**Do NOT push:** `agent.py`, `scraper.py`, `app.py`, `.streamlit/secrets.toml`,
`browser_profiles/`, `ig_sessions/`, `results/`

Quick way to create the repo and push:
```bash
mkdir creator-scout-dashboard
cp dashboard.py db.py requirements-dashboard.txt creator-scout-dashboard/
cd creator-scout-dashboard
cp requirements-dashboard.txt requirements.txt
git init && git add . && git commit -m "init dashboard"
gh repo create creator-scout-dashboard --private --push --source=.
```

---

## Step 2 — Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io → **New app**
2. Connect your GitHub account → pick `creator-scout-dashboard` repo
3. Main file path: `dashboard.py`
4. Click **Advanced settings** → paste secrets:

```toml
supabase_url = "https://xxxx.supabase.co"
supabase_key = "sb_secret_xxxxxxxx"

# Optional — only needed if you use the Google Sheet push button
# gsheet_webapp_url = "https://script.google.com/macros/s/xxxx/exec"
```

5. Click **Deploy** — takes ~1 min to build

---

## Step 3 — Share the URL with the team

Streamlit gives you a URL like:
```
https://your-name-creator-scout-dashboard-dashboard-xxxx.streamlit.app
```

Send this to the team. Anyone who opens it can:
- Queue scrape jobs (agents on local laptops pick them up)
- See job status in real time
- Browse the shared creator database + CRM
- Push selected creators to Google Sheets

---

## Agents still run locally

Each team member who wants to run scrapes must still have:
- The full `instagram-scraper` folder (with Playwright + Instagram session)
- `python3 agent.py` running in a terminal

The cloud dashboard just shows what agents are online and sends them jobs.
Agents heartbeat every 5s — the sidebar shows 🟢 if an agent was seen in the
last 40 seconds.

---

## Updating the dashboard

Just push to the GitHub repo — Streamlit Cloud auto-redeploys in ~30s.
The local agents don't need to update.
