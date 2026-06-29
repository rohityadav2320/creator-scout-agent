import re
from langdetect import detect, LangDetectException

# Words to strip when extracting keywords from a natural-language description query.
_QUERY_STOP_WORDS = {
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "they", "their",
    "a", "an", "the", "and", "or", "but", "so", "if", "in", "on", "at", "by",
    "for", "of", "to", "from", "with", "about", "into", "that", "this", "these",
    "those", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "can",
    "need", "want", "find", "get", "give", "show", "shows", "see", "look",
    "reel", "reels", "video", "videos", "content", "post", "posts",
    "which", "where", "when", "who", "how", "what", "why",
    "some", "any", "all", "more", "very", "just", "also", "too", "only",
    "share", "shares", "shared", "type", "kind", "sort", "related", "like",
}


def extract_keywords(query: str) -> list[str]:
    """Extract meaningful keywords from a natural-language description query."""
    words = re.findall(r"[a-z0-9]+", query.lower())
    return [w for w in words if w not in _QUERY_STOP_WORDS and len(w) >= 3]

CONTENT_TYPE_KEYWORDS = {
    "funny": ["funny", "comedy", "meme", "lol", "humor", "joke", "prank", "rofl", "haha"],
    "skit": ["skit", "sketch", "act", "scene", "drama", "roleplay", "character"],
    "direct to camera": ["dtc", "direct", "talking", "speaking", "sharing", "story", "vlog", "day in my life"],
    "podcast": ["podcast", "interview", "discussion", "conversation", "episode", "talk show"],
    "tutorial": ["how to", "tutorial", "learn", "tips", "trick", "guide", "step by step", "diy"],
    "dance": ["dance", "dancing", "choreography", "moves", "reel dance"],
    "fitness": ["fitness", "workout", "gym", "exercise", "health", "yoga", "training"],
    "food": ["food", "recipe", "cooking", "chef", "taste", "eat", "restaurant", "foodie"],
    "travel": ["travel", "trip", "explore", "adventure", "destination", "wanderlust", "vlog"],
    "fashion": ["fashion", "outfit", "style", "ootd", "clothing", "wear", "trend"],
    "beauty": ["beauty", "makeup", "skincare", "glow", "routine", "cosmetics"],
    "motivation": ["motivation", "inspire", "mindset", "hustle", "grind", "success"],
    "product review": ["review", "unboxing", "honest review", "product", "recommend"],
}

LANG_CODES = {
    "hindi": "hi",
    "english": "en",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "bengali": "bn",
    "marathi": "mr",
    "punjabi": "pa",
    "gujarati": "gu",
}

# Hashtags that reliably indicate language — much more accurate than langdetect
# for short Hindi captions that mix scripts/English words.
LANG_HASHTAGS = {
    "hi": {
        "hindi", "hindireels", "hindicomedy", "hindivideo", "hindicontent",
        "hindiyt", "hindimotivation", "hindishayari", "hindipodcast",
        "indiancreator", "indiacreator", "indiareels", "desi", "desicreator",
        "hindustani", "hindirap", "hindipoetry",
    },
    "en": {
        "english", "englishcontent", "englishspeaking", "englishvideo",
        "englishcomedy", "englishpodcast",
    },
    "ta": {
        "tamil", "tamilreels", "tamilcomedy", "tamilvideo", "tamilcontent",
        "tamilcreator", "tamilyt",
    },
    "te": {
        "telugu", "telugureels", "telugucomedy", "teluguvideo",
        "telugucontent", "teluguyt",
    },
    "kn": {
        "kannada", "kannadareels", "kannadacomedy", "kannadavideo",
        "kannadacontent",
    },
    "ml": {
        "malayalam", "malayalamreels", "malayalamcomedy", "malayalamvideo",
        "mollywood",
    },
    "bn": {
        "bengali", "bengalireels", "bengalivideo", "bangla", "banglareels",
    },
    "mr": {
        "marathi", "marathireels", "marathicomedy", "marathivideo",
        "marathicontent",
    },
    "pa": {
        "punjabi", "punjabireels", "punjabisong", "punjabicontent",
        "punjabicreator",
    },
    "gu": {
        "gujarati", "gujaratireels", "gujarativideo", "gujaraticontent",
    },
}


