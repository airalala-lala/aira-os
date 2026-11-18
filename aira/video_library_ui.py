"""Video Inspiration Library (inside Creator Lab): Paste link -> Save -> Organise -> Reuse.

Three things are always kept apart and labelled on screen:
  * the saved link (always kept);
  * retrieved details (from the platform's public service, with the source);
  * creative analysis (only what you wrote, or Claude's draft from a
    transcript or description you provided; Claude never watches the video).
"""

import html

import streamlit as st

from aira import auth, claude_api, db, ui
from aira import video_refs as vr
from aira.timeutil import format_date, format_timestamp, parse_timestamp

PLATFORM_COLOURS = {"tiktok": "rose", "instagram": "gold", "youtube": "rose", "vimeo": "teal"}


def _act(action, message: str) -> None:
    try:
        action()
    except db.DataError as exc:
        st.error(str(exc))
        return
    st.session_state["_flash"] = message
    st.rerun()


def _image_url(ref: dict) -> str | None:
    """A saved copy of the thumbnail if there is one, else the platform's own link."""
    path = ref.get("thumbnail_path")
    if path:
        cache = st.session_state.setdefault("_vr_signed", {})
        if path not in cache:
            cache[path] = db.signed_url(path)
        if cache[path]:
            return cache[path]
    return ref.get("thumbnail_url")


def _status_badges(ref: dict) -> str:
    badges = [ui.badge(vr.PLATFORM_LABELS.get(ref.get("platform"), "Other"), PLATFORM_COLOURS.get(ref.get("platform"), "teal"))]
    meta = ref.get("metadata_status")
    badges.append(ui.badge({"retrieved": "Details retrieved", "edited": "Details edited by me"}.get(meta, "Link only")))
    basis = ref.get("analysis_basis") or "not_analysed"
    badges.append(ui.badge({
        "not_analysed": "Not analysed", "watched_by_me": "Analysed by me",
        "from_my_materials": "Analysed from my materials", "claude_draft_from_materials": "Claude draft from my transcript",
    }[basis], "sage" if basis != "not_analysed" else ""))
    return "".join(badges)


