"""Video Inspiration Library logic.

Three kinds of information are kept apart everywhere:
  1. the saved link (always kept, even when nothing else can be found);
  2. retrieved details (title, creator, thumbnail) from the platform's own
     public oEmbed service or the page's Open Graph tags, with their source;
  3. creative analysis, which only exists when you wrote it, or when Claude
     drafted it from a transcript or description that you provided.

Nothing here watches a video or invents what is in it.
"""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.error
import urllib.parse
import urllib.request

PLATFORMS = ["tiktok", "instagram", "youtube", "facebook", "x", "vimeo", "other"]
PLATFORM_LABELS = {
    "tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube", "facebook": "Facebook",
    "x": "X", "vimeo": "Vimeo", "other": "Other",
}
ANALYSIS_FIELDS = [
    ("hook", "Hook and opening style"),
    ("editing", "Editing and transitions"),
    ("visuals", "Visual aesthetics"),
    ("storytelling", "Storytelling structure"),
    ("text_style", "Text and subtitle style"),
    ("recreate", "Elements I want to recreate"),
    ("biology_use", "How I could use it for Biology teaching"),
]
ANALYSIS_BASIS = ["not_analysed", "watched_by_me", "from_my_materials", "claude_draft_from_materials"]
ANALYSIS_BASIS_LABELS = {
    "not_analysed": "Not analysed yet",
    "watched_by_me": "Analysed by me after watching",
    "from_my_materials": "Analysed by me from screenshots or a transcript",
    "claude_draft_from_materials": "Claude's draft from my transcript or description (Claude did not watch the video)",
}
METADATA_LABELS = {
    "retrieved": "Details retrieved automatically",
    "not_available": "Link only (details could not be retrieved)",
    "edited": "Details edited by me",
}

_HOSTS = [
    ("tiktok", ("tiktok.com",)),
    ("instagram", ("instagram.com", "instagr.am")),
    ("youtube", ("youtube.com", "youtu.be", "youtube-nocookie.com")),
    ("facebook", ("facebook.com", "fb.watch", "fb.com")),
    ("x", ("twitter.com", "x.com")),
    ("vimeo", ("vimeo.com",)),
]
_TRACKING = re.compile(r"^(utm_|fbclid|igsh|igshid|si|is_from_webapp|sender_device|_r|_t|share_|feature)")


def clean_url(raw: str) -> str:
    """Trim spaces and add https:// when it was left out."""
    url = (raw or "").strip()
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url


def is_valid_url(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    return parts.scheme in ("http", "https") and "." in parts.netloc


def detect_platform(url: str) -> str:
    host = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    for platform, domains in _HOSTS:
        if any(host == d or host.endswith("." + d) for d in domains):
            return platform
    return "other"


def youtube_id(url: str) -> str | None:
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower()
    if host.endswith("youtu.be"):
        return parts.path.strip("/").split("/")[0] or None
    match = re.match(r"^/(shorts|embed|live|v)/([^/?#]+)", parts.path)
    if match:
        return match.group(2)
    return urllib.parse.parse_qs(parts.query).get("v", [None])[0]


def url_key(url: str) -> str:
    """A cleaned form of the link, so the same video is not saved twice."""
    platform = detect_platform(url)
    if platform == "youtube" and youtube_id(url):
        return f"youtube:{youtube_id(url)}"
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if not _TRACKING.match(k)]
    path = parts.path.rstrip("/") or "/"
    key = f"{host}{path}"
    if query:
        key += "?" + urllib.parse.urlencode(sorted(query))
    return key.lower() if platform != "other" else key


# ------------------------------------------------------------- metadata

OEMBED = {
    "youtube": ("https://www.youtube.com/oembed?format=json&url={url}", "YouTube oEmbed"),
    "tiktok": ("https://www.tiktok.com/oembed?url={url}", "TikTok oEmbed"),
    "vimeo": ("https://vimeo.com/api/oembed.json?url={url}", "Vimeo oEmbed"),
}
_USER_AGENT = "Mozilla/5.0 (compatible; AIRA-OS personal dashboard)"


def _get(url: str, timeout: float = 6.0, limit: int = 600_000) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https endpoints
        return response.read(limit), response.headers.get("Content-Type", "")


def _meta(page: str, *names: str) -> str | None:
    for name in names:
        for pattern in (
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
        ):
            match = re.search(pattern, page, re.IGNORECASE)
            if match:
                return html_lib.unescape(match.group(1)).strip()
    return None


def parse_open_graph(page: str) -> dict:
    return {
        "title": _meta(page, "og:title", "twitter:title"),
        "creator": _meta(page, "author", "og:video:director", "twitter:creator"),
        "thumbnail_url": _meta(page, "og:image", "twitter:image"),
    }


def fetch_metadata(url: str, fetch=_get) -> dict:
    """Try the platform's public oEmbed service, then the page's Open Graph tags.

    Returns {"status": "retrieved" | "not_available", "source", "title",
    "creator", "thumbnail_url", "message"}. Never raises: a failure just means
    the link is saved on its own.
    """
    platform = detect_platform(url)
    empty = {"status": "not_available", "source": None, "title": None, "creator": None, "thumbnail_url": None}
    if platform in OEMBED:
        endpoint, label = OEMBED[platform]
        try:
            body, _ = fetch(endpoint.format(url=urllib.parse.quote(url, safe="")))
            data = json.loads(body.decode("utf-8", "replace"))
            found = {
                "title": (data.get("title") or "").strip() or None,
                "creator": (data.get("author_name") or "").strip() or None,
                "thumbnail_url": data.get("thumbnail_url") or None,
            }
            if any(found.values()):
                return {**found, "status": "retrieved", "source": label, "message": f"Details from {label}."}
        except Exception:  # network error, 4xx, private video, not JSON
            pass
    if platform in ("instagram", "facebook"):
        return {**empty, "message": f"{PLATFORM_LABELS[platform]} does not share video details without a "
                                    "developer account, so only the link was saved. Add the details yourself."}
    try:
        body, content_type = fetch(url)
        if "html" in content_type.lower():
            found = parse_open_graph(body.decode("utf-8", "replace"))
            if found.get("title") or found.get("thumbnail_url"):
                return {**found, "status": "retrieved", "source": "the page's preview tags",
                        "message": "Details from the page's preview tags."}
    except Exception:
        pass
    return {**empty, "message": "No details could be retrieved, so only the link was saved. Add them yourself."}