# Creator style detection + search hashtags.
# Each style has:
#   "detect"  — hashtags that signal a creator uses this style (for filtering results)
#   "search"  — hashtags to ADD to the search when this style is selected
CREATOR_STYLE_TAGS = {
    "🎤 Direct to Camera": {
        "detect": ["dtc", "directtocamera", "talkinghead", "vlog", "vlogger",
                   "storytime", "myopinion", "reaction", "facecam", "realtalk",
                   "chatting", "monologue", "talkingvideo"],
        "search": ["dtc", "directtocamera", "vlogger", "storytime", "talkinghead",
                   "facecam", "realtalk", "vlog", "myopinion"],
    },
    "🎭 Skit / Acting": {
        "detect": ["skit", "skitreels", "skitcomedy", "acting", "actingreels",
                   "sketch", "comedyskit", "roleplay", "shortfilm", "characteract"],
        "search": ["skitreels", "skitcomedy", "actingreels", "comedyskit",
                   "skit", "shortfilm", "sketch", "acting"],
    },
    "😂 Stand-up / Comedy": {
        "detect": ["standupcomedy", "standup", "comedyvideo", "comedyclip",
                   "hindistandup", "openmic", "comedian", "comedyreels"],
        "search": ["standupcomedy", "comedyreels", "hindistandup", "openmic",
                   "comedian", "comedyvideo", "standup"],
    },
    "💃 Dance / Choreography": {
        "detect": ["dancereels", "choreography", "dancecover", "dancevideo",
                   "bollywooddance", "dancechallenge", "choreographyreels"],
        "search": ["dancereels", "choreographyreels", "dancecover", "bollywooddance",
                   "dancechallenge", "dancevideo", "indiandance"],
    },
    "🎵 Music / Singing / Cover": {
        "detect": ["coversong", "singingreels", "musiccover", "acousticcover",
                   "unplugged", "originalmusic", "musicvideo", "hindicovers"],
        "search": ["singingreels", "coversong", "acousticcover", "musiccover",
                   "unplugged", "originalmusic", "hindicovers"],
    },
    "💪 Fitness / Workout": {
        "detect": ["workoutreels", "gymreels", "fitnessreels", "homeworkout",
                   "fitnessvlog", "gymlife", "workoutvideo", "fitnessmotivation"],
        "search": ["workoutreels", "gymreels", "fitnessreels", "homeworkout",
                   "fitnessvlog", "gymlife", "fitnessmotivation"],
    },
    "🍛 Food / Cooking / Recipe": {
        "detect": ["cookingvideo", "recipevideo", "foodreels", "cookingreels",
                   "foodvlog", "quickrecipes", "kitchenreels", "chefathome"],
        "search": ["cookingvideo", "recipevideo", "foodreels", "cookingreels",
                   "quickrecipes", "kitchenreels", "foodvlog"],
    },
    "✈️ Travel / Vlog": {
        "detect": ["travelvlog", "travelreels", "travelblogger", "travelwithme",
                   "traveldiary", "roadtrip", "backpacking", "explorationindia"],
        "search": ["travelvlog", "travelreels", "travelblogger", "travelwithme",
                   "traveldiary", "roadtrip", "travelindia"],
    },
    "👗 Fashion / OOTD": {
        "detect": ["ootd", "ootdindia", "fashionreels", "outfitoftheday",
                   "styleoftheday", "fashionblogger", "streetstyle", "lookoftheday"],
        "search": ["ootdindia", "fashionreels", "outfitoftheday", "streetstyleindia",
                   "fashionbloggerindia", "styleoftheday", "indianfashion"],
    },
    "💄 Beauty / Makeup / Skincare": {
        "detect": ["makeuptutorial", "skincareroutine", "makeuplooks", "beautyhacks",
                   "makeupvideo", "skincarevideo", "glowup", "hairtutorial"],
        "search": ["makeuptutorial", "skincareroutine", "makeuplooks", "beautyhacks",
                   "makeupindia", "skincareindia", "glowup"],
    },
    "🎙️ Podcast / Interview": {
        "detect": ["podcast", "podcastreels", "interview", "talkshow",
                   "podcastclip", "conversation", "indianpodcast", "podcastinhindi"],
        "search": ["podcastreels", "indianpodcast", "podcastclip", "interview",
                   "talkshow", "podcastinhindi", "conversation"],
    },
    "📚 Tutorial / Educational": {
        "detect": ["tutorial", "howto", "educationalreels", "learnwithme",
                   "tipsandtricks", "hacksinhindi", "factsinhindi", "explained"],
        "search": ["educationalreels", "tutorial", "howto", "learnwithme",
                   "tipsandtricks", "factsinhindi", "knowledgereels"],
    },
    "🔥 Motivation / Mindset": {
        "detect": ["motivationreels", "motivationinhindi", "selfimprovement",
                   "growthmindset", "mindsetshift", "personaldevelopment", "dailymotivation"],
        "search": ["motivationreels", "motivationinhindi", "selfimprovement",
                   "growthmindset", "mindsetshift", "dailymotivation"],
    },
    "🎮 Gaming": {
        "detect": ["gamingreels", "gaminginhindi", "gamingcreator", "gameplay",
                   "mobilegaming", "bgmiindia", "freefireindia", "gamingcommunity"],
        "search": ["gamingreels", "gaminginhindi", "gamingcreator", "mobilegaming",
                   "bgmiindia", "freefireindia", "gameplay"],
    },
    "📱 Tech / Gadget Review": {
        "detect": ["techreels", "gadgetreview", "techtips", "unboxing",
                   "technologyinhindi", "techvlogger", "reviewinhindi", "smartphones"],
        "search": ["techreels", "gadgetreview", "techtips", "unboxingindia",
                   "technologyinhindi", "techvlogger", "reviewinhindi"],
    },
    "🔥 Roast / Reaction / Commentary": {
        "detect": ["roastreels", "reactionvideo", "roastinhindi", "reactvideo",
                   "hindicommentary", "roastvideos", "desiroast", "trollvideo"],
        "search": ["roastreels", "reactionvideo", "roastinhindi", "desiroast",
                   "hindicommentary", "reactvideo"],
    },
    "💼 Business / Entrepreneur": {
        "detect": ["entrepreneurreels", "startupindia", "businesstips",
                   "businessinhindi", "sidehustle", "founderlife", "startuplife"],
        "search": ["entrepreneurreels", "startupindia", "businesstips",
                   "businessinhindi", "sidehustle", "founderlife"],
    },
    "👻 Storytelling / Horror / Mystery": {
        "detect": ["storytellingreels", "hindihorror", "horrorstories",
                   "mysterystories", "hindistorytelling", "thrillerreels", "truestories"],
        "search": ["storytellingreels", "hindihorror", "horrorstories",
                   "mysterystories", "hindistorytelling", "thrillerreels"],
    },
    "📊 Animation / Infographic": {
        "detect": ["animation", "animated", "infographic", "motiondesign",
                   "explainervideo", "2danimation", "motiongraphics", "whiteboard"],
        "search": ["animationreels", "infographic", "motiondesign", "explainervideo",
                   "2danimation", "motiongraphics"],
    },
    "🌅 Lifestyle / Day in My Life": {
        "detect": ["dayinmylife", "morningroutine", "lifestylevlog", "dailyvlog",
                   "nightroutine", "weekendvlog", "productivityvlog", "routinevlog"],
        "search": ["dayinmylife", "morningroutine", "lifestylevlog", "dailyvlog",
                   "weekendvlog", "productivityvlog"],
    },
}


