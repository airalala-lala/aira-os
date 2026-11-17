"""The six AIRA OS modules.

'built' stays False until a module really exists, so the app never pretends
that something works when it does not.
"""

from __future__ import annotations

MODULES = [
    {
        "key": "phd",
        "title": "PhD Research Hub",
        "short": "PhD",
        "icon": ":material/school:",
        "path": "views/phd.py",
        "phase": "Phase 2",
        "built": False,
        "summary": "Timeline, literature review manager, synthesis board, "
        "supervisor meetings, POL500 and weekly planner.",
        "planned": [
            "Literature review manager with CSV import and duplicate checks",
            "Supervisor meeting log with action items",
            "Six-semester timeline with planned and actual dates",
            "Synthesis board and evidence tracker for each research gap",
            "POL500 tracker and PhD weekly planner",
        ],
    },
    {
        "key": "fitness",
        "title": "Fitness Studio",
        "short": "Fitness",
        "icon": ":material/fitness_center:",
        "path": "views/fitness.py",
        "phase": "Phase 3",
        "built": False,
        "summary": "Weight tracker, workout logger, strength progression "
        "and a weekly training planner.",
        "planned": [
            "Weight tracker with trend, moving average and goal line",
            "Workout logger with individual sets, original units kept",
            "Strength progression and personal bests by exercise",
            "Weekly planner for strength, rowing, swimming and recovery",
            "Optional nutrition and habit tracking",
        ],
    },
    {
        "key": "business",
        "title": "Business & Boundaries",
        "short": "Business",
        "icon": ":material/balance:",
        "path": "views/business.py",
        "phase": "Phase 4",
        "built": False,
        "summary": "A light business task list and a weekly time boundary, "
        "kept separate from the RR Services system.",
        "planned": [
            "Business task list with delegation and waiting-on status",
            "Daily and weekly time summaries from logged time",
            "Time allocation across PhD, fitness, business and family",
            "End Business Day button",
        ],
    },
    {
        "key": "review",
        "title": "Weekly Life Review",
        "short": "Review",
        "icon": ":material/event_repeat:",
        "path": "views/review.py",
        "phase": "Phase 5",
        "built": False,
        "summary": "A 5 to 10 minute Sunday review built from what you "
        "actually recorded.",
        "planned": [
            "Six reflection questions",
            "Weekly summary generated from recorded data",
            "Saved reflections and week-to-week comparison",
        ],
    },
    {
        "key": "opportunities",
        "title": "Global Opportunities",
        "short": "Global",
        "icon": ":material/public:",
        "path": "views/opportunities.py",
        "phase": "Phase 6",
        "built": False,
        "summary": "Application tracker and a conference and symposium radar, "
        "entered by hand from official sources.",
        "planned": [
            "Application tracker with status, documents and follow-up dates",
            "Conference and symposium radar with official links",
            "Each deadline stored with its source and the date you verified it",
        ],
    },
    {
        "key": "creator",
        "title": "Creator Lab",
        "short": "Creator",
        "icon": ":material/videocam:",
        "path": "views/creator.py",
        "phase": "Phase 7",
        "built": False,
        "summary": "Bio with Teacher Aira: idea bank, scripts, production "
        "status and a content calendar.",
        "planned": [
            "Video idea bank and script drafts",
            "Recording, editing and publishing status",
            "Content calendar",
            "Performance numbers you enter yourself",
        ],
    },
]

MODULE_KEYS = [m["key"] for m in MODULES]
MODULE_TITLES = {m["key"]: m["title"] for m in MODULES}

# Pages shown in the bottom bar on a phone (the rest are in the side menu).
BOTTOM_NAV = [
    {"path": "views/home.py", "label": "Home", "icon": ":material/home:"},
    {"path": "views/phd.py", "label": "PhD", "icon": ":material/school:"},
    {"path": "views/fitness.py", "label": "Fitness", "icon": ":material/fitness_center:"},
    {"path": "views/business.py", "label": "Business", "icon": ":material/balance:"},
    {"path": "views/review.py", "label": "Review", "icon": ":material/event_repeat:"},
]


def get_module(key: str) -> dict:
    for module in MODULES:
        if module["key"] == key:
            return module
    raise KeyError(key)
