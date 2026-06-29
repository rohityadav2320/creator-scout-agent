#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Creator Scout — Chrome launcher for CDP scraping
#
# Opens a SEPARATE Chrome window (its own profile, won't touch your main Chrome)
# with remote debugging on port 9222. Log into Instagram in this window ONCE,
# keep it open, and the portal will connect to it — real Chrome = no bot detection.
#
# Usage: double-click this file, or run:  bash launch_chrome.command
# ─────────────────────────────────────────────────────────────────────────────

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="$HOME/chrome-ig-debug"

echo "🚀 Launching Chrome with debugging on port 9222..."
echo "   Profile: $PROFILE (separate from your main Chrome)"
echo ""
echo "👉 Log into Instagram in the window that opens, then keep it open."
echo "   Run your Hashtag / Reference Creator search in the portal."
echo ""

# Use `open -na` so Chrome launches as a fully detached GUI app (won't die when
# this terminal closes) on its own separate profile.
open -na "Google Chrome" --args \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE" \
  --no-first-run \
  --no-default-browser-check \
  "https://www.instagram.com/"

echo "✅ Chrome launched. Leave the Chrome window open while scraping."
