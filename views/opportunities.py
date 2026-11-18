"""Global Opportunities (Phase 6): conferences, summer schools, scholarships.

Every deadline shown here was entered by you or imported with the page it came
from. Nothing is searched for automatically, and no deadline is guessed.
"""

import html

import streamlit as st

from aira import db, ui
from aira import opportunities as opp_logic
from aira.opportunities import KIND_LABELS, KINDS, STAGE_LABELS, STAGES
from aira.timeutil import format_date, parse_date, today_kl

TODAY = today_kl()


def _act(action, message: str) -> None:
    try:
        action()
    except db.DataError as exc:
        st.error(str(exc))
        return
    st.session_state["_flash"] = message
    st.rerun()


def _when(o: dict) -> str:
    start, end = parse_date(o.get("event_start")), parse_date(o.get("event_end"))
    if start and end and start != end:
        return f"{format_date(start)} to {format_date(end)}"
    if start:
        return format_date(start)
    return ""


def _card(o: dict, section: str) -> None:
    oid = o["id"]
    stage = o.get("stage") or "interested"
    days = opp_logic.days_left(o, TODAY)
    with st.container(border=True):
        badges = [ui.badge(KIND_LABELS.get(o.get("kind"), "Other"))]
        if section == "closing":
            tone = "rose" if days is not None and days <= 7 else "gold" if days is not None and days <= opp_logic.SOON_DAYS else "teal"
            badges.append(ui.badge(opp_logic.countdown(o, TODAY), tone))
        badges.append(ui.badge(STAGE_LABELS.get(stage, stage), "sage" if stage in ("submitted", "accepted") else ""))
        st.markdown(
            f'<div class="aira-card-title">{html.escape(o["title"])}</div>'
            f'<div style="margin-top:0.35rem">{"".join(badges)}</div>',
            unsafe_allow_html=True,
        )
        facts = []
        where = " · ".join(x for x in [o.get("location"), _when(o)] if x)
        if where:
            facts.append(f"**Where and when:** {where}")
        if o.get("deadline"):
            facts.append(f"**Deadline:** {format_date(parse_date(o['deadline']))}"
                         + (f" ([source]({o['deadline_source_url']}))" if o.get("deadline_source_url") else ""))
        if o.get("fit"):
            facts.append(f"**Fit:** {o['fit']}")
        if o.get("next_step") and stage not in ("submitted", "accepted", "rejected", "withdrawn", "not_pursuing", "closed"):
            facts.append(f"**Next step:** {o['next_step']}")
        if o.get("applied_on"):
            facts.append(f"**Applied on:** {format_date(parse_date(o['applied_on']))}")
        if o.get("notes"):
            facts.append(f"**Notes:** {o['notes']}")
        if o.get("verified_on"):
            facts.append(f"*Details checked on {format_date(parse_date(o['verified_on']))}.*")
        st.markdown("  \n".join(facts))
        if o.get("url"):
            st.link_button("Official page", o["url"], icon=":material/open_in_new:")

        with st.container(horizontal=True, gap="small"):
            if section in ("closing", "watch"):
                if stage != "preparing" and st.button("Preparing", key=f"op_prep_{oid}"):
                    _act(lambda: db.set_opportunity_stage(oid, "preparing"), "Marked as preparing.")
                if st.button("Applied", key=f"op_applied_{oid}", type="primary", icon=":material/check:"):
                    _act(lambda: db.set_opportunity_stage(oid, "submitted"), "Marked as applied. Good luck!")
                if st.button("Not pursuing", key=f"op_skip_{oid}"):
                    _act(lambda: db.set_opportunity_stage(oid, "not_pursuing"), "Moved to past.")
            elif section == "applied":
                if stage != "interview" and st.button("Interview", key=f"op_int_{oid}"):
                    _act(lambda: db.set_opportunity_stage(oid, "interview"), "Interview noted.")
                if st.button("Accepted", key=f"op_acc_{oid}", type="primary"):
                    _act(lambda: db.set_opportunity_stage(oid, "accepted"), "Congratulations!")
                if st.button("Not successful", key=f"op_rej_{oid}"):
                    _act(lambda: db.set_opportunity_stage(oid, "rejected"), "Recorded.")
            else:
                if st.button("Back to open", key=f"op_reopen_{oid}"):
                    _act(lambda: db.set_opportunity_stage(oid, "interested"), "Back in the open list.")

        if st.toggle("Edit or delete", key=f"op_edit_{oid}"):
            _form(f"op_{oid}", o)
            ok = st.checkbox("Yes, delete this opportunity", key=f"op_del_ok_{oid}")
            if st.button("Delete", key=f"op_del_{oid}", disabled=not ok):
                _act(lambda: db.delete_opportunity(oid), "Deleted.")


