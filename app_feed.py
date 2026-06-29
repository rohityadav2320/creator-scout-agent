"""
Trained Feed portal — SEPARATE from the discovery portal (app.py).

This app uses the Instagram MOBILE API (instagrapi) only. It shares NO login or
session code with the browser-based discovery portal, so changes here can never
break Hashtag / Reference Creator.

Run:  python3 -m streamlit run app_feed.py --server.port 8503
"""
import os
import io
import streamlit as st
import pandas as pd

from feed_scraper import scrape_trained_feed
from filters import apply_filters, LANG_CODES, extract_keywords
from hashtag_library import HASHTAG_LIBRARY, get_all_hashtags
import db

st.set_page_config(page_title="Trained Feed — Vidrow", page_icon="📱", layout="wide")

for key, default in {
    "tf_reels": [], "tf_filtered": [], "tf_error": "", "tf_meta": {},
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def fmt_number(n):
    n = n or 0
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


# ── Sidebar — Login (instagrapi only) ────────────────────────────────────────
with st.sidebar:
    st.title("📱 Trained Feed")
    st.caption("by Vidrow — Creator Scout")
    st.divider()

    scraped_by = st.text_input("Your name (team member)", placeholder="e.g. Rohit")

    st.divider()
    st.subheader("Instagram Login")
    st.caption("Logs in via Instagram's mobile API. Separate from the Discovery portal.")
    ig_user = st.text_input("Instagram Username", placeholder="your_burner_username")

    st.markdown("**🍪 Session ID** *(recommended — no challenge)*")
    ig_session = st.text_input(
        "sessionid", type="password", placeholder="Paste your sessionid here",
        key="tf_sessionid", label_visibility="collapsed",
        help="Adopts your logged-in session — skips the password login Instagram challenges.",
    )
    with st.expander("Or log in with password"):
        ig_pass = st.text_input("Instagram Password", type="password", key="tf_pass")
        ig_code = st.text_input(
            "Verification code (only if Instagram asks)",
            placeholder="6-digit code from email/SMS", key="tf_code",
        )

    st.divider()
    max_reels = st.slider("Max reels to scan", 10, 500, 50, step=10)


# ── Main ─────────────────────────────────────────────────────────────────────
st.title("📱 Trained Feed Search")
st.caption(
    "Train your burner account on your phone by watching niche reels, then scrape "
    "its algorithmic feed here — Instagram's algorithm surfaces the right creators."
)

with st.expander("ℹ️ How to train your account + how this works", expanded=False):
    st.markdown("""
**Step 1 — Train on your phone (one-time)**
- Log into your burner on the Instagram app
- Watch 30–50 Reels in your target niche; like, save, follow a few creators
- Do it over 2–3 sessions — Instagram learns fast

**Step 2 — Log in (sessionid recommended) and scrape**
- Uses Instagram's mobile API — no browser opens
- Pulls reels from your trained feed

**Step 3 — Filter and keep**
- Apply filters, keep the good ones, save to the shared database
""")

f1, f2, f3 = st.columns(3)
with f1:
    min_followers = st.number_input("Min Followers", min_value=0, value=10000, step=1000)
    max_followers = st.number_input("Max Followers (0 = no limit)", min_value=0, value=0, step=10000)
with f2:
    min_likes = st.number_input("Min Likes", min_value=0, value=0, step=500)
    min_views = st.number_input("Min Views (0 = no limit)", min_value=0, value=0, step=1000)
with f3:
    language = st.selectbox("Language", ["any"] + list(LANG_CODES.keys()))
    creators_only = st.checkbox("🙅 Exclude clip / movie / meme channels", value=True)

st.markdown("**Must contain hashtag** *(optional)*")
hc1, hc2 = st.columns([1, 2])
with hc1:
    category = st.selectbox("📂 Browse by niche",
                            ["— browse by category —"] + list(HASHTAG_LIBRARY.keys()))
with hc2:
    cat_tags = HASHTAG_LIBRARY.get(category, []) if category != "— browse by category —" else []
    sel_tags = st.multiselect(
        "Hashtags (type to search or pick)", options=get_all_hashtags(),
        default=[t for t in cat_tags if t in get_all_hashtags()],
        placeholder="Search hashtags e.g. 'comedy', 'finance'...",
    )
custom_tags_input = st.text_input("➕ Add custom hashtags (comma separated, without #)",
                                  placeholder="mynewhashtag, anothertag")
custom_tags = [t.strip() for t in custom_tags_input.split(",") if t.strip()]
all_hashtags = list(dict.fromkeys(sel_tags + custom_tags))

description = st.text_area("Content filter (optional — describe the reels you want)",
                          placeholder="e.g. direct to camera speaking | skit / acting", height=68)
if description.strip():
    kws = extract_keywords(description)
    if kws:
        st.caption(f"🔍 Matching reels that mention: **{', '.join(kws)}**")

feed_filters = {
    "min_likes": int(min_likes), "min_views": int(min_views),
    "min_followers": int(min_followers), "max_followers": int(max_followers),
    "language": language, "creators_only": creators_only,
    "creator_styles": [], "hashtags": all_hashtags,
    "content_types": [], "description": description,
}

if st.button("🚀 Scrape My Feed", type="primary", use_container_width=True):
    if not ig_user:
        st.error("Enter your Instagram username in the sidebar.")
    elif not (ig_session or ig_pass):
        st.error("Paste your sessionid (recommended) or password in the sidebar.")
    else:
        st.session_state.tf_reels = []
        st.session_state.tf_filtered = []
        st.session_state.tf_error = ""
        log = []
        area = st.empty()

        def progress(msg):
            log.append(msg)
            area.info("  \n".join(f"• {m}" for m in log[-8:]))

        with st.spinner("Connecting to Instagram mobile API..."):
            reels, error = scrape_trained_feed(
                ig_user, ig_pass, max_reels,
                progress_callback=progress, scraped_by=scraped_by,
                hashtags=all_hashtags or None,
                sessionid=ig_session, verification_code=ig_code,
            )
        if error:
            area.error(f"❌ {error}")
            st.session_state.tf_error = error
        else:
            st.session_state.tf_reels = reels or []
            st.session_state.tf_filtered = apply_filters(st.session_state.tf_reels, feed_filters)
            st.session_state.tf_meta = {"scraped_by": scraped_by, "scraped_from": ig_user}
            area.success(
                f"✅ Collected **{len(reels or [])} reels** → "
                f"**{len(st.session_state.tf_filtered)} match your filters**"
            )

# ── Results ──────────────────────────────────────────────────────────────────
results = st.session_state.tf_filtered
if results:
    st.divider()
    st.markdown(f"#### 🎯 {len(results)} creators — review & keep")
    rows = []
    for r in results:
        uname = r.get("username", "")
        rows.append({
            "Keep": True,
            "Profile": f"https://www.instagram.com/{uname}/",
            "Reel": r.get("reel_url", ""),
            "Username": uname,
            "Followers": r.get("followers", 0),
            "ER %": r.get("engagement_rate", 0.0),
            "Likes": r.get("likes", 0),
            "Email": r.get("contact_email", ""),
            "Hashtags": ", ".join(r.get("hashtags", [])[:5]),
            "Caption": (r.get("caption", "") or "")[:120],
        })
    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df, hide_index=True, use_container_width=True,
        column_config={
            "Keep": st.column_config.CheckboxColumn("Keep"),
            "Profile": st.column_config.LinkColumn("Profile", display_text="open ↗"),
            "Reel": st.column_config.LinkColumn("Reel", display_text="watch ↗"),
        },
        key="tf_editor",
    )
    kept_usernames = set(edited[edited["Keep"]]["Username"].tolist())
    kept = [r for r in results if r.get("username") in kept_usernames]

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button(f"💾 Save {len(kept)} kept → Database", type="primary", use_container_width=True):
            if not db.is_configured():
                st.warning("Supabase not configured — can't save. (Check .streamlit/secrets.toml)")
            else:
                meta = st.session_state.tf_meta
                new, known, err = db.upsert_reels(
                    kept, scraped_by=meta.get("scraped_by", ""),
                    scraped_from=meta.get("scraped_from", ""),
                )
                if err:
                    st.error(f"Save failed: {err}")
                else:
                    st.success(f"✅ Saved — {new} new, {known} already in the database.")
    with c2:
        st.download_button(
            "⬇️ Download Excel", data=to_excel(pd.DataFrame(rows)),
            file_name="trained_feed_creators.xlsx", use_container_width=True,
        )
elif st.session_state.tf_error:
    pass
else:
    st.info("Train your account, log in, and hit **Scrape My Feed** to pull your trained feed.")