def _save_thumbnail(ref: dict) -> None:
    """Keep a private copy of the thumbnail, because platform links can expire."""
    if not ref.get("thumbnail_url") or not ref.get("id"):
        return
    image = vr.fetch_image(ref["thumbnail_url"])
    if not image:
        return
    data, content_type = image
    extension = {"image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(content_type, "jpg")
    try:
        path = db.upload_file(auth.current_user_id(), ref["id"], f"thumbnail.{extension}", data, content_type)
        db.update_video_ref(ref["id"], {"thumbnail_path": path})
    except db.DataError:
        pass  # the thumbnail link is still saved


# --------------------------------------------------------------------- save


def _save_tab() -> None:
    st.caption("Paste the share link of a TikTok, Reel, Short or any video. The link is always saved, "
               "even if the details cannot be retrieved.")
    with st.form("vr_save", clear_on_submit=True):
        url = st.text_input("Video link", placeholder="https://www.tiktok.com/@creator/video/…", key="vr_new_url")
        notes = st.text_area("Why I like it (optional)", height=80, key="vr_new_notes")
        tags = st.text_input("Tags (optional, separate with commas)", placeholder="hook, animation, genetics",
                             key="vr_new_tags")
        if st.form_submit_button("Save", type="primary", icon=":material/bookmark_add:"):
            clean = vr.clean_url(url)
            if not vr.is_valid_url(clean):
                st.error("That does not look like a web link. Copy the video's share link and paste it again.")
                return
            with st.spinner("Saving and looking up the video's details…"):
                metadata = vr.fetch_metadata(clean)
                try:
                    ref = db.save_video_ref(clean, notes, tags, metadata)
                except db.DataError as exc:
                    st.error(str(exc))
                    return
                _save_thumbnail(ref)
            st.session_state["_flash"] = "Saved. " + metadata.get("message", "")
            st.rerun()


# ------------------------------------------------------------------ gallery


def _card(ref: dict) -> None:
    with st.container(border=True):
        image = _image_url(ref)
        if image:
            st.image(image)
        title = ref.get("title") or "Untitled video"
        st.markdown(
            f'<div class="aira-card-title">{html.escape(title[:120])}</div>'
            + (f'<div class="aira-card-text">{html.escape(ref["creator"])}</div>' if ref.get("creator") else "")
            + f'<div style="margin:0.3rem 0">{_status_badges(ref)}</div>'
            + "".join(ui.badge(t, "sage") for t in vr.tags_of(ref)),
            unsafe_allow_html=True,
        )
        if ref.get("my_notes"):
            st.caption(ref["my_notes"][:180] + ("…" if len(ref["my_notes"]) > 180 else ""))
        with st.container(horizontal=True, gap="small"):
            st.link_button("Open video", ref["url"], icon=":material/open_in_new:")
            if st.button("Details", key=f"vr_open_{ref['id']}"):
                st.session_state["_vr_open"] = ref["id"]
                st.rerun()


def _field_key(ref_id: str, name: str) -> str:
    return f"vr_{ref_id}_{name}"


def _init_fields(ref: dict, names: list[str]) -> None:
    for name in names:
        key = _field_key(ref["id"], name)
        if key not in st.session_state:
            st.session_state[key] = ref.get(name) or ""


def _detail(ref: dict) -> None:
    rid = ref["id"]
    with st.container(border=True, key=f"vr_detail_{rid}"):
        top_left, top_right = st.columns([1, 2])
        with top_left:
            image = _image_url(ref)
            if image:
                st.image(image)
        with top_right:
            st.markdown(f'<div class="aira-card-title">{html.escape(ref.get("title") or "Untitled video")}</div>'
                        f'<div style="margin:0.3rem 0">{_status_badges(ref)}</div>', unsafe_allow_html=True)
            st.markdown(f"**Saved link:** [{html.escape(ref['url'][:80])}]({ref['url']})")
            if ref.get("metadata_status") == "retrieved":
                when = format_timestamp(parse_timestamp(ref.get("metadata_retrieved_at")))
                st.caption(f"Title, creator and thumbnail retrieved from {ref.get('metadata_source')} on {when}. "
                           "Nobody has watched the video here.")
            elif ref.get("metadata_status") == "edited":
                st.caption("Title, creator or platform were edited by you.")
            else:
                st.caption("Only the link is saved. The platform did not share the video's details.")
            with st.container(horizontal=True, gap="small"):
                st.link_button("Open video", ref["url"], icon=":material/open_in_new:", type="primary")
                if ref.get("metadata_status") == "not_available" and st.button("Try again to get details", key=f"vr_retry_{rid}"):
                    meta = vr.fetch_metadata(ref["url"])
                    if meta["status"] == "retrieved":
                        def apply():
                            db.apply_retrieved_metadata(rid, meta)
                            _save_thumbnail({**ref, "thumbnail_url": meta["thumbnail_url"]})
                        _act(apply, meta["message"])
                    else:
                        st.info(meta["message"])
                if st.button("Close", key=f"vr_close_{rid}"):
                    st.session_state.pop("_vr_open", None)
                    st.rerun()

        # ---- details and notes
        with st.expander("Details, tags and my notes", icon=":material/edit:"):
            with st.form(f"vr_details_{rid}"):
                title = st.text_input("Title", value=ref.get("title") or "", key=f"vrd_{rid}_title")
                creator = st.text_input("Creator", value=ref.get("creator") or "", key=f"vrd_{rid}_creator")
                platform = st.selectbox("Platform", vr.PLATFORMS, format_func=vr.PLATFORM_LABELS.get,
                                        index=vr.PLATFORMS.index(ref.get("platform") or "other"), key=f"vrd_{rid}_platform")
                tags = st.text_input("Tags (separate with commas)", value=ref.get("tags") or "", key=f"vrd_{rid}_tags")
                notes = st.text_area("Why I like it", value=ref.get("my_notes") or "", key=f"vrd_{rid}_notes")
                if st.form_submit_button("Save details", type="primary"):
                    changed = ((title or None) != ref.get("title") or (creator or None) != ref.get("creator")
                               or platform != ref.get("platform"))
                    _act(lambda: db.update_video_ref(rid, {"title": title, "creator": creator, "platform": platform,
                                                           "tags": tags, "my_notes": notes}, details_changed=changed),
                         "Details saved.")

        # ---- material for analysis
        with st.expander("Material for analysis: screenshots, transcript, description", icon=":material/attach_file:"):
            st.caption("Claude cannot watch videos here. Add screenshots, a transcript or your own description "
                       "so the analysis is based on something real.")
            shots = ref.get("screenshot_paths") or []
            if shots:
                columns = st.columns(3)
                for i, path in enumerate(shots):
                    with columns[i % 3]:
                        link = db.signed_url(path)
                        if link:
                            st.image(link)
                        if st.button("Remove", key=f"vr_shot_del_{rid}_{i}"):
                            def remove(p=path):
                                db.remove_file(p)
                                db.update_video_ref(rid, {"screenshot_paths": [x for x in shots if x != p]})
                            _act(remove, "Screenshot removed.")
            files = st.file_uploader("Add screenshots", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True,
                                     key=f"vr_shots_{rid}")
            if files and st.button("Upload screenshots", key=f"vr_shots_go_{rid}"):
                def upload():
                    paths = list(shots)
                    for f in files[:10]:
                        if f.size > 5_000_000:
                            raise db.DataError(f"{f.name} is larger than 5 MB.")
                        paths.append(db.upload_file(auth.current_user_id(), rid, f.name, f.getvalue(), f.type or "image/jpeg"))
                    db.update_video_ref(rid, {"screenshot_paths": paths})
                _act(upload, "Screenshots saved.")
            text_file = st.file_uploader("Or load a transcript file (.txt, .srt, .vtt)", type=["txt", "srt", "vtt"],
                                         key=f"vr_tfile_{rid}")
            if text_file and st.button("Use this file as the transcript", key=f"vr_tfile_go_{rid}"):
                text = text_file.getvalue().decode("utf-8", "replace")[:60000]
                _act(lambda: db.update_video_ref(rid, {"transcript": text}), "Transcript saved.")
            with st.form(f"vr_material_{rid}"):
                transcript = st.text_area("Transcript", value=ref.get("transcript") or "", height=140, key=f"vrm_{rid}_t")
                description = st.text_area("My description of what happens on screen", value=ref.get("description") or "",
                                           height=110, key=f"vrm_{rid}_d")
                if st.form_submit_button("Save material"):
                    _act(lambda: db.update_video_ref(rid, {"transcript": transcript, "description": description}),
                         "Material saved.")

        # ---- creative analysis
        st.markdown("**Creative analysis**")
        names = [f for f, _ in vr.ANALYSIS_FIELDS]
        _init_fields(ref, names)
        basis_key = _field_key(rid, "analysis_basis")
        if basis_key not in st.session_state:
            st.session_state[basis_key] = ref.get("analysis_basis") or "not_analysed"

        if claude_api.is_configured() and (ref.get("transcript") or ref.get("description")):
            if st.button("Draft the analysis from my transcript and description", key=f"vr_draft_{rid}",
                         icon=":material/auto_awesome:"):
                material = "\n\n".join(x for x in [
                    f"Transcript:\n{ref['transcript']}" if ref.get("transcript") else "",
                    f"My description:\n{ref['description']}" if ref.get("description") else "",
                ] if x)
                try:
                    with st.spinner("Asking Claude…"):
                        draft = vr.parse_analysis_json(claude_api.ask(vr.DRAFT_ANALYSIS_INSTRUCTIONS + material, 1500))
                except (claude_api.ClaudeError, ValueError) as exc:
                    st.error(str(exc))
                else:
                    for name, value in draft.items():
                        st.session_state[_field_key(rid, name)] = value
                    st.session_state[basis_key] = "claude_draft_from_materials"
                    st.info("Claude's draft is filled in below. Check and edit it, then press Save analysis.")
        elif not claude_api.is_configured():
            st.caption("Fill these in yourself after watching. (With an Anthropic API key in the app's Secrets, "
                       "Claude can draft them from your transcript or description.)")

        with st.form(f"vr_analysis_{rid}"):
            values = {}
            for name, label in vr.ANALYSIS_FIELDS:
                values[name] = st.text_area(label, key=_field_key(rid, name), height=80)
            basis = st.selectbox("What this analysis is based on", vr.ANALYSIS_BASIS,
                                 format_func=vr.ANALYSIS_BASIS_LABELS.get, key=basis_key)
            if st.form_submit_button("Save analysis", type="primary"):
                if basis == "not_analysed" and any(v.strip() for v in values.values()):
                    st.error("Please say what the analysis is based on.")
                else:
                    _act(lambda: db.update_video_ref(rid, {**values, "analysis_basis": basis}), "Analysis saved.")

        confirm = st.checkbox("Yes, delete this reference and its stored files", key=f"vr_del_ok_{rid}")
        if st.button("Delete reference", key=f"vr_del_{rid}", disabled=not confirm):
            st.session_state.pop("_vr_open", None)
            _act(lambda: db.delete_video_ref(ref), "Reference deleted.")


def _gallery_tab(refs: list[dict]) -> None:
    open_id = st.session_state.get("_vr_open")
    opened = next((r for r in refs if r["id"] == open_id), None)
    if opened:
        _detail(opened)
        st.write("")

    if not refs:
        ui.empty_state("No references yet", "Paste your first video link in the Save tab.")
        return
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        query = st.text_input("Search", placeholder="Words in titles, notes, tags or analysis", key="vr_q")
    with c2:
        platform = st.selectbox("Platform", ["all"] + vr.PLATFORMS,
                                format_func=lambda p: "All" if p == "all" else vr.PLATFORM_LABELS[p], key="vr_pf")
    with c3:
        tags = sorted({t for r in refs for t in vr.tags_of(r)}, key=str.lower)
        tag = st.selectbox("Tag", ["all"] + tags, format_func=lambda t: "All" if t == "all" else t, key="vr_tag")
    with c4:
        state = st.selectbox("Analysis", ["all", "analysed", "not_analysed"], key="vr_an",
                             format_func={"all": "All", "analysed": "Analysed", "not_analysed": "Not analysed"}.get)
    shown = [
        r for r in refs
        if vr.matches(r, query)
        and (platform == "all" or r.get("platform") == platform)
        and (tag == "all" or tag in vr.tags_of(r))
        and (state == "all" or (state == "analysed") == vr.has_analysis(r))
    ]
    st.caption(f"Showing {len(shown)} of {len(refs)} references.")
    if not shown:
        ui.empty_state("No matches", "Try fewer words, or set the filters back to All.")
        return
    columns = st.columns(3)
    for i, ref in enumerate(shown):
        with columns[i % 3]:
            _card(ref)


# ------------------------------------------------------------- make a video


def _make_tab(refs: list[dict]) -> None:
    if not refs:
        ui.empty_state("Save some references first", "Then choose one or more of them here to plan a new video.")
        return
    st.caption("Choose references, describe the Biology topic, and get an original video plan built only from "
               "what you recorded about each reference.")
    by_id = {r["id"]: r for r in refs}
    chosen = st.multiselect(
        "References to draw on", list(by_id),
        format_func=lambda i: (by_id[i].get("title") or by_id[i]["url"])[:70]
        + ("" if vr.has_analysis(by_id[i]) else " (not analysed)"),
        key="mk_refs",
    )
    thin = [by_id[i] for i in chosen if not vr.has_analysis(by_id[i])]
    if thin:
        st.warning(f"{len(thin)} chosen reference(s) have no analysis yet, so only their notes can be used. "
                   "Add an analysis in the Gallery for a better plan.")
    topic = st.text_input("Biology topic", placeholder="e.g. Kenapa antibiotics tak boleh bunuh viruses?", key="mk_topic")
    c1, c2 = st.columns(2)
    with c1:
        level = st.selectbox("Level", vr.LEVELS, key="mk_level")
    with c2:
        length = st.selectbox("Length", vr.LENGTHS, index=1, key="mk_length")
    extra = st.text_area("Anything else (optional)", placeholder="e.g. faceless, uses a common SPM mistake as the hook",
                         height=70, key="mk_extra")

    if st.button("Build the brief", type="primary", key="mk_build", disabled=not chosen or not topic.strip()):
        st.session_state["_mk_brief"] = vr.build_brief([by_id[i] for i in chosen], topic, level, length, extra)
        st.session_state["_mk_meta"] = {"refs": chosen, "topic": topic, "level": level}
        st.session_state.pop("_mk_result", None)
    if not chosen or not topic.strip():
        st.caption("Choose at least one reference and write a topic to build the brief.")

    brief = st.session_state.get("_mk_brief")
    if not brief:
        return
    meta = st.session_state.get("_mk_meta", {})
    ui.section("Brief")
    st.code(brief, language=None)

    if claude_api.is_configured():
        if st.button("Generate the video plan with Claude", key="mk_generate", icon=":material/auto_awesome:"):
            try:
                with st.spinner("Claude is writing the concept, script and storyboard…"):
                    st.session_state["_mk_result"] = {"text": claude_api.ask(vr.CONCEPT_INSTRUCTIONS + brief),
                                                      "source": "claude_api"}
            except claude_api.ClaudeError as exc:
                st.error(str(exc))
    else:
        st.info("To get the plan: copy the brief with the copy button at its top right, paste it into a Claude chat "
                "with the instruction below, then paste Claude's answer underneath.")
        st.code(vr.CONCEPT_INSTRUCTIONS.strip().replace("\nBrief:", "\n(Then paste the brief.)"), language=None)
        pasted = st.text_area("Paste Claude's answer here", height=220, key="mk_pasted")
        if pasted.strip():
            st.session_state["_mk_result"] = {"text": pasted, "source": "pasted"}

    result = st.session_state.get("_mk_result")
    if result:
        ui.section("Video plan")
        if result["source"] == "claude_api":
            st.caption("Written by Claude from the brief above. Check every [CHECK] fact against your textbook.")
            st.markdown(result["text"])
        with st.form("mk_save"):
            title = st.text_input("Save as", value=meta.get("topic", "")[:120], key="mk_title")
            if st.form_submit_button("Save video plan", type="primary"):
                def save():
                    db.save_concept(title, meta.get("topic"), meta.get("level"), meta.get("refs", []),
                                    brief, result["text"], result["source"])
                    for key in ("_mk_brief", "_mk_result", "_mk_meta"):
                        st.session_state.pop(key, None)
                _act(save, "Video plan saved. Find it in the Video plans tab.")


# ------------------------------------------------------------------ concepts

CONCEPT_STATUS = {"draft": "Draft", "approved": "Approved", "in_tracker": "Added to my content tracker"}


def _concepts_tab(concepts: list[dict], refs: list[dict]) -> None:
    if not concepts:
        ui.empty_state("No video plans yet", "Build one in the Make a video tab.")
        return
    titles = {r["id"]: (r.get("title") or r["url"]) for r in refs}
    for c in concepts:
        cid = c["id"]
        when = format_date(parse_timestamp(c.get("created_at")).date()) if parse_timestamp(c.get("created_at")) else ""
        with st.expander(f"{c['title']} · {CONCEPT_STATUS.get(c.get('status'), 'Draft')} · {when}"):
            used = [titles.get(i, "a deleted reference") for i in (c.get("reference_ids") or [])]
            source = {"claude_api": "Written by Claude from the saved brief", "pasted": "Pasted from a Claude chat",
                      "written": "Written by me"}.get(c.get("source"), "")
            st.caption(" · ".join(x for x in [source, f"References: {', '.join(used)}" if used else ""] if x))
            st.markdown(c.get("body") or "")
            if c.get("brief"):
                if st.toggle("Show the brief it was built from", key=f"vc_brief_{cid}"):
                    st.code(c["brief"], language=None)
            if st.toggle("Edit", key=f"vc_edit_{cid}"):
                with st.form(f"vc_form_{cid}"):
                    title = st.text_input("Title", value=c["title"], key=f"vc_title_{cid}")
                    status = st.selectbox("Status", list(CONCEPT_STATUS), format_func=CONCEPT_STATUS.get,
                                          index=list(CONCEPT_STATUS).index(c.get("status") or "draft"), key=f"vc_status_{cid}")
                    body = st.text_area("Plan", value=c.get("body") or "", height=300, key=f"vc_body_{cid}")
                    if st.form_submit_button("Save", type="primary"):
                        _act(lambda: db.update_concept(cid, title, body, status), "Video plan saved.")
                ok = st.checkbox("Yes, delete this video plan", key=f"vc_del_ok_{cid}")
                if st.button("Delete", key=f"vc_del_{cid}", disabled=not ok):
                    _act(lambda: db.delete_concept(cid), "Video plan deleted.")


# --------------------------------------------------------------------- main


def render() -> None:
    """Draw the library. Called from the Creator Lab page."""
    st.caption("Paste a link, save it, organise it, reuse it.")
    try:
        refs = db.list_video_refs()
        concepts = db.list_concepts()
    except db.DataError as exc:
        st.error(str(exc))
        st.info("The library needs migration 0008. In Supabase, open the SQL Editor, run "
                "supabase/migrations/0008_video_library.sql, then reload this page.")
        st.stop()

    save, gallery, make, plans = st.tabs(["Save", f"Gallery ({len(refs)})", "Make a video",
                                          f"Video plans ({len(concepts)})"])
    with save:
        _save_tab()
    with gallery:
        _gallery_tab(refs)
    with make:
        _make_tab(refs)
    with plans:
        _concepts_tab(concepts, refs)