def _form(prefix: str, o: dict | None = None) -> None:
    o = o or {}
    with st.form(f"{prefix}_form", clear_on_submit=not o):
        title = st.text_input("Name", value=o.get("title") or "", key=f"{prefix}_title")
        c1, c2 = st.columns(2)
        with c1:
            kind = st.selectbox("Type", KINDS, format_func=KIND_LABELS.get,
                                index=KINDS.index(o["kind"]) if o.get("kind") in KINDS else 0, key=f"{prefix}_kind")
            organisation = st.text_input("Organiser", value=o.get("organisation") or "", key=f"{prefix}_org")
            location = st.text_input("Where", value=o.get("location") or "", key=f"{prefix}_loc")
            start = st.date_input("Starts (optional)", value=parse_date(o.get("event_start")), format="DD/MM/YYYY", key=f"{prefix}_start")
            end = st.date_input("Ends (optional)", value=parse_date(o.get("event_end")), format="DD/MM/YYYY", key=f"{prefix}_end")
        with c2:
            stage = st.selectbox("Status", STAGES, format_func=STAGE_LABELS.get,
                                 index=STAGES.index(o["stage"]) if o.get("stage") in STAGES else 0, key=f"{prefix}_stage")
            deadline = st.date_input("Deadline (optional)", value=parse_date(o.get("deadline")), format="DD/MM/YYYY", key=f"{prefix}_deadline")
            source = st.text_input("Where the deadline comes from (link)", value=o.get("deadline_source_url") or "", key=f"{prefix}_source")
            url = st.text_input("Official page (link)", value=o.get("url") or "", key=f"{prefix}_url")
            verified = st.date_input("Details checked on", value=parse_date(o.get("verified_on")) or TODAY,
                                     max_value=TODAY, format="DD/MM/YYYY", key=f"{prefix}_verified")
        fit = st.text_input("Why it fits", value=o.get("fit") or "", key=f"{prefix}_fit")
        next_step = st.text_input("Next step", value=o.get("next_step") or "", key=f"{prefix}_next")
        notes = st.text_area("Notes", value=o.get("notes") or "", height=70, key=f"{prefix}_notes")
        clear = st.checkbox("Remove the dates", key=f"{prefix}_clear") if o else False
        if st.form_submit_button("Save changes" if o else "Add opportunity", type="primary"):
            fields = {"title": title, "kind": kind, "stage": stage, "organisation": organisation,
                      "location": location, "url": url, "deadline": None if clear else deadline,
                      "deadline_source_url": source, "event_start": None if clear else start,
                      "event_end": None if clear else end, "fit": fit, "next_step": next_step,
                      "notes": notes, "verified_on": verified, "outcome": o.get("outcome")}
            if o:
                _act(lambda: db.update_opportunity(o["id"], fields), "Saved.")
            else:
                _act(lambda: db.add_opportunity(fields), "Opportunity added.")


def main() -> None:
    ui.page_header("Global Opportunities", "Conferences, summer schools and scholarships, by closing date.",
                   eyebrow="Phase 6")
    flash = st.session_state.pop("_flash", None)
    if flash:
        st.toast(flash)
    try:
        opps = db.list_opportunities()
    except db.DataError as exc:
        st.error(str(exc))
        st.stop()

    groups = opp_logic.group(opps, TODAY)
    soon = opp_logic.closing_soon(opps, TODAY)
    if soon:
        st.warning(f"{len(soon)} deadline(s) in the next {opp_logic.SOON_DAYS} days: "
                   + "; ".join(f"{o['title']} ({opp_logic.countdown(o, TODAY).lower()})" for o in soon))

    closing, applied, watch, past = st.tabs([
        f"Closing soon ({len(groups['closing'])})", f"Applied ({len(groups['applied'])})",
        f"Watch list ({len(groups['watch'])})", f"Past ({len(groups['past'])})",
    ])
    with closing:
        if not groups["closing"]:
            ui.empty_state("No open deadlines", "Add an opportunity below, or import a list from the Import data page.")
        for o in groups["closing"]:
            _card(o, "closing")
    with applied:
        if not groups["applied"]:
            ui.empty_state("Nothing applied for yet", "Tap Applied on an opportunity when you submit.")
        for o in groups["applied"]:
            _card(o, "applied")
    with watch:
        st.caption("Opportunities without a published deadline. Add the deadline when it appears.")
        if not groups["watch"]:
            ui.empty_state("Nothing on the watch list", "Opportunities without a deadline appear here.")
        for o in groups["watch"]:
            _card(o, "watch")
    with past:
        if not groups["past"]:
            ui.empty_state("Nothing here yet", "Closed, accepted and declined opportunities appear here.")
        for o in groups["past"]:
            _card(o, "past")

    with st.expander("Add an opportunity", icon=":material/add:"):
        _form("new_op")


main()
