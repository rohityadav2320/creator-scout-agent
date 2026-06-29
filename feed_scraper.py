"""
Trained Feed Scraper using instagrapi (Instagram mobile API).
No browser needed — authenticates like the Instagram phone app.
"""
import os
import re
import time
import random
import threading

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _session_path(username: str) -> str:
    safe = re.sub(r"[^\w]", "_", username.lower())
    return os.path.join(SESSIONS_DIR, f"{safe}.json")


def _call_with_timeout(fn, timeout=20):
    """Run fn() in a thread; return (result, None) or (None, error_str) on timeout/exception."""
    result = [None]
    error = [None]

    def _run():
        try:
            result[0] = fn()
        except Exception as e:
            error[0] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None, "timeout"
    if error[0]:
        return None, error[0]
    return result[0], None


def _get_client(username: str, password: str, progress_callback=None, sessionid: str = "",
                verification_code: str = ""):
    from instagrapi import Client
    from instagrapi.exceptions import BadPassword, ChallengeRequired

    cl = Client()
    cl.delay_range = [1, 3]
    # Set a request timeout so network calls don't hang forever
    cl.request_timeout = 15
    session_file = _session_path(username or "session")

    # If Instagram challenges the login, use the code the user typed in the portal.
    verification_code = (verification_code or "").strip()
    cl.challenge_code_handler = lambda u, choice: verification_code or ""

    # ── Preferred: log in by sessionid (adopts the browser session — NO password,
    # NO device challenge, because the session already passed verification). ──
    sessionid = (sessionid or "").strip()
    if sessionid:
        # If the user pasted a full cookie string, pull the sessionid out of it.
        if "sessionid=" in sessionid:
            import re as _re
            m = _re.search(r"sessionid=([^;]+)", sessionid)
            if m:
                sessionid = m.group(1).strip()
        if progress_callback:
            progress_callback("🔑 Logging in with your session (no password needed)...")
        _, err = _call_with_timeout(lambda: cl.login_by_sessionid(sessionid), timeout=30)
        if err == "timeout":
            return None, "Session login timed out — check your internet and try again."
        if err:
            return None, ("Session login failed — your sessionid may be expired. "
                          "Grab a fresh one from instagram.com (logged in) and paste it again.")
        try:
            cl.dump_settings(session_file)
        except Exception:
            pass
        if progress_callback:
            progress_callback("✅ Logged in via session")
        return cl, None

    if not password:
        return None, "Enter your Instagram password OR paste your sessionid in the sidebar."

    if os.path.exists(session_file):
        try:
            cl.load_settings(session_file)
            if progress_callback:
                progress_callback("🔑 Logging in (reusing saved session)...")
            login_result, login_err = _call_with_timeout(
                lambda: cl.login(username, password), timeout=30
            )
            if login_err and login_err != "timeout":
                raise Exception(login_err)
            if login_err != "timeout":
                cl.dump_settings(session_file)
                if progress_callback:
                    progress_callback("✅ Session restored")
                return cl, None
        except (BadPassword, ChallengeRequired) as e:
            os.remove(session_file)
            return None, (
                "Instagram sent a verification challenge. "
                "Open the Instagram app on your phone, complete any verification, then try again."
                if isinstance(e, ChallengeRequired)
                else "Wrong password — please check your credentials."
            )
        except Exception:
            # Session stale — try fresh login below
            try:
                os.remove(session_file)
            except Exception:
                pass

    if progress_callback:
        progress_callback("🔑 Logging in via mobile API (first time — may take 15s)...")

    login_result, login_err = _call_with_timeout(
        lambda: cl.login(username, password), timeout=40
    )
    if login_err == "timeout":
        return None, (
            "Login timed out. Instagram may be sending a challenge.\n"
            "1. Open the Instagram app on your phone\n"
            "2. Complete any verification prompt\n"
            "3. Try scraping again"
        )
    if login_err:
        low = login_err.lower()
        if "badpassword" in low or "bad_password" in low:
            return None, "Wrong password — please check your credentials."
        if "challenge" in low or "checkpoint" in low or "verif" in low or "code" in low:
            if verification_code:
                return None, ("That verification code didn't work — it may be wrong or expired. "
                              "Check for a NEW code and enter it again.")
            return None, ("🔐 Instagram sent a verification code to the account's email/SMS. "
                          "Enter it in the **Verification code** box in the sidebar, then search again.")
        return None, f"Login failed: {login_err}"

    cl.dump_settings(session_file)
    if progress_callback:
        progress_callback("✅ Logged in — session saved for next time")
    return cl, None


