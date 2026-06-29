"""
Quick CLI to QUEUE a scrape job — for testing the agent before the web
dashboard exists. (Later, the dashboard does this.)

Usage:
  python3 queue_job.py hashtag tamilskit,tamilcomedy
  python3 queue_job.py reference some_creator_username
  python3 queue_job.py hashtag tamilskit account_label     # target a specific agent
"""
import sys
import db


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python3 queue_job.py hashtag tag1,tag2 [account_label]")
        print("  python3 queue_job.py reference user1,user2 [account_label]")
        return
    if not db.is_configured():
        print("❌ Supabase not configured (.streamlit/secrets.toml or env vars).")
        return

    jtype = sys.argv[1].strip().lower()
    items = [x.strip().lstrip("#@") for x in sys.argv[2].split(",") if x.strip()]
    account = sys.argv[3].strip() if len(sys.argv) > 3 else ""

    if jtype == "hashtag":
        params = {"hashtags": items, "max": 20, "enrich": True}
    elif jtype == "reference":
        params = {"seeds": items, "max": 50, "depth": 1}
    else:
        print("Type must be 'hashtag' or 'reference'.")
        return

    jid, err = db.create_job(jtype, params, account_label=account, created_by="test")
    if err:
        print(f"❌ Error: {err}")
    else:
        print(f"✅ Queued job #{jid} ({jtype}: {', '.join(items)})"
              + (f" for account '{account}'" if account else ""))
        print("   Now run the agent (python3 agent.py) on a machine to pick it up.")


if __name__ == "__main__":
    main()
