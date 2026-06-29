#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Creator Scout — Agent Launcher (Mac)
# Double-click this file to start the agent.
# ─────────────────────────────────────────────────────────────────────────────

# Go to the folder where this script lives
cd "$(dirname "$0")"

CONFIG="config.txt"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       Creator Scout — Agent              ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: Read config.txt ───────────────────────────────────────────────────
if [ ! -f "$CONFIG" ]; then
  echo "❌  config.txt not found!"
  echo ""
  echo "Create a file called config.txt in this folder with these two lines:"
  echo ""
  echo "   NAME=YourName"
  echo "   SUPABASE_URL=https://xxxx.supabase.co"
  echo "   SUPABASE_KEY=sb_secret_xxxx"
  echo ""
  read -p "Press Enter to exit..."
  exit 1
fi

# Parse config.txt
NAME=$(grep -i "^NAME=" "$CONFIG" | cut -d'=' -f2- | tr -d '[:space:]')
SUPABASE_URL=$(grep -i "^SUPABASE_URL=" "$CONFIG" | cut -d'=' -f2- | tr -d '[:space:]')
SUPABASE_KEY=$(grep -i "^SUPABASE_KEY=" "$CONFIG" | cut -d'=' -f2- | tr -d '[:space:]')

if [ -z "$NAME" ] || [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
  echo "❌  config.txt is incomplete. It must have:"
  echo "   NAME=YourName"
  echo "   SUPABASE_URL=https://xxxx.supabase.co"
  echo "   SUPABASE_KEY=sb_secret_xxxx"
  echo ""
  read -p "Press Enter to exit..."
  exit 1
fi

echo "👤  Agent name   : $NAME"
echo "🔗  Supabase     : $SUPABASE_URL"
echo ""

# ── Step 2: Check Python ──────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    MAJOR=$(echo "$VER" | cut -d. -f1)
    MINOR=$(echo "$VER" | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
      PYTHON="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "❌  Python 3.9+ not found."
  echo "    Install it from https://www.python.org/downloads/"
  echo "    Then double-click this file again."
  echo ""
  read -p "Press Enter to exit..."
  exit 1
fi

echo "✅  Python found: $($PYTHON --version)"

# ── Step 3: Install dependencies (first time only, ~1 min) ───────────────────
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo ""
  echo "📦  First-time setup: installing packages (~1-2 min)..."
  $PYTHON -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
  "$VENV_DIR/bin/pip" install --quiet \
    streamlit pandas openpyxl requests "supabase>=2.3.0" toml \
    playwright playwright-stealth
  echo "🌐  Downloading browser (~150 MB, one-time only)..."
  "$VENV_DIR/bin/python" -m playwright install chromium
  echo "✅  Setup complete!"
fi

# ── Step 4: Write secrets so db.py can read them ─────────────────────────────
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<EOF
supabase_url = "$SUPABASE_URL"
supabase_key = "$SUPABASE_KEY"
EOF

# ── Step 5: Run the agent ─────────────────────────────────────────────────────
echo ""
echo "🚀  Starting agent as '$NAME'..."
echo "    Keep this window open while scraping."
echo "    Close it (or press Ctrl+C) to stop."
echo ""

AGENT_ACCOUNT="$NAME" "$VENV_DIR/bin/python" agent.py