def get_style_search_hashtags(styles):
    """Given a list of selected style names, return combined search hashtags."""
    tags = []
    for style in styles:
        data = CREATOR_STYLE_TAGS.get(style, {})
        if isinstance(data, dict):
            tags.extend(data.get("search", []))
        elif isinstance(data, list):
            tags.extend(data)
    return list(dict.fromkeys(tags))  # dedup, preserve order

# Heuristic blocklist: words that signal a NON-creator account (clip/movie/cartoon/
# meme/repost/edit page) rather than an original creator who could shoot a script.
NON_CREATOR_NAME_WORDS = [
    # Movie / clip / cartoon reposter accounts
    "clips", "clip", "movie", "movies", "moviescene", "scene", "scenes", "cinema",
    "film", "films", "filmy", "bollywood", "hollywood", "tollywood", "kollywood",
    "webseries", "web_series", "series", "cartoon", "cartoons", "animation",
    "animated", "anime", "toon", "toons", "doraemon", "shinchan", "motu",
    "chotabheem", "tomandjerry", "pokemon", "meme", "memes", "memer", "troll",
    "trolls", "viral", "viralvideos", "viralvideo", "status", "statuses",
    "whatsappstatus", "edits", "editz", "editx", "_edit", "edit_", "fanpage",
    "fanclub", "_fc", "fc_", "trending", "entertainment", "dialogues",
    "funnyvideos", "funny_videos", "comedyvideos", "videos_", "_videos", "reels_",
    "_reels", "factz", "facts", "knowledge", "gyan",
    # News / info / corporate pages (not individual creators)
    "news", "newsroom", "breaking", "update", "updates", "daily", "weekly",
    "market", "markets", "stockmarket", "stock", "stocks", "trading", "trader",
    "invest", "investing", "investment", "investor", "economy", "economic",
    "finance_news", "financenews", "moneymarket", "sensex", "nifty", "crypto",
    "bitcoin", "nft", "official", "media", "channel", "broadcast", "press",
    "magazine", "blog", "infographic", "infographics", "tips", "hacks",
    "academy", "institute", "school", "university", "college", "coaching",
    "brand", "agency", "studio", "production", "productions", "corp", "inc",
]
# Strong content-type hashtags that mark a clip/cartoon/movie post.
NON_CREATOR_STRONG_TAGS = {
    "cartoon", "animation", "anime", "webseries", "moviescene", "moviescenes",
    "movieclips", "movieclip", "filmclips", "doraemon", "shinchan",
    # News / info content — not shootable scripts
    "stockmarket", "sharemarket", "sensex", "nifty", "trading", "cryptocurrency",
    "breakingnews", "newsupdate", "infographic",
}
NON_CREATOR_TAGS = {
    "movie", "moviescene", "moviescenes", "movieclips", "bollywood", "hollywood",
    "film", "webseries", "cartoon", "animation", "anime", "meme", "memes",
    "trending", "status", "whatsappstatus", "scene", "filmclips", "edit", "edits",
}


