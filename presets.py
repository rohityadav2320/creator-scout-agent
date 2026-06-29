"""
Search preset manager for Creator Scout.
Saves/loads named hashtag search configurations to a local JSON file.
"""
import json
import os

PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets.json")


def load_presets():
    """Return dict of {preset_name: settings_dict}."""
    if not os.path.exists(PRESETS_FILE):
        return {}
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_preset(name, settings):
    """Save or overwrite a preset by name."""
    presets = load_presets()
    presets[name] = settings
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)


def delete_preset(name):
    """Delete a preset by name."""
    presets = load_presets()
    presets.pop(name, None)
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)