def _media_to_reel(media) -> dict:
    try:
        if isinstance(media, dict):
            username = media.get("user", {}).get("username", "")
            full_name = media.get("user", {}).get("full_name", "")
            followers = media.get("user", {}).get("follower_count", 0) or 0
            likes = media.get("like_count", 0) or 0
            comments = media.get("comment_count", 0) or 0
            caption = (media.get("caption") or {})
            caption_text = caption.get("text", "") if isinstance(caption, dict) else str(caption or "")
            code = media.get("code", "")
        else:
            username = getattr(getattr(media, "user", None), "username", "") or ""
            full_name = getattr(getattr(media, "user", None), "full_name", "") or ""
            followers = getattr(getattr(media, "user", None), "follower_count", 0) or 0
            likes = getattr(media, "like_count", 0) or 0
            comments = getattr(media, "comment_count", 0) or 0
            caption_text = getattr(media, "caption_text", "") or ""
            code = getattr(media, "code", "") or ""

        if not username or not code:
            return {}

        reel_url = f"https://www.instagram.com/reel/{code}/"
        hashtags = [w[1:] for w in caption_text.split() if w.startswith("#")]
        er = round((likes / followers * 100), 2) if followers > 0 else 0.0

        return {
            "username": username,
            "full_name": full_name,
            "reel_url": reel_url,
            "likes": likes,
            "comments": comments,
            "followers": followers,
            "engagement_rate": er,
            "caption": caption_text[:500],
            "hashtags": hashtags,
            "bio": "",
            "contact_email": "",
            "category": "",
            "detected_language": "",
        }
    except Exception:
        return {}