def is_likely_creator(reel):
    """Heuristic: True if this looks like an ORIGINAL creator, False if it looks
    like a clip/movie/cartoon/meme/repost channel. Precision-first (errs toward
    excluding the junk the user can't use)."""
    name = (str(reel.get("username", "")) + " " + str(reel.get("full_name", ""))).lower()
    if any(w in name for w in NON_CREATOR_NAME_WORDS):
        return False
    tags = {str(h).lower() for h in (reel.get("hashtags") or [])}
    if tags & NON_CREATOR_STRONG_TAGS:
        return False
    if len(tags & NON_CREATOR_TAGS) >= 2:
        return False
    return True


def detect_language(text, hashtags=None):
    """Detect language — hashtags first (reliable), then langdetect fallback.
    Hindi creators write captions in Hindi but always tag #hindi/#hindireels etc.
    langdetect alone misclassifies short Hindi captions with English words."""
    # Step 1: hashtag-based detection (most reliable for Indian creators)
    if hashtags:
        reel_tags = {str(h).lower().replace("#", "").replace("_", "") for h in hashtags}
        for lang_code, tag_set in LANG_HASHTAGS.items():
            if reel_tags & tag_set:
                return lang_code
    # Step 2: langdetect fallback on caption text
    if not text or len(text.strip()) < 10:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def detect_content_type(caption, description=""):
    combined = (caption + " " + description).lower()
    matched_types = []
    for ctype, keywords in CONTENT_TYPE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            matched_types.append(ctype)
    return matched_types if matched_types else ["unknown"]


