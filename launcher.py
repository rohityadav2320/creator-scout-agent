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
# Browsers go in a STABLE folder (not the temp _MEIPASS bundle dir that gets
# wiped every run). MUST be set before Playwright is imported anywhere.
BROWSERS_DIR = os.path.join(DATA_DIR, "ms-playwright")
os.makedirs(BROWSERS_DIR, exist_ok=True)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSERS_DIR

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


def start_identity_server(name):
    """Expose this agent's name on localhost so the web portal can detect that
    it's running on THIS machine and lock the 'Your name' field to it.
    Binds to 127.0.0.1 only (no firewall prompt, not reachable from network)."""
    import threading
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code=200):
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Content-Type", "application/json")
            self.end_headers()

        def do_OPTIONS(self):
            self._send(204)

        def do_GET(self):
            self._send(200)
            self.wfile.write(json.dumps({"name": name}).encode())

        def log_message(self, *args):
            pass  # stay quiet

    def run():
        for port in (17613, 17614, 17615):
            try:
                srv = HTTPServer(("127.0.0.1", port), Handler)
                srv.serve_forever()
                return
            except OSError:
                continue  # port busy, try next

    threading.Thread(target=run, daemon=True).start()


def ensure_browser():
    # Already installed in our stable folder?
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            if os.path.exists(p.chromium.executable_path):
                return  # Already installed
    except Exception:
        pass

    print("📦 First run: downloading browser (~150 MB). Takes a few minutes — please wait...\n")

    # Install using the Playwright driver that's BUNDLED inside this app
    # (works even with no system Python / no pip).
    try:
        from playwright.__main__ import main as pw_main
        old_argv = sys.argv
        sys.argv = ["playwright", "install", "chromium"]
        try:
            pw_main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
        print("\n✅ Browser ready.\n")
        return
    except Exception as e:
        print(f"⚠️  Bundled install failed ({e}); trying system Python...\n")

    # Fallback: system python (only if available)
    for python in ["python3", "python"]:
        try:
            result = subprocess.run(
                [python, "-m", "playwright", "install", "chromium"],
                env={**os.environ}, timeout=600, check=False
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue


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

    # Let the web portal auto-detect this agent on this machine
    start_identity_server(name)

    print(f"🚀 Starting as '{name}'... (Ctrl+C to stop)\n")

    from agent import main as agent_main
    agent_main()


if __name__ == "__main__":
    main()