def fetch_image(url: str, fetch=_get) -> tuple[bytes, str] | None:
    """Download a thumbnail (images up to 2 MB only). None if it fails."""
    try:
        body, content_type = fetch(url, limit=2_000_001)
    except Exception:
        return None
    if not content_type.lower().startswith("image/") or len(body) > 2_000_000 or not body:
        return None
    return body, content_type.split(";")[0].strip()


# --------------------------------------------------------- organisation


def tags_of(ref: dict) -> list[str]:
    return [t.strip() for t in (ref.get("tags") or "").split(",") if t.strip()]


def has_analysis(ref: dict) -> bool:
    return any((ref.get(field) or "").strip() for field, _ in ANALYSIS_FIELDS)


def matches(ref: dict, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(str(ref.get(f) or "") for f in (
        "title", "creator", "tags", "my_notes", "url", "transcript", "description",
        *[field for field, _ in ANALYSIS_FIELDS],
    )).lower()
    return all(word in haystack for word in query.lower().split())


# ------------------------------------------------------------ the brief

LENGTHS = ["30 seconds", "60 seconds", "90 seconds", "3 to 5 minutes"]
LEVELS = ["Form 4", "Form 5", "Form 4 and 5", "Form 1 to 3 (Science)"]


def build_brief(refs: list[dict], topic: str, level: str, length: str, extra: str = "") -> str:
    """A plain-text brief made only from what is recorded about each reference."""
    lines = [
        "# Brief: new Bio with Teacher Aira video",
        "",
        f"Biology topic: {topic.strip()}",
        f"Audience: Malaysian secondary school students, {level} (KSSM), many preparing for SPM",
        f"Length: {length}",
        "Language: engaging Bahasa Melayu (Manglish is fine), with English scientific terms",
    ]
    if extra.strip():
        lines.append(f"My extra notes: {extra.strip()}")
    lines += ["", "## Saved references (only what I recorded about them)"]
    for number, ref in enumerate(refs, start=1):
        name = ref.get("title") or "Untitled reference"
        lines += ["", f"### Reference {number}: {name}"]
        lines.append(f"- Platform: {PLATFORM_LABELS.get(ref.get('platform'), 'Other')}"
                     + (f"; creator: {ref['creator']}" if ref.get("creator") else ""))
        lines.append(f"- Analysis basis: {ANALYSIS_BASIS_LABELS.get(ref.get('analysis_basis'), 'Not analysed yet')}")
        if ref.get("my_notes"):
            lines.append(f"- Why I saved it: {ref['my_notes']}")
        for field, label in ANALYSIS_FIELDS:
            if (ref.get(field) or "").strip():
                lines.append(f"- {label}: {ref[field].strip()}")
        if not has_analysis(ref) and not ref.get("my_notes"):
            lines.append("- Nothing recorded about this reference beyond its link.")
    return "\n".join(lines)


CONCEPT_INSTRUCTIONS = """You are helping a Malaysian secondary school Biology teacher, Teacher Aira, plan an original short educational video for her channel "Bio with Teacher Aira".

Use the brief below. Borrow only the creative techniques that the brief records about each reference (hook style, editing, visuals, structure, text style). Do not copy any reference's content, wording, characters or jokes, and do not describe anything about the reference videos that the brief does not say.

The Biology must be accurate for the Malaysian KSSM syllabus. Where a fact needs checking against the textbook or DSKP, mark it [CHECK].

Write in this order, with these headings:
1. Concept: a working title, the one-sentence idea, and which recorded techniques it borrows from which reference.
2. Hook: the first 3 seconds, word for word.
3. Script: timed lines (for example 0:00-0:03), in engaging Bahasa Melayu with English scientific terms in bold.
4. Storyboard: a table with columns Time | On screen | Spoken | On-screen text.
5. Production notes: filming setup, B-roll or props, editing and transitions, subtitle style, music mood.
6. Fact-check list: every scientific claim in the script, each with [CHECK] or the textbook chapter it comes from.

Brief:
"""

DRAFT_ANALYSIS_INSTRUCTIONS = """Below is material that a teacher provided about a short video: a transcript and/or her own description. You have NOT seen the video.

Using only this material, draft notes for these fields. Where the material does not say enough for a field, write "Not enough information in the transcript or description" for it. Do not guess visuals, editing or anything else that the material does not describe.

Answer with JSON only, with exactly these keys: hook, editing, visuals, storytelling, text_style, recreate, biology_use.
- hook: how the video opens and grabs attention
- editing: editing and transition techniques
- visuals: visual aesthetics
- storytelling: storytelling structure
- text_style: text and subtitle style
- recreate: elements worth recreating
- biology_use: how a Malaysian secondary school Biology teacher could apply it

Material:
"""


def parse_analysis_json(text: str) -> dict:
    """Pull the seven fields out of Claude's JSON answer. Missing keys come back empty."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise ValueError("The answer did not contain the expected JSON.")
    data = json.loads(match.group(0))
    return {field: str(data.get(field) or "").strip() for field, _ in ANALYSIS_FIELDS}