def apply_filters(reels, filters):
    result = []
    for reel in reels:
        if not passes_filter(reel, filters):
            continue
        reel["detected_language"] = detect_language(
            reel.get("caption", ""), reel.get("hashtags", [])
        )
        # Calculate engagement rate = likes / followers * 100
        likes = reel.get("likes", 0) or 0
        followers = reel.get("followers", 0) or 0
        reel["engagement_rate"] = round((likes / followers * 100), 2) if followers > 0 else 0.0
        result.append(reel)
    return result


def passes_filter(reel, filters):
    # Exclude clip/movie/cartoon/meme channels when "creators only" is on.
    if filters.get("creators_only") and not is_likely_creator(reel):
        return False

    # NOTE: Instagram's reels-feed payload does NOT include view counts or follower
    # counts, so those arrive as 0 ("unknown"). We must NOT reject a reel for an
    # unknown metric, or every result would be filtered out. We only apply a
    # view/follower bound when the reel actually carries a known (> 0) value.

    views = reel.get("views", 0) or 0
    followers = reel.get("followers", 0) or 0

    # Min views (only when known)
    min_views = filters.get("min_views", 0)
    if min_views and views > 0 and views < min_views:
        return False

    # Max views (only when known)
    max_views = filters.get("max_views", 0)
    if max_views and views > 0 and views > max_views:
        return False

    # Min likes (likes ARE available in the feed payload)
    min_likes = filters.get("min_likes", 0)
    if min_likes and reel.get("likes", 0) < min_likes:
        return False

    # Min followers (only when known)
    min_followers = filters.get("min_followers", 0)
    if min_followers and followers > 0 and followers < min_followers:
        return False

    # Max followers (only when known)
    max_followers = filters.get("max_followers", 0)
    if max_followers and followers > 0 and followers > max_followers:
        return False

    # Creator style filter — checks reel hashtags for style indicators
    selected_styles = filters.get("creator_styles", [])
    if selected_styles:
        reel_tags = {str(h).lower().replace("#", "").replace("_", "")
                     for h in (reel.get("hashtags") or [])}
        matched_style = False
        for style in selected_styles:
            data = CREATOR_STYLE_TAGS.get(style, {})
            detect_tags = data.get("detect", data) if isinstance(data, dict) else data
            style_tags = {t.replace("_", "") for t in detect_tags}
            if reel_tags & style_tags:
                matched_style = True
                break
        if not matched_style:
            return False

    # Hashtag filter
    required_hashtags = filters.get("hashtags", [])
    if required_hashtags:
        reel_tags = [h.lower() for h in reel.get("hashtags", [])]
        if not any(tag.lower() in reel_tags for tag in required_hashtags):
            return False

    # Language filter — hashtag-based first, langdetect fallback
    selected_lang = filters.get("language", "")
    if selected_lang and selected_lang != "any":
        lang_code = LANG_CODES.get(selected_lang.lower(), selected_lang.lower())
        detected = detect_language(reel.get("caption", ""), reel.get("hashtags", []))
        if detected != lang_code:
            return False

    # Natural-language content filter — match keywords against caption + hashtags.
    # Require at least half (min 1) of the extracted keywords to appear somewhere.
    description_query = filters.get("description", "")
    if description_query and description_query.strip():
        keywords = extract_keywords(description_query)
        if keywords:
            caption_text = (reel.get("caption", "") or "").lower()
            hashtag_text = " ".join(str(h) for h in (reel.get("hashtags") or [])).lower()
            searchable = caption_text + " " + hashtag_text
            matched = sum(1 for kw in keywords if kw in searchable)
            required = max(1, len(keywords) // 2)
            if matched < required:
                return False

    return True


def filters_from_reference_reel(reel_data):
    """Auto-populate filters from a reference reel."""
    if not reel_data:
        return {}

    caption = reel_data.get("caption", "")
    hashtags = reel_data.get("hashtags", [])[:5]
    lang = detect_language(caption)
    content_types = detect_content_type(caption)

    lang_name = next((k for k, v in LANG_CODES.items() if v == lang), lang)

    return {
        "hashtags": hashtags,
        "language": lang_name,
        "content_types": content_types if content_types != ["unknown"] else [],
        "description": "",
        "min_views": 0,
        "min_likes": 0,
        "min_followers": 0,
        "max_followers": 0,
    }