def scrape_trained_feed(username: str, password: str, max_reels: int = 50,
                        progress_callback=None, scraped_by: str = "",
                        hashtags: list = None, sessionid: str = "",
                        verification_code: str = "") -> tuple:
    cl, err = _get_client(username, password, progress_callback,
                          sessionid=sessionid, verification_code=verification_code)
    if err:
        return None, err

    reels = []
    seen_urls = set()
    source_counts = {}

    def add(media, source="?"):
        r = _media_to_reel(media)
        if r and r.get("reel_url") and r["reel_url"] not in seen_urls:
            seen_urls.add(r["reel_url"])
            reels.append(r)
            source_counts[source] = source_counts.get(source, 0) + 1

    # ── Source 1: Hashtag reels via API (works on ANY account, trained or not) ─
    if hashtags:
        for tag in hashtags:
            if len(reels) >= max_reels:
                break
            if progress_callback:
                progress_callback(f"🏷️ Fetching reels for #{tag}...")
            try:
                need = max_reels - len(reels)
                medias, t_err = _call_with_timeout(
                    lambda t=tag: cl.hashtag_medias_reels_v1(t, amount=need), timeout=25
                )
                for media in (medias or []):
                    add(media, source=f"#{tag}")
                    if len(reels) >= max_reels:
                        break
                if t_err and progress_callback:
                    progress_callback(f"⚠️ #{tag}: {t_err}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"⚠️ #{tag}: {e}")

    # ── Source 2: Reels tray feed (trained feed — empty if untrained) ──────────
    if len(reels) < max_reels:
        if progress_callback:
            progress_callback("📱 Fetching your trained reels feed...")
        try:
            tray, t_err = _call_with_timeout(lambda: cl.get_reels_tray_feed(), timeout=20)
            if tray:
                trays = tray.get("tray", []) if isinstance(tray, dict) else []
                raw_count = sum(len(t.get("items", [])) for t in trays if isinstance(t, dict))
                if progress_callback:
                    progress_callback(f"📱 Tray raw items: {raw_count}")
                for tray_item in trays:
                    items = tray_item.get("items", []) if isinstance(tray_item, dict) else []
                    for item in items:
                        add(item, source="trained_tray")
                        if len(reels) >= max_reels:
                            break
                    if len(reels) >= max_reels:
                        break
            if t_err and progress_callback:
                progress_callback(f"⚠️ Reels tray: {t_err}")
        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ Reels tray: {e}")

    # ── Source 3: Timeline feed — filter for reels/clips ─────────────────────
    if len(reels) < max_reels:
        if progress_callback:
            progress_callback("📰 Fetching timeline feed...")
        try:
            timeline, t_err = _call_with_timeout(lambda: cl.get_timeline_feed(), timeout=20)
            if timeline:
                items = timeline.get("feed_items", []) if isinstance(timeline, dict) else []
                if progress_callback:
                    progress_callback(f"📰 Timeline raw items: {len(items)}")
                for item in items:
                    if len(reels) >= max_reels:
                        break
                    media = item.get("media_or_ad") if isinstance(item, dict) else item
                    if not media:
                        continue
                    if isinstance(media, dict):
                        if media.get("media_type") == 2 and media.get("product_type") == "clips":
                            add(media, source="timeline")
                    else:
                        if getattr(media, "media_type", None) == 2:
                            add(media, source="timeline")
            if t_err and progress_callback:
                progress_callback(f"⚠️ Timeline: {t_err}")
        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ Timeline: {e}")

    # ── Source 4: Reels timeline (best source for trained accounts) ──────────
    if len(reels) < max_reels:
        if progress_callback:
            progress_callback("🎬 Fetching reels timeline (trained)...")
        try:
            need = max_reels - len(reels)
            reel_list, t_err = _call_with_timeout(
                lambda: cl.reels_timeline_media(amount=need), timeout=25
            )
            raw = len(reel_list) if reel_list else 0
            if progress_callback:
                progress_callback(f"🎬 Reels timeline raw: {raw} items")
            for media in (reel_list or []):
                add(media, source="reels_timeline")
                if len(reels) >= max_reels:
                    break
            if t_err and progress_callback:
                progress_callback(f"⚠️ Reels timeline: {t_err}")
        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ Reels timeline: {e}")

    # ── Source 5: Explore reels (works even on untrained accounts) ────────────
    if len(reels) < max_reels:
        if progress_callback:
            progress_callback("🔍 Fetching explore reels...")
        try:
            need = max_reels - len(reels)
            explore, t_err = _call_with_timeout(
                lambda: cl.explore_reels(amount=need), timeout=25
            )
            raw = len(explore) if explore else 0
            if progress_callback:
                progress_callback(f"🔍 Explore raw: {raw} items")
            if explore and raw > 0:
                first = explore[0]
                ftype = type(first).__name__
                fkeys = list(first.keys())[:6] if isinstance(first, dict) else [a for a in dir(first) if not a.startswith("_")][:6]
                if progress_callback:
                    progress_callback(f"🔍 First item: {ftype} → {fkeys}")
            for media in (explore or []):
                add(media, source="explore")
                if len(reels) >= max_reels:
                    break
            if t_err and progress_callback:
                progress_callback(f"⚠️ Explore: {t_err}")
        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ Explore: {e}")

    if not reels:
        tag_hint = ""
        if not hashtags:
            tag_hint = "\n4. Enter hashtags in the field above (e.g. tamilcomedy, tamilskit)"
        return None, (
            "Got 0 reels from all sources.\n\n"
            "**Most likely causes:**\n"
            "1. Account is new/untrained — no feed content yet\n"
            "2. Instagram is blocking API requests (check app on phone for alerts)\n"
            "3. Username or password is wrong" + tag_hint + "\n\n"
            f"Sources tried: {list(source_counts.keys()) or 'all returned 0'}"
        )

    if progress_callback:
        progress_callback(f"📊 Got {len(reels)} reels — enriching creator profiles...")

    # ── Enrich: fetch followers + bio + email for creators missing data ────────
    for i, r in enumerate(reels):
        if r.get("followers", 0) == 0 and r.get("username"):
            try:
                info, _ = _call_with_timeout(
                    lambda u=r["username"]: cl.user_info_by_username(u), timeout=15
                )
                if info:
                    r["followers"] = getattr(info, "follower_count", 0) or 0
                    r["bio"] = getattr(info, "biography", "") or ""
                    r["full_name"] = getattr(info, "full_name", "") or r["full_name"]
                    email_match = re.search(
                        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", r["bio"]
                    )
                    r["contact_email"] = email_match.group(0) if email_match else ""
                    if r["followers"] > 0:
                        r["engagement_rate"] = round(r["likes"] / r["followers"] * 100, 2)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception:
                pass
        if progress_callback and (i + 1) % 5 == 0:
            progress_callback(f"📊 Enriched {i+1}/{len(reels)} creators...")

    if progress_callback:
        progress_callback(f"✅ Done — {len(reels)} reels collected")

    return reels, None


# ─────────────────────────────────────────────────────────────────────────────
# HASHTAG SEARCH via instagrapi (mobile API) — reliable replacement for the
# Playwright browser scraper. No browser, no cookies, no device-trust issues.
# ─────────────────────────────────────────────────────────────────────────────

def _media_to_creator(media, source_tag: str = "") -> dict:
    """Convert an instagrapi Media object into a creator record (keeps photos AND
    reels — we want the creator; the user filters later)."""
    try:
        user = getattr(media, "user", None)
        username = getattr(user, "username", "") or ""
        if not username:
            return {}
        code = getattr(media, "code", "") or ""
        media_type = getattr(media, "media_type", 0) or 0
        path = "reel" if media_type == 2 else "p"
        likes = getattr(media, "like_count", 0) or 0
        comments = getattr(media, "comment_count", 0) or 0
        views = getattr(media, "view_count", 0) or getattr(media, "play_count", 0) or 0
        caption = getattr(media, "caption_text", "") or ""
        hashtags = [w[1:] for w in caption.split() if w.startswith("#")]
        return {
            "username": username,
            "full_name": getattr(user, "full_name", "") or "",
            "reel_url": f"https://www.instagram.com/{path}/{code}/" if code else "",
            "likes": likes,
            "comments": comments,
            "views": views,
            "followers": 0,
            "engagement_rate": 0.0,
            "caption": caption[:500],
            "hashtags": hashtags,
            "bio": "",
            "contact_email": "",
            "category": "",
            "detected_language": "",
            "source_hashtag": source_tag,
            "media_type": media_type,
        }
    except Exception:
        return {}


def scrape_hashtags_api(username: str, password: str, hashtags: list,
                        max_results: int = 30, progress_callback=None,
                        scraped_by: str = "", seen_usernames=None,
                        enrich: bool = True, sessionid: str = "",
                        verification_code: str = "") -> tuple:
    """Fetch creators for the given hashtags via Instagram's mobile API.
    Returns (creators, error). One record per unique creator."""
    cl, err = _get_client(username, password, progress_callback,
                          sessionid=sessionid, verification_code=verification_code)
    if err:
        return None, err

    seen = set(seen_usernames or [])
    creators, seen_local = [], set()
    tags = [t.strip().lstrip("#") for t in (hashtags or []) if t.strip()]
    if not tags:
        return None, "No hashtags provided."
    per_tag = max(8, (max_results * 2) // max(1, len(tags)))

    rate_limited = False
    for ti, tag in enumerate(tags):
        if len(creators) >= max_results:
            break
        if progress_callback:
            progress_callback(f"🔎 #{tag} — fetching top posts...")
        medias = []
        # GENTLE: use 'top' (best creators) only; add 'recent' just if we still
        # need more. Fewer calls = far less chance of a rate-limit block.
        methods = [("top", "hashtag_medias_top_v1")]
        for label, method in methods:
            try:
                fn = getattr(cl, method)
                res, terr = _call_with_timeout(
                    lambda f=fn, t=tag: f(t, amount=per_tag), timeout=40)
                if res:
                    medias.extend(res)
                if terr and "feedback_required" in str(terr).lower():
                    rate_limited = True
                if terr and progress_callback:
                    progress_callback(f"⚠️ #{tag} {label}: {terr}")
            except Exception as e:
                if "feedback_required" in str(e).lower():
                    rate_limited = True
                if progress_callback:
                    progress_callback(f"⚠️ #{tag} {label}: {e}")

        # One creator per unique username (skip already-seen across sessions).
        for m in medias:
            rec = _media_to_creator(m, tag)
            u = rec.get("username")
            if not u or u in seen_local or u in seen:
                continue
            seen_local.add(u)
            creators.append(rec)
            if len(creators) >= max_results:
                break
        if progress_callback:
            progress_callback(f"#{tag}: {len(creators)} creators so far")
        if rate_limited:
            break
        # Pause between hashtags so we look human and don't trip the rate limit.
        if ti < len(tags) - 1:
            time.sleep(random.uniform(2.5, 4.5))

    if rate_limited and not creators:
        return None, ("This account is rate-limited right now (Instagram's 'feedback_required'). "
                      "It's a temporary block from too many actions — use a different account or "
                      "wait a few hours. Nothing in the code can bypass an Instagram rate-limit.")

    if not creators:
        return None, (
            "Got 0 creators. Likely the account is rate-limited or needs verification "
            "(open the Instagram app on your phone), or the hashtags are very small. "
            "Try popular hashtags and wait a few minutes if you searched a lot."
        )

    # Enrich: followers + bio + email + category (one profile lookup each).
    if enrich:
        if progress_callback:
            progress_callback(f"📊 Enriching {len(creators)} creators (followers/email)...")
        for i, r in enumerate(creators):
            try:
                info, _ = _call_with_timeout(
                    lambda u=r["username"]: cl.user_info_by_username(u), timeout=15)
                if info:
                    r["followers"] = getattr(info, "follower_count", 0) or 0
                    r["bio"] = getattr(info, "biography", "") or ""
                    r["full_name"] = getattr(info, "full_name", "") or r["full_name"]
                    bio_em = re.search(
                        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", r["bio"])
                    pub = getattr(info, "public_email", "") or ""
                    r["contact_email"] = (bio_em.group(0) if bio_em else "") or pub
                    r["category"] = getattr(info, "category", "") or ""
                    if r["followers"] > 0:
                        r["engagement_rate"] = round(r["likes"] / r["followers"] * 100, 2)
                time.sleep(random.uniform(0.8, 1.8))
            except Exception:
                pass
            if progress_callback and (i + 1) % 5 == 0:
                progress_callback(f"📊 Enriched {i+1}/{len(creators)} creators...")

    if progress_callback:
        progress_callback(f"✅ Done — {len(creators)} creators")
    return creators, None
