#!/usr/bin/env python3
"""
Creator Scout — Agent Launcher
Double-click to start. No setup needed.
"""
import os
import sys
import subprocess

# Stable data directory — survives across binary runs
DATA_DIR = os.path.join(os.path.expanduser("~"), "CreatorScout")
NAME_FILE = os.path.join(DATA_DIR, "name.txt")

# Team credentials — injected at build time (see _build_creds.py, gitignored)
try:
    from _build_creds import SUPABASE_URL, SUPABASE_KEY
except ImportError:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

BANNER = """
╔══════════════════════════════════════════╗
║       🎬  Creator Scout — Agent          ║
╚══════════════════════════════════════════╝
"""


def get_name():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(NAME_FILE):
        name = open(NAME_FILE).read().strip()
        if name:
            return name
    print("First-time setup — this runs once.\n")
    name = input("Enter your name (e.g. Rohit, Priya): ").strip()
    while not name:
        name = input("Name cannot be empty: ").strip()
    with open(NAME_FILE, "w") as f:
        f.write(name)
    print(f"\n✅ Saved as '{name}'. Won't be asked again.\n")
    return name


def ensure_browser():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            if os.path.exists(p.chromium.executable_path):
                return
    except Exception:
        pass
    print("📦 Downloading browser (~150 MB) — one-time only, please wait...\n")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                   check=False)


def main():
    print(BANNER)

    name = get_name()

    # Point all file I/O to the stable data dir
    os.environ["CREATOR_SCOUT_DATA_DIR"] = DATA_DIR
    os.environ["SUPABASE_URL"] = SUPABASE_URL
    os.environ["SUPABASE_KEY"] = SUPABASE_KEY
    os.environ["AGENT_ACCOUNT"] = name

    # If running as PyInstaller bundle, add extracted dir to path so agent/scraper imports work
    if hasattr(sys, "_MEIPASS"):
        sys.path.insert(0, sys._MEIPASS)

    ensure_browser()

    print(f"🚀 Starting as '{name}'... (Ctrl+C to stop)\n")

    from agent import main as agent_main
    agent_main()


if __name__ == "__main__":
    main()
