#!/bin/bash
cd "$(dirname "$0")"
echo "================================"
echo "  Creator Scout Agent"
echo "================================"
echo ""

# Install dependencies if needed
echo "Checking dependencies..."
pip3 install supabase toml playwright playwright-stealth requests --quiet 2>/dev/null || \
python3 -m pip install supabase toml playwright playwright-stealth requests --quiet 2>/dev/null

# Install playwright browsers if needed
python3 -m playwright install chromium 2>/dev/null

echo ""
python3 agent.py
