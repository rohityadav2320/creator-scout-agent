#!/bin/bash
# Launch the Creator Scout portal
cd "$(dirname "$0")"
python3 -m streamlit run app.py
