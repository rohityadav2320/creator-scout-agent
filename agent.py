"""
Creator Scout — Local Agent
============================

Runs on a team member's computer. It watches the shared database for queued
scrape jobs, runs them LOCALLY (real browser + your Instagram login + your home
internet IP — so Instagram doesn't block it), and writes results back to the
shared database. The web dashboard only QUEUES jobs; this agent does the actual
scraping. This reuses the same proven scraper.py — nothing about the local
Streamlit portal changes.

SETUP (once)
------------
1. This folder must have `.streamlit/secrets.toml` with `supabase_url` /
   `supabase_key` (same file the portal uses), OR set env vars
   `SUPABASE_URL` / `SUPABASE_KEY`.
2. Set this machine's account label (the Instagram account it scrapes with):
       export AGENT_ACCOUNT=chits          # Mac/Linux
       set AGENT_ACCOUNT=chits             # Windows
   …or just create a file `agent_account.txt` next to this script with the label.

RUN
---
    python3 agent.py

The first scrape opens a Chromium window — log into Instagram once; the session
is saved and reused. Leave this running (minimise the window) to stay available.
"""
import os
import time
import traceback

import db
from scraper import run_scrape_hashtags, run_scrape_seed, run_scrape

POLL_SECONDS = 5
_DIR = os.path.dirname(os.path.abspath(__file__))


def _account_label():
    label = os.environ.get("AGENT_ACCOUNT", "").strip()
    if not label:
        p = os.path.join(_DIR, "agent_account.txt")
        if os.path.exists(p):
            try:
                label = open(p).read().strip()
            except Exception:
                pass
    return label


def _run_job(job, account):
    """Dispatch a job to the right scraper. Returns (result_count, error)."""
    jtype = job.get("type")
    params = job.get("params") or {}
    jid = job.get("id")
    created_by = job.get("created_by", "") or ""
    # ig_account in params overrides the agent's default account
    ig_account = params.get("ig_account", "").strip() or account

    def progress(msg):
        db.update_job(jid, progress=msg)

    if jtype == "hashtag":
        tags = params.get("hashtags") or []
        if not tags:
            return 0, "No hashtags in job params."
        reels, err = run_scrape_hashtags(
            ig_account, tags, int(params.get("max", 50)),
            scraped_by=created_by,
            enrich=bool(params.get("enrich", True)),
            progress_callback=progress,
        )
    elif jtype == "reference":
        seeds = params.get("seeds") or []
        if not seeds:
            return 0, "No seed creators in job params."
        reels, _signals, err = run_scrape_seed(
            ig_account, seeds, int(params.get("max", 100)),
            scraped_by=created_by,
            mode="hashtags",
            depth=int(params.get("depth", 1)),
            progress_callback=progress,
        )
    elif jtype == "trained_feed":
        # Uses the same browser engine as hashtag/reference — NO instagrapi, NO session ID.
        # Agent opens Chromium with the account's saved session, goes to /reels/ feed,
        # scrolls and collects creators just like a human would.
        reels, err = run_scrape(
            ig_account, None, int(params.get("max", 50)),
            progress_callback=progress,
            scraped_by=created_by,
        )
        if err:
            return 0, err
        reels = reels or []
        # Filter by min/max followers
        min_fol = int(params.get("min_followers", 0))
        max_fol = int(params.get("max_followers", 0))
        if min_fol:
            reels = [r for r in reels if int(r.get("followers", 0) or 0) >= min_fol]
        if max_fol:
            reels = [r for r in reels if int(r.get("followers", 0) or 0) <= max_fol]
        # Filter by hashtags — only keep reels whose caption/hashtags contain any of the given tags
        feed_tags = [t.strip().lower().lstrip("#") for t in params.get("feed_hashtags", []) if t.strip()]
        if feed_tags:
            def _has_tag(r):
                reel_tags = [h.lower().lstrip("#") for h in (r.get("hashtags") or [])]
                caption = (r.get("caption") or "").lower()
                return any(tag in reel_tags or tag in caption for tag in feed_tags)
            reels = [r for r in reels if _has_tag(r)]
        if reels:
            db.upsert_reels(reels, scraped_by=created_by, scraped_from=ig_account)
        return len(reels), None
    else:
        return 0, f"Unknown job type: {jtype}"

    if err:
        return 0, err
    reels = reels or []
    # Filter by min/max followers
    min_fol = int(params.get("min_followers", 0))
    max_fol = int(params.get("max_followers", 0))
    if min_fol:
        reels = [r for r in reels if int(r.get("followers", 0) or 0) >= min_fol]
    if max_fol:
        reels = [r for r in reels if int(r.get("followers", 0) or 0) <= max_fol]
    if reels:
        db.upsert_reels(reels, scraped_by=created_by, scraped_from=ig_account)
    return len(reels), None


def main():
    if not db.is_configured():
        print("❌ Supabase not configured. Add supabase_url/supabase_key to "
              ".streamlit/secrets.toml (or env vars) and try again.")
        return

    account = _account_label()
    label = account or "agent"
    print(f"✅ Agent '{label}' online. Watching for jobs…  (Ctrl+C to stop)")
    if not account:
        print("ℹ️  No AGENT_ACCOUNT set — this agent will pick up jobs for ANY account.")

    while True:
        try:
            db.agent_heartbeat(label)
            job = db.claim_next_job(label, account)
            if not job:
                time.sleep(POLL_SECONDS)
                continue

            jid = job.get("id")
            print(f"▶ Job #{jid} ({job.get('type')}) — starting…")
            try:
                n, err = _run_job(job, account)
                if err:
                    db.update_job(jid, status="error", error=err)
                    print(f"✖ Job #{jid} error: {err}")
                else:
                    db.update_job(jid, status="done", result_count=n,
                                  progress=f"Done — {n} creators")
                    print(f"✔ Job #{jid} done — {n} creators saved")
            except Exception as e:
                db.update_job(jid, status="error", error=str(e))
                print(f"✖ Job #{jid} crashed: {e}")
                traceback.print_exc()

        except KeyboardInterrupt:
            print("\nAgent stopped.")
            break
        except Exception as e:
            print(f"Agent loop error: {e}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
