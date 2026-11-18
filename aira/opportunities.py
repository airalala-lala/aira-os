"""Global Opportunities logic: stages, days left and grouping. Pure Python.

Nothing here invents a deadline: an opportunity without a recorded deadline
is shown as "deadline not published", never as urgent.
"""

from __future__ import annotations

from datetime import date

from aira.timeutil import parse_date

KINDS = [
    "conference_or_symposium", "summer_school", "scholarship_or_fellowship", "application",
    "internship_or_attachment", "visiting_researcher", "funding", "collaboration", "unspecified",
]
KIND_LABELS = {
    "conference_or_symposium": "Conference", "summer_school": "Summer school",
    "scholarship_or_fellowship": "Scholarship or fellowship", "application": "Programme application",
    "internship_or_attachment": "Internship or attachment", "visiting_researcher": "Visiting researcher",
    "funding": "Funding", "collaboration": "Collaboration", "unspecified": "Other",
}
STAGES = [
    "interested", "preparing", "submitted", "interview", "accepted", "rejected",
    "withdrawn", "not_pursuing", "closed", "status_unconfirmed",
]
STAGE_LABELS = {
    "interested": "Interested", "preparing": "Preparing", "submitted": "Applied",
    "interview": "Interview", "accepted": "Accepted", "rejected": "Not successful",
    "withdrawn": "Withdrawn", "not_pursuing": "Not pursuing", "closed": "Closed",
    "status_unconfirmed": "Status not confirmed",
}
OPEN_STAGES = {"interested", "preparing", "status_unconfirmed"}
WAITING_STAGES = {"submitted", "interview"}
SOON_DAYS = 14


def days_left(opp: dict, today: date) -> int | None:
    deadline = parse_date(opp.get("deadline"))
    return (deadline - today).days if deadline else None


def countdown(opp: dict, today: date) -> str:
    days = days_left(opp, today)
    if days is None:
        return "Deadline not published"
    if days < 0:
        return f"Closed {-days} day(s) ago"
    if days == 0:
        return "Closes today"
    if days == 1:
        return "Closes tomorrow"
    return f"{days} days left"


def group(opps: list[dict], today: date) -> dict[str, list[dict]]:
    """Split opportunities into the page's four lists."""
    groups = {"closing": [], "applied": [], "watch": [], "past": []}
    for opp in opps:
        stage = opp.get("stage") or "interested"
        days = days_left(opp, today)
        if stage in WAITING_STAGES:
            groups["applied"].append(opp)
        elif stage in OPEN_STAGES and days is not None and days >= 0:
            groups["closing"].append(opp)
        elif stage in OPEN_STAGES and days is None:
            groups["watch"].append(opp)
        else:
            groups["past"].append(opp)
    groups["closing"].sort(key=lambda o: o["deadline"])
    groups["applied"].sort(key=lambda o: o.get("applied_on") or "", reverse=True)
    groups["watch"].sort(key=lambda o: (o.get("event_start") or "9999", o.get("title") or ""))
    groups["past"].sort(key=lambda o: o.get("deadline") or o.get("updated_at") or "", reverse=True)
    return groups


def closing_soon(opps: list[dict], today: date, within: int = SOON_DAYS) -> list[dict]:
    """Open opportunities whose recorded deadline is within the next N days."""
    return [o for o in group(opps, today)["closing"] if days_left(o, today) <= within]
