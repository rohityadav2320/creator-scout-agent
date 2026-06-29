# Creator Scout — Setup Guide (for the team)

Creator Scout finds Instagram creators by hashtag and "similar creator", saves
them to a shared database, and tracks your outreach (DM status). Every teammate
runs it **on their own laptop** — there's no shared website, because the tool
opens a real browser window for you to log into Instagram.

Everyone's results go to the **same Supabase database**, so the team builds one
shared creator list together.

---

## 1. One-time install (≈10 minutes)

**You need:** a Mac or Windows laptop with **Python 3.9+**.
Check by opening Terminal (Mac) / Command Prompt (Windows) and running:
```
python3 --version
```
If it's missing, install it from https://www.python.org/downloads/ (tick
"Add Python to PATH" on Windows).

**Get the project folder** (Rohit will share the `instagram-scraper` folder —
via Google Drive / zip). Put it somewhere easy like your Desktop.

**Open Terminal in that folder and install everything:**
```
cd path/to/instagram-scraper
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```
(The second line downloads the browser the tool drives — needed once.)

---

## 2. Connect the shared database (one-time)

Create a file at `.streamlit/secrets.toml` inside the folder with the Supabase
credentials Rohit gives you:
```
supabase_url = "https://xxxx.supabase.co"
supabase_key = "sb_secret_xxxxxxxx"
```
> ⚠️ Never share this file or upload it anywhere public. It's the team key.

If the `reels` table is new, run this **once** in the Supabase SQL editor
(Dashboard → SQL Editor → paste → Run) — it's safe to re-run:
```sql
alter table reels add column if not exists status       text default 'To Contact';
alter table reels add column if not exists notes        text default '';
alter table reels add column if not exists scraped_by   text default '';
alter table reels add column if not exists scraped_from text default '';
alter table reels add column if not exists batch_id     text default '';
alter table reels add column if not exists engagement_rate float default 0;
alter table reels add column if not exists category      text default '';
alter table reels add column if not exists contact_email text default '';
alter table reels add column if not exists bio           text default '';
alter table reels add column if not exists external_url  text default '';
```

---

## 3. Run it

**Discovery portal** (Hashtag Search + Reference Creator + Database/CRM):
```
python3 -m streamlit run app.py
```
Opens at http://localhost:8502

**Trained Feed portal** (separate — optional, for later):
```
python3 -m streamlit run app_feed.py --server.port 8503
```
Opens at http://localhost:8503

To stop a portal: click the Terminal and press **Ctrl + C**.

---

## 4. How to use (Discovery)

1. In the sidebar, type **Your name** (so the team knows who found whom) and an
   **Instagram username** (use a **burner account**, not your personal/Vidrow one).
2. Go to **Hashtag Search** → enter 4-5 hashtags (comma or space separated) →
   **Quick Preview** (fast sample) or **Full Search**.
3. A **Chromium browser window opens** — **log into Instagram there** (any burner).
   Scraping starts automatically once you're logged in.
4. Review the creators → tick the ones to keep → **Save to Database**.
5. **Reference Creator** tab: paste a good creator → get 10+ similar ones.
6. **Database** tab: see all creators, set **Status** (To Contact → Contacted →
   Replied → Negotiating → Confirmed → Rejected), add **Notes**, **Save changes**.
   This is your outreach tracker — the whole team shares it.

---

## Tips & troubleshooting

- **"No new creators found / all already seen"** → those creators are already in
  your seen-list from a past search. Click **🗑️ Clear** (resets the list) or use
  different hashtags.
- **Use a burner Instagram account** — heavy scraping can get an account
  rate-limited ("we limit how often..."). If that happens, wait a few hours or
  use a different burner. Don't hammer one account all day.
- **`streamlit` command not found** → always launch with `python3 -m streamlit run ...`
- **Rotate hashtags** — Instagram shows the same top creators for the same tag.
  Different tags + Reference Creator = more unique creators.
- Results also save locally to the `results/` folder (CSV + Excel) as a backup.
