import io
import os
import threading
from datetime import datetime
import streamlit as st
import pandas as pd

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_usernames.json")


def _load_seen():
    import json
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_seen(seen: set):
    import json
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception:
        pass
from scraper import run_scrape, run_extract_reference, run_scrape_hashtags, run_scrape_seed, run_scrape_reference_reel, open_training_browser
from filters import apply_filters, filters_from_reference_reel, LANG_CODES, CREATOR_STYLE_TAGS, get_style_search_hashtags, extract_keywords
import db
from presets import load_presets, save_preset, delete_preset
from hashtag_library import HASHTAG_LIBRARY, get_all_hashtags

st.set_page_config(
    page_title="Creator Scout — Vidrow",
    page_icon="🎬",
    layout="wide",
)

# ── Session state defaults ──────────────────────────────────────────────────
for key, default in {
    "reels": [],           # accumulated across searches (deduped by username)
    "filtered_reels": [],
    "scraping": False,
    "logged_in": False,
    "ref_reel_data": None,
    "progress_msg": "",
    "error": "",
    "scrape_meta": {},
    "active_filters": {},
    "ht_preview_results": [],  # quick preview — separate from main pool
    "seed_signals": {},        # detected styles + hashtags from last seed run
    "seen_usernames": _load_seen(),   # persists across sessions via file
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helpers ─────────────────────────────────────────────────────────────────
def fmt_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def to_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Creators")
    return buf.getvalue()


def to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


def push_to_gsheet(creators):
    """POST selected creators to the Google Sheet Apps Script web app.
    Reads the web-app URL from secrets (gsheet_webapp_url). Returns (ok, message)."""
    import requests
    try:
        url = st.secrets.get("gsheet_webapp_url", "")
    except Exception:
        url = ""
    if not url:
        return False, ("Google Sheet not connected — add `gsheet_webapp_url = \"...\"` to "
                       "`.streamlit/secrets.toml` (the Apps Script web-app URL).")
    if not creators:
        return False, "No creators ticked for the sheet."
    try:
        resp = requests.post(url, json={"creators": creators}, timeout=25)
        if resp.status_code in (200, 302):
            try:
                data = resp.json()
                added = data.get("added", len(creators))
                skipped = data.get("skipped", 0)
                msg = f"Added {added} to the sheet"
                if skipped:
                    msg += f" · skipped {skipped} (already in sheet)"
                return True, msg + "."
            except Exception:
                return True, f"Sent {len(creators)} creator(s) to your Google Sheet."
        return False, f"Sheet responded with status {resp.status_code}."
    except Exception as e:
        return False, f"Could not reach the sheet: {e}"


def render_reel_card(reel, idx):
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            uname = reel.get("username", "")
            profile_url = f"https://www.instagram.com/{uname}/" if uname else reel.get("reel_url", "")
            # @username links to the profile (for outreach); 'reel ↗' opens the reel.
            st.markdown(f"**[@{uname}]({profile_url})**  ·  [reel ↗]({reel.get('reel_url','')})")
            if reel.get("full_name"):
                st.caption(reel["full_name"])
            caption = reel.get("caption", "")
            st.write(caption[:180] + ("..." if len(caption) > 180 else ""))
            if reel.get("hashtags"):
                tags = " ".join(f"`#{h}`" for h in reel["hashtags"][:6])
                st.markdown(tags)
            if reel.get("detected_language"):
                st.markdown(f"**Language:** {reel['detected_language']}")
        with col2:
            st.metric("Views", fmt_number(reel.get("views", 0)))
            st.metric("Likes", fmt_number(reel.get("likes", 0)))
            if reel.get("followers"):
                st.metric("Followers", fmt_number(reel["followers"]))
            st.markdown(f"[Open Reel ↗]({reel['reel_url']})")


# ── Sidebar — Login ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 Creator Scout")
    st.caption("by Vidrow")
    st.divider()

    st.subheader("Your Name")
    scraped_by = st.text_input(
        "Your name (team member)", placeholder="e.g. Rohit",
        help="Tags every creator you scrape so the team can tell who found whom.",
    )

    st.divider()
    st.subheader("Instagram Login")
    st.caption("Hashtag & Reference open a **Chromium browser window** — log in there "
               "(any account) when it opens. No password or cookie needed here.")
    ig_user = st.text_input(
        "Instagram Username", placeholder="your_burner_username",
        help="Used to name the browser profile. You log in inside the browser window itself.",
    )
    ig_session = ""  # discovery uses manual browser login — not a cookie/sessionid

    st.caption("📱 For **Trained Feed**, use the separate portal "
               "(`python3 -m streamlit run app_feed.py --server.port 8503`).")

    st.divider()
    st.subheader("Scraping Settings")
    max_reels = st.slider("Max reels to scan", 10, 500, 50, step=10)

    st.divider()
    st.subheader("📩 DM Template")
    st.caption("Variables: `{name}` `{username}`")
    dm_template = st.text_area(
        "DM Template",
        value=st.session_state.get("dm_template", (
            "Hey {name}! 👋\n\n"
            "We're Vidrow, a creative marketing agency. "
            "We loved your content and would love to collaborate with you.\n\n"
            "Would you be open to a quick chat? 🙌"
        )),
        height=160,
        key="dm_template_input",
        label_visibility="collapsed",
    )
    st.session_state["dm_template"] = dm_template

    st.divider()
    st.caption("Use a burner account, not your main or Vidrow's official one.")


# ── Main content ─────────────────────────────────────────────────────────────
st.title("Creator Scout")
st.markdown("Find the right creators for your scripts — fast.")
st.divider()

tab_hashtag, tab_seed, tab_db = st.tabs(
    ["#️⃣ Hashtag Search", "🎯 Reference Creator", "🗄️ Database"]
)

# ── Tab: Hashtag Search (targeted discovery) ─────────────────────────────────
with tab_hashtag:
    style_auto_tags = []   # always defined — overwritten below after style multiselect
    st.subheader("Find creators by hashtag")
    st.caption("Targeted discovery — pulls reels from specific hashtag pages instead of "
               "your random home feed. Much higher hit-rate for the creator types you want.")

    with st.expander("ℹ️ How it works", expanded=False):
        st.markdown("""
**Step 1 — Pick your hashtags**
- Browse our curated library by niche (Comedy, Finance, Fitness, etc.)
- Or type any custom hashtag directly
- Select a Creator Style → its hashtags are auto-added to your search

**Step 2 — Quick Preview** *(optional)*
- Grabs ~10 creators fast via Instagram's mobile API (no browser)
- Shows a triage table — tick Keep / untick the ones you don't want
- Only kept creators go to the full search

**Step 3 — Full Search**
- Calls Instagram's mobile API for each hashtag's **top + recent** posts
- No browser, no cookies — fast and reliable, doesn't hang
- Collects one record per unique creator (username, likes, caption)

**Step 4 — Enrich**
- For each unique creator found, fetches their follower count, bio, contact email
- Skips creators already seen this session (no wasted API calls)
- One creator per username

**Step 5 — Review & Keep**
- Triage table sorted by ER% (new creators first, already-saved ones at bottom)
- Tick who you want → Save to Database
- Results accumulate across multiple searches (no data lost between runs)
""")

    # ── Preset loader (applied before widgets so values pre-fill) ────────────
    if "ht_preset_to_load" in st.session_state:
        p = st.session_state.pop("ht_preset_to_load")
        st.session_state["ht_input"]         = p.get("hashtags", "")
        st.session_state["ht_likes"]         = p.get("min_likes", 0)
        st.session_state["ht_minf"]          = p.get("min_followers", 0)
        st.session_state["ht_maxf"]          = p.get("max_followers", 0)
        st.session_state["ht_lang"]          = p.get("language", "any")
        st.session_state["ht_styles"]        = p.get("creator_styles", [])
        st.session_state["ht_creators_only"] = p.get("creators_only", True)
        st.session_state["ht_enrich"]        = p.get("enrich", True)

    all_presets = load_presets()
    if all_presets:
        pc1, pc2, pc3 = st.columns([3, 1, 1])
        with pc1:
            chosen_preset = st.selectbox(
                "📂 Load a saved search", ["— select preset —"] + list(all_presets.keys()),
                key="preset_select",
            )
        with pc2:
            if st.button("Load ↩️", use_container_width=True, key="preset_load"):
                if chosen_preset != "— select preset —":
                    st.session_state["ht_preset_to_load"] = all_presets[chosen_preset]
                    st.rerun()
        with pc3:
            if st.button("🗑 Delete", use_container_width=True, key="preset_delete"):
                if chosen_preset != "— select preset —":
                    delete_preset(chosen_preset)
                    st.success(f"Deleted '{chosen_preset}'")
                    st.rerun()
        st.divider()

    # ── Filter inputs ────────────────────────────────────────────────────────

    # Step 1 — Creator Style (comes first so its auto-tags can feed into hashtag picker)
    ht_styles = st.multiselect(
        "🎬 Creator Style — selecting one auto-adds its hashtags to the search",
        options=list(CREATOR_STYLE_TAGS.keys()),
        default=[],
        key="ht_styles_pills",
        placeholder="e.g. 🎤 Direct to Camera, 🎭 Skit / Acting",
        help="Pick a style → its hashtags are automatically added to your search pool.",
    )
    style_auto_tags = get_style_search_hashtags(ht_styles) if ht_styles else []
    if style_auto_tags:
        st.caption(f"✅ Auto-added from style: `{'`, `'.join(style_auto_tags[:8])}{'...' if len(style_auto_tags) > 8 else ''}`")

    # Step 2 — Hashtag picker (category shortcut + searchable multiselect)
    lib_col1, lib_col2 = st.columns([1, 2])
    with lib_col1:
        selected_category = st.selectbox(
            "📂 Pick a niche",
            ["— browse by category —"] + list(HASHTAG_LIBRARY.keys()),
            key="ht_category_picker",
        )
    with lib_col2:
        category_suggestions = (
            HASHTAG_LIBRARY.get(selected_category, [])
            if selected_category != "— browse by category —" else []
        )
        existing_tags = [t.strip() for t in st.session_state.get("ht_input", "").split(",") if t.strip()]
        default_tags = list(dict.fromkeys(existing_tags + category_suggestions))

        ht_selected_tags = st.multiselect(
            "Hashtags (type to search or pick from list)",
            options=get_all_hashtags(),
            default=[t for t in default_tags if t in get_all_hashtags()],
            key="ht_tags_multiselect",
            placeholder="Search hashtags e.g. 'comedy', 'finance'...",
        )

    # Step 3 — Custom hashtags not in library
    ht_custom = st.text_input(
        "➕ Add custom hashtags not in the list (comma separated, without #)",
        placeholder="mynewhashtag, anothertag",
        key="ht_custom_input",
    )
    # Merge: picked hashtags + custom + style auto-tags.
    # Accept commas OR spaces OR newlines between tags, and strip any leading '#'.
    custom_tags = [t.strip().lstrip("#")
                   for t in ht_custom.replace(",", " ").split()
                   if t.strip().lstrip("#")]
    all_selected_tags = list(dict.fromkeys(ht_selected_tags + custom_tags + style_auto_tags))
    st.session_state["ht_input"] = ", ".join(all_selected_tags)

    hc1, hc2, hc3, hc4 = st.columns(4)
    with hc1:
        ht_min_likes = st.number_input("Min Likes", min_value=0, value=0, step=500, key="ht_likes")
    with hc2:
        ht_min_followers = st.number_input("Min Followers", min_value=0, value=0, step=1000,
                                           help="Filter out tiny accounts. e.g. 5000 = only creators with 5k+ followers.",
                                           key="ht_minf")
    with hc3:
        ht_max_followers = st.number_input("Max Followers (0 = no limit)",
                                           min_value=0, value=0, step=10000, key="ht_maxf")
    with hc4:
        ht_language = st.selectbox("Language", ["any"] + list(LANG_CODES.keys()), key="ht_lang")

    ht_creators_only = st.checkbox(
        "🙅 Exclude clip / movie / cartoon / meme channels (keep real creators)",
        value=True, key="ht_creators_only",
    )
    ht_enrich = st.checkbox(
        "🔍 Fetch follower count + category + contact email (slower, recommended)",
        value=True, key="ht_enrich",
    )

    ht_filters = {
        "min_likes": int(ht_min_likes),
        "min_followers": int(ht_min_followers),
        "max_followers": int(ht_max_followers),
        "language": ht_language,
        "creator_styles": ht_styles,
        "content_types": [],
        "description": "",
        "hashtags": [],
        "creators_only": ht_creators_only,
    }

    # ── Save preset UI ───────────────────────────────────────────────────────
    with st.expander("💾 Save these settings as a preset"):
        sv1, sv2 = st.columns([3, 1])
        with sv1:
            preset_name = st.text_input("Preset name", placeholder="Hindi Comedy Pack", key="preset_name")
        with sv2:
            st.write("")
            st.write("")
            if st.button("Save ✅", use_container_width=True, key="preset_save"):
                if not preset_name.strip():
                    st.error("Enter a name for the preset.")
                elif not all_selected_tags:
                    st.error("Select at least one hashtag before saving.")
                else:
                    save_preset(preset_name.strip(), {
                        "hashtags":       ", ".join(all_selected_tags),
                        "min_likes":      int(ht_min_likes),
                        "min_followers":  int(ht_min_followers),
                        "max_followers":  int(ht_max_followers),
                        "language":       ht_language,
                        "creator_styles": ht_styles,
                        "creators_only":  ht_creators_only,
                        "enrich":         ht_enrich,
                    })
                    st.success(f"✅ Saved preset '{preset_name.strip()}'")
                    st.rerun()

    # ── Action buttons ───────────────────────────────────────────────────────
    btn1, btn2, btn3 = st.columns([3, 2, 1])
    with btn3:
        if st.button("🗑️ Clear", use_container_width=True, key="ht_clear"):
            st.session_state.reels = []
            st.session_state.filtered_reels = []
            st.session_state.ht_preview_results = []
            st.session_state.seen_usernames = set()
            _save_seen(set())
            st.session_state.error = ""
            st.rerun()
    with btn2:
        ht_preview = st.button("👁️ Quick Preview", use_container_width=True, key="ht_preview",
                               help="Grab ~15 creators fast (no enrichment) to check if this "
                                    "hashtag has the right type before doing a full scrape.")
    with btn1:
        ht_go = st.button("🔎 Full Search", type="primary", use_container_width=True, key="ht_go")

    # ── Quick Preview ────────────────────────────────────────────────────────
    if ht_preview:
        tags = all_selected_tags
        if not ig_user:
            st.error("Enter your Instagram username in the sidebar (for the browser profile).")
        elif not tags:
            st.error("Enter at least one hashtag.")
        else:
            st.session_state.ht_preview_results = []
            ht_prev_log = []
            ht_prev_area = st.empty()
            ht_prev_area.warning("🪟 A Chromium window opens — **log in there if asked** "
                                 "(any account). Scraping starts automatically once you're in.")

            def ht_prev_progress(msg):
                ht_prev_log.append(msg)
                ht_prev_area.info("  \n".join(f"• {m}" for m in ht_prev_log[-6:]))

            with st.spinner("⚡ Quick preview — browser open, scraping hashtag pages..."):
                try:
                    prev_reels, prev_err = run_scrape_hashtags(
                        ig_user, tags, max_reels=10,
                        scraped_by=scraped_by, enrich=True, max_scrolls=5,
                        progress_callback=ht_prev_progress,
                    )
                    if prev_err:
                        ht_prev_area.error(f"❌ {prev_err}")
                    else:
                        # Mark which creators are already in the shared team DB (+ who found them)
                        known = db.fetch_known_profiles() if db.is_configured() else {}
                        for r in (prev_reels or []):
                            u = r.get("username", "")
                            r["already_in_db"] = u in known
                            r["db_finder"] = known.get(u, {}).get("scraped_by", "") if u in known else ""
                        # Filter out already-seen creators
                        fresh = [r for r in (prev_reels or [])
                                 if r.get("username") not in st.session_state.seen_usernames]
                        dup_count = len(prev_reels or []) - len(fresh)
                        if dup_count:
                            st.info(f"✅ {len(fresh)} new creators · {dup_count} duplicates removed")
                        st.session_state.seen_usernames.update(r.get("username") for r in fresh if r.get("username"))
                        _save_seen(st.session_state.seen_usernames)
                        st.session_state.ht_preview_results = fresh
                        if not fresh:
                            st.warning("No new creators found — all were already seen. Try a different hashtag or click Clear to reset.")
                except Exception as e:
                    st.error(f"Preview crashed: {e}")

    if st.session_state.ht_preview_results:
        st.markdown("#### 👁️ Preview — Keep or Skip")
        st.caption("Open the reel, decide if the creator is right, tick Keep. Then save directly to DB.")
        _saved_n = sum(1 for r in st.session_state.ht_preview_results if r.get("already_in_db"))
        _new_n = len(st.session_state.ht_preview_results) - _saved_n
        st.caption(f"🆕 **{_new_n} new** · ✅ {_saved_n} already in DB (unticked by default)")

        prev_triage_df = pd.DataFrame([
            {
                "Keep": not r.get("already_in_db", False),   # already saved → untick by default
                "→ Sheet": False,
                "In DB": (f"✅ {r.get('db_finder')}" if r.get("db_finder") else "✅ Saved")
                         if r.get("already_in_db") else "🆕 New",
                "Profile": f"https://www.instagram.com/{r.get('username','')}/" if r.get("username") else "",
                "Reel": r.get("reel_url", ""),
                "Followers": r.get("followers", 0),
                "ER %": round(r.get("engagement_rate", 0.0), 2),
                "Likes": r.get("likes", 0),
                "Hashtags": ", ".join(r.get("hashtags", [])[:5]),
                "Caption": (r.get("caption", "") or "")[:120],
                "_url": r.get("reel_url", ""),
                "_username": r.get("username", ""),
                "_email": r.get("contact_email", ""),
                "_language": r.get("detected_language", ""),
            }
            for r in st.session_state.ht_preview_results
        ])

        edited_prev = st.data_editor(
            prev_triage_df, use_container_width=True, hide_index=True,
            key="prev_triage_editor",
            column_config={
                "Keep": st.column_config.CheckboxColumn("Keep", default=True, width="small"),
                "→ Sheet": st.column_config.CheckboxColumn("→ Sheet", default=False, width="small",
                                                           help="Tick to send this creator to your Google Sheet"),
                "In DB": st.column_config.TextColumn("In DB", width="small",
                                                     help="✅ Saved = already in your team database · 🆕 New = not yet"),
                "Profile": st.column_config.LinkColumn("Profile", display_text=r"instagram\.com/([^/]+)"),
                "Reel": st.column_config.LinkColumn("Reel", display_text="watch ↗"),
                "Followers": st.column_config.NumberColumn("Followers", format="%d"),
                "ER %": st.column_config.NumberColumn("ER %", format="%.2f"),
                "Likes": st.column_config.NumberColumn("Likes", format="%d"),
                "_url": None, "_username": None, "_email": None, "_language": None,
            },
            disabled=[c for c in prev_triage_df.columns if c not in ("Keep", "→ Sheet")],
        )

        # Send ticked preview creators to the Google Sheet
        prev_sheet_rows = edited_prev[edited_prev["→ Sheet"] == True]  # noqa: E712
        n_prev_sheet = len(prev_sheet_rows)
        if st.button(f"📤 Send {n_prev_sheet} ticked → Google Sheet", use_container_width=True,
                     disabled=n_prev_sheet == 0, key="push_sheet_preview"):
            payload = [{"name": row["_username"], "username": row["_username"],
                        "email": row["_email"], "language": row["_language"]}
                       for _, row in prev_sheet_rows.iterrows()]
            ok, msg = push_to_gsheet(payload)
            st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")

        kept_prev_urls = set(edited_prev[edited_prev["Keep"] == True]["_url"].tolist())  # noqa: E712
        kept_prev = [r for r in st.session_state.ht_preview_results if r.get("reel_url") in kept_prev_urls]

        pc1, pc2 = st.columns([2, 3])
        with pc1:
            if st.button(f"💾 Save {len(kept_prev)} kept → Database", type="primary",
                         use_container_width=True, key="save_preview_kept"):
                if not kept_prev:
                    st.warning("Tick at least one creator to keep.")
                elif not db.is_configured():
                    st.warning("Supabase not connected — credentials missing in secrets.toml.")
                else:
                    meta = st.session_state.get("scrape_meta", {})
                    bid = datetime.now().strftime("%Y%m%d_%H%M%S")
                    new_n, known_n, err = db.upsert_reels(
                        kept_prev,
                        scraped_by=meta.get("scraped_by", scraped_by),
                        batch_id=bid,
                        scraped_from=meta.get("scraped_from", ""),
                    )
                    if err:
                        st.error(f"Save error: {err}")
                    else:
                        st.session_state.pop("db_rows", None)
                        st.success(f"✅ Saved {len(kept_prev)} creators "
                                   f"({new_n} new, {known_n} already in bank). "
                                   "Note: no follower/email data — run Full Search for that.")
        with pc2:
            st.caption(f"**{len(kept_prev)} of {len(st.session_state.ht_preview_results)}** ticked")
        st.divider()

    # ── Full Search ──────────────────────────────────────────────────────────
    if ht_go:
        tags = all_selected_tags
        if not ig_user:
            st.error("Enter your Instagram username in the sidebar (for the browser profile).")
        elif not tags:
            st.error("Enter at least one hashtag.")
        else:
            st.session_state.error = ""
            st.session_state.active_filters = ht_filters
            known_profiles = db.fetch_known_profiles() if db.is_configured() else {}
            ht_full_log = []
            ht_full_area = st.empty()
            ht_full_area.warning("🪟 A Chromium window opens — **log in there if asked** "
                                 "(any account). Scraping starts automatically once you're in.")

            def ht_full_progress(msg):
                ht_full_log.append(msg)
                ht_full_area.info("  \n".join(f"• {m}" for m in ht_full_log[-8:]))

            with st.spinner("Searching hashtags in the browser — fetching followers + emails..."):
                reels, error = run_scrape_hashtags(
                    ig_user, tags, max_reels,
                    scraped_by=scraped_by, enrich=ht_enrich,
                    known_profiles=known_profiles,
                    progress_callback=ht_full_progress)
            if error:
                ht_full_area.error(f"❌ {error}")
                st.session_state.error = error
            else:
                raw = reels or []
                # Dedup by creator — keep highest-ER reel per username
                best = {}
                for r in raw:
                    u = r.get("username", "")
                    if not u:
                        continue
                    if u not in best or r.get("engagement_rate", 0) > best[u].get("engagement_rate", 0):
                        best[u] = r
                # Mark creators already in the shared team DB (+ who found them)
                db_usernames = set(known_profiles.keys())
                for r in best.values():
                    u = r.get("username", "")
                    r["already_in_db"] = u in db_usernames
                    r["db_finder"] = known_profiles.get(u, {}).get("scraped_by", "") if u in db_usernames else ""
                # Filter out already-seen creators this session
                already_seen = st.session_state.seen_usernames
                new_creators = {u: r for u, r in best.items() if u not in already_seen}
                dup_count = len(best) - len(new_creators)
                if dup_count:
                    st.info(f"✅ {len(new_creators)} new creators found · {dup_count} duplicates removed")
                else:
                    st.info(f"✅ {len(new_creators)} new creators found")
                # Update seen set
                st.session_state.seen_usernames.update(new_creators.keys())
                _save_seen(st.session_state.seen_usernames)
                # Accumulate only new creators into session reels
                existing = {r.get("username", ""): r for r in st.session_state.reels if r.get("username")}
                existing.update(new_creators)
                merged = list(existing.values())
                st.session_state.reels = merged
                st.session_state.filtered_reels = apply_filters(merged, ht_filters)
                st.session_state.active_filters = ht_filters
                st.session_state.scrape_meta = {
                    "scraped_by": scraped_by,
                    "scraped_from": ", ".join(f"#{t.lstrip('#')}" for t in tags),
                }

# ── Tab: Reference Creator ────────────────────────────────────────────────────
with tab_seed:
    st.subheader("Find creators like a reference")
    st.caption(
        "Type a creator whose style you want — we read their reels, detect their niche, "
        "and find similar creators on Instagram Explore."
    )

    with st.expander("ℹ️ How it works", expanded=False):
        st.markdown("""
- Fetches their last 12 reels via Instagram API
- Extracts niche hashtags (generic ones like #reels #viral filtered out)
- Auto-detects content style → adds curated hashtags from our style library
- Searches Instagram Explore with the combined tag list
- Enriches results with follower count, bio, contact email

**Limitation:** Works best when the reference creator uses niche-specific hashtags.
""")

    seed_input = st.text_area(
        "Creator usernames (comma or newline separated, without @)",
        placeholder="comedychakkar56, rahul_sketches, ...",
        height=70, key="seed_input")

    sc1, sc2 = st.columns(2)
    with sc1:
        seed_max = st.number_input("Max creators to find", min_value=10, max_value=500,
                                   value=100, step=10, key="seed_max")
    with sc2:
        seed_min_likes = st.number_input("Min Likes", min_value=0, value=0,
                                         step=500, key="seed_minlikes")
    sf1, sf2 = st.columns(2)
    with sf1:
        seed_min_followers = st.number_input("Min Followers (0 = no limit)", min_value=0,
                                             value=0, step=1000, key="seed_minf")
    with sf2:
        seed_max_followers = st.number_input("Max Followers (0 = no limit)", min_value=0,
                                             value=0, step=10000, key="seed_maxf")
    seed_creators_only = st.checkbox(
        "🙅 Exclude clip / movie / cartoon / meme channels", value=True, key="seed_co")

    seed_depth = st.select_slider(
        "🔗 Similar-creator depth",
        options=[0, 1, 2],
        value=1,
        key="seed_depth",
        help="0 = hashtags only · 1 = also pull Instagram's 'similar accounts' for each seed "
             "· 2 = also chain from those similar accounts (way more creators, slower).",
    )

    seed_filters = {
        "min_likes": int(seed_min_likes),
        "min_followers": int(seed_min_followers),
        "max_followers": int(seed_max_followers),
        "creators_only": seed_creators_only,
        "creator_styles": [],
        "hashtags": [], "content_types": [], "description": "", "language": "any",
    }

    # Last run analysis
    if st.session_state.get("seed_signals"):
        sig = st.session_state.seed_signals
        with st.expander("📊 Last run analysis", expanded=True):
            if sig.get("reel_username"):
                st.caption(f"Reference reel by @{sig['reel_username']}")
            if sig.get("detected_styles"):
                st.markdown(f"**Detected style:** {' · '.join(sig['detected_styles'])}")
            if sig.get("seed_hashtags") or sig.get("reel_hashtags"):
                tags = sig.get("seed_hashtags") or sig.get("reel_hashtags", [])
                st.markdown(f"**From content:** {' '.join('#'+t for t in tags)}")
            if sig.get("style_hashtags"):
                st.markdown(f"**Style library added:** {' '.join('#'+t for t in sig['style_hashtags'][:6])}")
            if sig.get("search_tags"):
                st.markdown(f"**Searched on Explore:** `{'`, `'.join('#'+t for t in sig['search_tags'])}`")

    if st.button("🔍 Find Similar Creators", type="primary", use_container_width=True, key="seed_go"):
        if not ig_user:
            st.error("Please enter your Instagram username in the sidebar.")
        else:
            st.session_state.reels = []
            st.session_state.filtered_reels = []
            st.session_state.error = ""
            st.session_state.seed_signals = {}
            st.session_state.active_filters = seed_filters

            ref_progress_area = st.empty()
            ref_progress_area.info("🪟 A Chromium window will open — log in if asked, then wait...")

            def ref_progress(msg):
                ref_progress_area.info(f"⏳ {msg}")

            known_profiles = db.fetch_known_profiles() if db.is_configured() else {}

            seeds = [s.strip().lstrip("@") for s in
                     st.session_state.get("seed_input", "").replace("\n", ",").split(",") if s.strip()]
            if not seeds:
                st.error("Enter at least one creator username.")
                st.stop()
            reels, signals, error = run_scrape_seed(
                ig_user, seeds, int(seed_max),
                progress_callback=ref_progress,
                scraped_by=scraped_by,
                known_profiles=known_profiles,
                mode="hashtags",
                session_id=ig_session or None,
                depth=int(seed_depth),
            )
            source_label = "creators: " + ", ".join(f"@{s}" for s in seeds)

            if error:
                ref_progress_area.error(f"❌ {error}")
                st.session_state.error = error
            else:
                st.session_state.reels = reels or []
                st.session_state.seed_signals = signals or {}
                st.session_state.filtered_reels = apply_filters(st.session_state.reels, seed_filters)
                st.session_state.scrape_meta = {"scraped_by": scraped_by, "scraped_from": source_label}
                styles_found = ", ".join(signals.get("detected_styles", [])) or "not detected"
                tags_searched = ", ".join(f"#{t}" for t in signals.get("search_tags", [])[:5])
                ref_progress_area.success(
                    f"✅ Done! Found **{len(reels or [])} creators** · "
                    f"Style: **{styles_found}** · Searched: {tags_searched}"
                )

# ── Tab 3: Database (Supabase) ───────────────────────────────────────────────
with tab_db:
    st.subheader("Stored Creator Database")
    st.caption("Every reel you scrape is saved here permanently (de-duplicated by reel link).")

    if not db.is_configured():
        st.warning(
            "⚠️ **Supabase is not connected yet.** Add your credentials to "
            "`.streamlit/secrets.toml` (or set `SUPABASE_URL` / `SUPABASE_KEY` env vars), "
            "then reload. Until then, your links are still saved locally in the "
            "`results/` folder (CSV + Excel)."
        )
    else:
        top = st.columns([1, 3])
        with top[0]:
            refresh = st.button("🔄 Refresh", use_container_width=True)
        # Cache the fetch in session so we don't hit the DB on every rerun.
        if refresh or "db_rows" not in st.session_state:
            with st.spinner("Loading from Supabase..."):
                st.session_state.db_rows, st.session_state.db_error = \
                    db.fetch_all_reels(limit=5000)

        rows = st.session_state.get("db_rows", [])
        db_error = st.session_state.get("db_error")
        if db_error:
            st.error(f"⚠️ {db_error}")
        elif not rows:
            st.info("Database is empty — no creators stored yet. Run a scrape and they'll appear here.")
        else:
            db_df = pd.DataFrame(rows)
            # Ensure CRM + team columns exist even if the ALTER hasn't been run yet.
            for col, default in [("status", "To Contact"), ("notes", ""),
                                 ("scraped_by", ""), ("scraped_from", ""),
                                 ("batch_id", "")]:
                if col not in db_df.columns:
                    db_df[col] = default
            db_df["status"] = db_df["status"].fillna("To Contact").replace("", "To Contact")
            db_df["notes"] = db_df["notes"].fillna("")
            db_df["scraped_by"] = db_df["scraped_by"].fillna("").replace("", "—")
            db_df["scraped_from"] = db_df["scraped_from"].fillna("").replace("", "—")
            # Clickable profile link derived from username (opens the creator's IG).
            db_df["profile"] = db_df["username"].fillna("").apply(
                lambda u: f"https://www.instagram.com/{u}/" if u else "")

            # Column order: outreach fields first, then the creator data.
            preferred = ["status", "profile", "followers", "engagement_rate", "likes",
                         "category", "contact_email", "scraped_by", "scraped_from",
                         "full_name", "reel_url", "comments", "hashtags", "notes",
                         "bio", "external_url", "caption", "username", "batch_id",
                         "first_scraped", "last_seen"]
            ordered = [c for c in preferred if c in db_df.columns] + \
                      [c for c in db_df.columns if c not in preferred]
            db_df = db_df[ordered]

            # ── Outreach pipeline metrics ──
            st.markdown("**📊 Outreach pipeline**")
            counts = db_df["status"].value_counts().to_dict()
            pcols = st.columns(len(db.STATUS_OPTIONS))
            for i, sname in enumerate(db.STATUS_OPTIONS):
                pcols[i].metric(sname, counts.get(sname, 0))

            # ── Filters ──
            people = sorted([p for p in db_df["scraped_by"].unique() if p and p != "—"])
            f1, f2, f3 = st.columns([1, 1, 2])
            with f1:
                status_filter = st.selectbox("Filter by status", ["All"] + db.STATUS_OPTIONS)
            with f2:
                who_filter = st.selectbox("Scraped by", ["Everyone"] + people)
            with f3:
                q = st.text_input("🔎 Search (username, caption, hashtag)", "")

            view_df = db_df
            if status_filter != "All":
                view_df = view_df[view_df["status"] == status_filter]
            if who_filter != "Everyone":
                view_df = view_df[view_df["scraped_by"] == who_filter]
            if q and not view_df.empty:
                ql = q.lower()
                mask = view_df.apply(
                    lambda row: ql in str(row.get("username", "")).lower()
                    or ql in str(row.get("caption", "")).lower()
                    or ql in str(row.get("hashtags", "")).lower(),
                    axis=1,
                )
                view_df = view_df[mask]
            st.caption(f"Showing {len(view_df)} of {len(db_df)} creators · "
                       "edit **Status**/**Notes** below, then click 💾 Save")

            # ── Editable CRM table ──
            edited = st.data_editor(
                view_df, use_container_width=True, hide_index=True,
                column_config={
                    "status": st.column_config.SelectboxColumn(
                        "Status", options=db.STATUS_OPTIONS, required=True, width="medium"),
                    "notes": st.column_config.TextColumn("Notes", width="large"),
                    "profile": st.column_config.LinkColumn(
                        "Profile", display_text=r"instagram\.com/([^/]+)"),
                    "reel_url": st.column_config.LinkColumn("Reel", display_text="open ↗"),
                    "engagement_rate": st.column_config.NumberColumn(
                        "ER %", format="%.1f%%",
                        help="Engagement Rate = Likes ÷ Followers × 100"),
                },
                disabled=[c for c in view_df.columns if c not in ("status", "notes")],
            )

            # ── Save / download ──
            b1, b2, b3 = st.columns([1, 1, 2])
            with b1:
                if st.button("💾 Save changes", type="primary", use_container_width=True):
                    orig = {r["reel_url"]: r for _, r in view_df.iterrows()}
                    changes = []
                    for _, row in edited.iterrows():
                        o = orig.get(row["reel_url"])
                        if o is None:
                            continue
                        if (str(row.get("status", "")) != str(o.get("status", "")) or
                                str(row.get("notes", "")) != str(o.get("notes", ""))):
                            changes.append({"reel_url": row["reel_url"],
                                            "status": row.get("status"),
                                            "notes": row.get("notes", "")})
                    if not changes:
                        st.info("No changes to save.")
                    else:
                        n, err = db.save_status_changes(changes)
                        if err:
                            st.error(f"Saved {n}/{len(changes)}, then error: {err}")
                        else:
                            st.success(f"✅ Saved {n} update(s).")
                            st.session_state.db_rows, st.session_state.db_error = \
                                db.fetch_all_reels(limit=5000)
                            st.rerun()
            with b2:
                st.download_button(
                    "⬇️ Excel", data=to_excel(view_df),
                    file_name="creators_database.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with b3:
                st.download_button(
                    "⬇️ CSV", data=to_csv(view_df),
                    file_name="creators_database.csv", mime="text/csv",
                    use_container_width=True,
                )


# ── Results Section ──────────────────────────────────────────────────────────
st.divider()

if st.session_state.error:
    st.error(f"Error: {st.session_state.error}")

if st.session_state.filtered_reels:
    results = st.session_state.filtered_reels
    total_scanned = len(st.session_state.reels)

    st.markdown(f"### Results: {len(results)} creators matched · {total_scanned} total in pool")

    def _reel_to_row(r):
        return {
            "Username": r.get("username", ""),
            "Profile URL": f"https://www.instagram.com/{r.get('username','')}/" if r.get("username") else "",
            "Full Name": r.get("full_name", ""),
            "Reel URL": r.get("reel_url", ""),
            "Followers": r.get("followers", 0),
            "Likes": r.get("likes", 0),
            "ER %": r.get("engagement_rate", 0.0),
            "Category": r.get("category", ""),
            "Email": r.get("contact_email", ""),
            "Bio": r.get("bio", ""),
            "Language": r.get("detected_language", ""),
            "Hashtags": ", ".join(r.get("hashtags", [])),
            "Caption": (r.get("caption", "") or "")[:400],
        }

    df = pd.DataFrame([_reel_to_row(r) for r in results])

    # Auto-save every result set to disk so the links always live in a file,
    # regardless of the browser UI. Writes a timestamped CSV + a plain links.txt.
    try:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(RESULTS_DIR, f"creators_{stamp}.csv")
        df.to_csv(csv_path, index=False)
        links_path = os.path.join(RESULTS_DIR, "links_latest.txt")
        with open(links_path, "w") as f:
            for r in results:
                f.write(f"{r.get('reel_url','')}\t@{r.get('username','')}\t{r.get('likes',0)} likes\n")
        st.success(f"💾 Saved {len(results)} links to `results/` folder "
                   f"(`{os.path.basename(csv_path)}` + `links_latest.txt`)")
    except Exception as e:
        st.warning(f"Could not auto-save results to disk: {e}")

    # ── TRIAGE: review and keep only the creators you want ──────────────────
    st.markdown("#### 🔍 Review & Keep")
    st.caption("Untick anyone you don't want (open the **reel** to judge their style), "
               "then save the keepers. **Only kept creators go to your database & get contacted.**")

    _dm_tmpl = st.session_state.get("dm_template", "Hey {name}! 👋\n\nWe're Vidrow, a creative marketing agency. We loved your content and would love to collaborate with you.\n\nWould you be open to a quick chat? 🙌")

    triage_df = pd.DataFrame([
        {
            "Keep": not r.get("already_in_db", False),  # already saved → default unticked
            "→ Sheet": False,                            # tick to send this creator to Google Sheet
            "In DB": (f"✅ {r.get('db_finder')}" if r.get("db_finder") else "✅ Saved")
                     if r.get("already_in_db") else "🆕 New",
            "Profile": f"https://www.instagram.com/{r.get('username','')}/" if r.get("username") else "",
            "DM": f"https://www.instagram.com/{r.get('username','')}/" if r.get("username") else "",
            "Reel": r.get("reel_url", ""),
            "Followers": r.get("followers", 0),
            "Likes": r.get("likes", 0),
            "ER %": r.get("engagement_rate", 0.0),
            "Category": r.get("category", ""),
            "Caption": (r.get("caption", "") or "")[:120],
            "_new": not r.get("already_in_db", False),   # robust flag for sort/count
            "_url": r.get("reel_url", ""),
            "_username": r.get("username", ""),
            "_email": r.get("contact_email", ""),
            "_language": r.get("detected_language", ""),
            "_dm_text": _dm_tmpl.replace("{name}", r.get("full_name", "") or r.get("username", "")).replace("{username}", r.get("username", "")),
        }
        for r in results
    ])

    # Sort: New creators first (by ER %), already-saved ones at bottom
    triage_sorted = pd.concat([
        triage_df[triage_df["_new"]].sort_values("ER %", ascending=False),
        triage_df[~triage_df["_new"]].sort_values("ER %", ascending=False),
    ]).reset_index(drop=True)

    new_count = int(triage_df["_new"].sum())
    saved_count = int((~triage_df["_new"]).sum())
    st.caption(f"🆕 **{new_count} new creators** · ✅ {saved_count} already in your DB (unticked by default)")

    edited_triage = st.data_editor(
        triage_sorted,
        use_container_width=True, hide_index=True, key="triage_editor",
        column_config={
            "Keep": st.column_config.CheckboxColumn("Keep", default=True, width="small"),
            "→ Sheet": st.column_config.CheckboxColumn("→ Sheet", default=False, width="small",
                                                       help="Tick to send this creator to your Google Sheet"),
            "In DB": st.column_config.TextColumn("In DB", width="small"),
            "Profile": st.column_config.LinkColumn("Profile", display_text=r"instagram\.com/([^/]+)"),
            "DM": st.column_config.LinkColumn("DM", display_text="📩 Message"),
            "Reel": st.column_config.LinkColumn("Reel", display_text="watch ↗"),
            "ER %": st.column_config.NumberColumn("ER %", format="%.2f%%",
                                                   help="Engagement Rate = Likes ÷ Followers × 100. Higher = better."),
            "Followers": st.column_config.NumberColumn("Followers", format="%d"),
            "Likes": st.column_config.NumberColumn("Likes", format="%d"),
            "_url": None, "_username": None, "_email": None, "_language": None,
            "_new": None, "_dm_text": None,
        },
        disabled=[c for c in triage_sorted.columns if c not in ("Keep", "→ Sheet")],
    )

    # ── Send ticked creators to the Google Sheet ──────────────────────────────
    sheet_rows = edited_triage[edited_triage["→ Sheet"] == True]  # noqa: E712
    n_sheet = len(sheet_rows)
    if st.button(f"📤 Send {n_sheet} ticked → Google Sheet", use_container_width=True,
                 disabled=n_sheet == 0, key="push_sheet"):
        creators_payload = [
            {"name": row["_username"], "username": row["_username"],
             "email": row["_email"], "language": row["_language"]}
            for _, row in sheet_rows.iterrows()
        ]
        ok, msg = push_to_gsheet(creators_payload)
        if ok:
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ {msg}")

    kept_urls = set(edited_triage[edited_triage["Keep"] == True]["_url"].tolist())  # noqa: E712
    kept = [r for r in results if r.get("reel_url") in kept_urls]

    # DM template preview — select creator to see filled message
    with st.expander("📩 DM Template Preview — select a creator to copy their message"):
        creator_names = [r.get("username", "") for r in results if r.get("username")]
        if creator_names:
            selected = st.selectbox("Creator", creator_names, key="dm_preview_select")
            selected_reel = next((r for r in results if r.get("username") == selected), None)
            if selected_reel:
                filled = _dm_tmpl.replace(
                    "{name}", selected_reel.get("full_name", "") or selected_reel.get("username", "")
                ).replace("{username}", selected_reel.get("username", ""))
                st.text_area("Filled message (copy this)", value=filled, height=150, key="dm_filled_preview")

    kept_urls_for_export = {r.get("reel_url") for r in kept}
    kept_df = df[df["Reel URL"].isin(kept_urls_for_export)].reset_index(drop=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    tcol1, tcol2, tcol3, tcol4 = st.columns([2, 1, 1, 1])
    with tcol1:
        if st.button(f"💾 Save {len(kept)} kept → Database", type="primary",
                     use_container_width=True, key="save_kept"):
            if not kept:
                st.warning("No creators ticked. Tick at least one to keep.")
            elif not db.is_configured():
                st.warning("Supabase isn't connected — can't save to the cloud DB "
                           "(your local CSV in `results/` still has everything).")
            else:
                meta = st.session_state.get("scrape_meta", {})
                bid = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_n, known_n, err = db.upsert_reels(
                    kept, scraped_by=meta.get("scraped_by", ""),
                    batch_id=bid, scraped_from=meta.get("scraped_from", ""))
                if err:
                    st.error(f"Save error: {err}")
                else:
                    st.session_state.pop("db_rows", None)  # force Database tab refresh
                    st.success(f"✅ Saved {len(kept)} creators "
                               f"({new_n} new, {known_n} already in the team bank). "
                               "Open the 🗄️ Database tab to see them.")
    with tcol2:
        st.download_button(
            f"⬇️ Kept Excel ({len(kept)})",
            data=to_excel(kept_df),
            file_name=f"kept_creators_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            disabled=len(kept) == 0,
            help="Download only the creators you ticked above",
        )
    with tcol3:
        st.download_button(
            f"⬇️ Kept CSV ({len(kept)})",
            data=to_csv(kept_df),
            file_name=f"kept_creators_{stamp}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=len(kept) == 0,
            help="Download only the creators you ticked above",
        )
    with tcol4:
        st.download_button(
            f"⬇️ All ({len(results)})",
            data=to_csv(df),
            file_name=f"all_creators_{stamp}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Download all filtered results regardless of ticks",
        )

    st.caption(f"**{len(kept)} of {len(results)}** ticked · Excel/CSV include: username, profile, reel, followers, ER%, email, bio, hashtags, caption")

    st.divider()

    # View toggle
    view_mode = st.radio("View as", ["Cards", "Table"], horizontal=True)

    if view_mode == "Cards":
        for i, reel in enumerate(results):
            render_reel_card(reel, i)
    else:
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={
                "Profile URL": st.column_config.LinkColumn(
                    "Profile", display_text=r"instagram\.com/([^/]+)"),
                "Reel URL": st.column_config.LinkColumn("Reel", display_text="open ↗"),
            },
        )

elif not st.session_state.scraping and st.session_state.reels:
    st.info("No reels matched your filters. Try relaxing the filter conditions.")
elif not st.session_state.scraping and not st.session_state.reels:
    st.info("Set your filters above and hit **Start Scraping** to find creators.")
