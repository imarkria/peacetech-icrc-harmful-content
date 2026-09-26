"""Harmwatch web app (Streamlit).

    streamlit run app.py

Pages: landing → report → thank you (outside users, no login)
       landing → sign in → control board (ICRC reviewers)
"""

import html
import json
import os
from collections import Counter

import pandas as pd
import streamlit as st

from harmwatch import db
from harmwatch.classify import backend_name
from harmwatch.pipeline import classify_post
from harmwatch.triage import ESCALATE, HARMFUL, NOT_HARMFUL, POTENTIAL

st.set_page_config(page_title="Harmwatch", page_icon="🛡️", layout="wide")

BUCKET_STYLE = {
    ESCALATE: ("Escalate", "#7a1f1f"),
    HARMFUL: ("Harmful", "#b3261e"),
    POTENTIAL: ("Potentially harmful", "#a8660f"),
    NOT_HARMFUL: ("Not harmful", "#4a6b4a"),
}
DECISIONS = {"yes": "Yes, harmful", "no": "No", "not_processed": "Not processed"}
PLATFORMS = ["Telegram", "TikTok", "Facebook", "X (Twitter)", "Instagram", "WhatsApp", "YouTube", "Other"]
TARGETS = {
    "woman": "A woman or women",
    "child": "A child",
    "man": "A man or men",
    "group": "A group (ethnic, national, prisoners…)",
    "unsure": "I'm not sure",
}
KINDS = {
    "threat": "A threat or a call to violence",
    "mockery": "Jokes or mockery",
    "identity": "Someone's identity or location shared",
    "explicit": "Explicit content",
    "claim": "A claim that seems false or unverified",
    "other": "Something else",
}

st.markdown(
    """
    <style>
      .chip {display:inline-block;padding:2px 8px;border-radius:4px;color:#fff;font-size:12px;font-weight:600;margin-right:6px}
      .label {display:inline-block;padding:1px 6px;border:1px solid #8792a1;border-radius:4px;font-size:12px;margin:0 4px 4px 0}
      .blurred {filter: blur(6px); user-select:none}
      .post {padding:10px 12px;border-left:3px solid #8792a1;background:rgba(135,146,161,.08);border-radius:4px}
      .hero {max-width:720px;margin:6vh auto 2rem;text-align:center}
      .hero h1 {font-size:2.4rem;margin-bottom:.25rem}
      .hero p {font-size:1.1rem;opacity:.8}
    </style>
    """,
    unsafe_allow_html=True,
)

conn = db.connect()

st.session_state.setdefault("page", "landing")
st.session_state.setdefault("reviewer", None)


def go(page: str):
    st.session_state.page = page
    st.rerun()


def reviewers() -> dict[str, str]:
    """ICRC_USERS="name:password,name2:password2" (default reviewer:demo)."""
    pairs = (p.split(":", 1) for p in os.getenv("ICRC_USERS", "reviewer:demo").split(",") if ":" in p)
    return {name.strip(): pw.strip() for name, pw in pairs}


# --- Outside users -------------------------------------------------------------

def landing():
    st.markdown(
        '<div class="hero"><h1>Harmwatch</h1>'
        "<p>Report online content that threatens, mocks or exposes people in connection with sexual violence. "
        "Reports are reviewed by trained ICRC staff.</p></div>",
        unsafe_allow_html=True,
    )
    _, left, right, _ = st.columns([1, 2, 2, 1])
    with left, st.container(border=True):
        st.subheader("Report content")
        st.write("No account needed. You can stay anonymous.")
        if st.button("Report content", type="primary", use_container_width=True, key="go_report"):
            go("report")
    with right, st.container(border=True):
        st.subheader("ICRC review")
        st.write("For ICRC staff. Sign in to open the control board.")
        if st.button("Review", use_container_width=True, key="go_login"):
            go("board" if st.session_state.reviewer else "login")


def report_page():
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        report_form()


def report_form():
    if st.button("← Back", key="back_report"):
        go("landing")
    st.title("Report content")
    st.write("Tell us what you saw. Share a link, paste the text, or describe it. Only a link or some text is required.")
    st.info("Please don't upload or send photos or videos. Describe them in words instead. "
            "If you or someone else is in immediate danger, contact local emergency services.", icon="ℹ️")

    with st.form("report"):
        link = st.text_input("Link to the content", placeholder="https://t.me/channel/1234", key="r_link")
        text = st.text_area("Text of the post, or a description of what you saw", height=140, key="r_text")
        platform = st.selectbox("Where did you see it?", PLATFORMS, index=None, placeholder="Choose a platform", key="r_platform")
        location = st.text_input("Which place does it concern? (optional)", placeholder="City, region or country", key="r_location")
        targets = st.multiselect("Who seems to be targeted? (optional)", list(TARGETS), format_func=TARGETS.get, key="r_targets")
        kinds = st.multiselect("What kind of content is it? (optional)", list(KINDS), format_func=KINDS.get, key="r_kinds")
        note = st.text_area("Anything else we should know? (optional)", height=80, key="r_note")
        contact = st.text_input("Contact, if you agree to be contacted (optional)", placeholder="Leave empty to stay anonymous", key="r_contact")
        submitted = st.form_submit_button("Send report", type="primary")

    if submitted:
        if not link.strip() and not text.strip():
            st.error("Add a link or some text so reviewers know what you saw.")
            return
        post_id = db.add_post(
            conn, source="volunteer", text=text.strip(), url=link.strip() or None, reporter="web",
            note=note.strip() or None, platform=platform, location=location.strip() or None,
            targets=targets, kinds=kinds, contact=contact.strip() or None,
        )
        if post_id is not None:
            classify_post(conn, db.get_post(conn, post_id))
        go("thanks")


def thanks_page():
    st.markdown(
        '<div class="hero"><h1>Thank you</h1>'
        "<p>Your report was received. A trained ICRC reviewer will look at it. "
        "You won't get an automatic reply, and your report stays confidential.</p></div>",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.caption("If this content affects you personally, support is available. "
                   "[Add local support services here with the ICRC team.]")
        c1, c2 = st.columns(2)
        if c1.button("Report something else", use_container_width=True, key="again"):
            go("report")
        if c2.button("Back to home", use_container_width=True, key="home"):
            go("landing")


# --- ICRC reviewers ------------------------------------------------------------

def login_page():
    if st.button("← Back", key="back_login"):
        go("landing")
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid, st.form("login"):
        st.subheader("ICRC sign in")
        user = st.text_input("Username", key="l_user")
        password = st.text_input("Password", type="password", key="l_pw")
        if st.form_submit_button("Sign in", type="primary", use_container_width=True):
            if reviewers().get(user.strip()) == password and password:
                st.session_state.reviewer = user.strip()
                go("board")
            else:
                st.error("Wrong username or password.")


def chip(bucket: str) -> str:
    label, color = BUCKET_STYLE[bucket]
    return f'<span class="chip" style="background:{color}">{label}</span>'


def review_queue():
    items = db.queue(conn)
    counts = Counter(i["bucket"] for i in items)
    for col, bucket in zip(st.columns(4), BUCKET_STYLE):
        col.metric(BUCKET_STYLE[bucket][0], counts.get(bucket, 0))

    shown = st.multiselect(
        "Show", list(BUCKET_STYLE), default=[ESCALATE, HARMFUL, POTENTIAL],
        format_func=lambda b: BUCKET_STYLE[b][0], key="bucket_filter",
    )
    for item in (i for i in items if i["bucket"] in shown):
        c = item["result"]
        with st.container(border=True):
            meta = " · ".join(filter(None, [
                item["channel"] and f"@{item['channel']}",
                item["platform"],
                item["views"] is not None and f"{item['views']:,} views",
                item["forwards"] is not None and f"{item['forwards']:,} forwards",
                item["source"] == "volunteer" and "reported by an outside user",
            ]))
            st.markdown(f"{chip(item['bucket'])} <small>{html.escape(meta)}</small>", unsafe_allow_html=True)

            if item["bucket"] == ESCALATE:
                st.error("Possible involvement of a child. The content is hidden. Escalate to the legal team; do not share.")
            else:
                st.markdown(f"**Summary:** {html.escape(c.summary)}")
                labels = "".join(f'<span class="label">{h}</span>' for h in c.harm_types) or '<span class="label">no harm type</span>'
                st.markdown(
                    f"{labels}<br><small>tone: {c.tone} · claim: {c.claim_status} · victims: {', '.join(c.victims)}"
                    f" · potential: {c.harm_potential}/3 · confidence: {c.confidence}</small>",
                    unsafe_allow_html=True,
                )
                if item["text"]:
                    reveal = st.toggle("Show post text", key=f"reveal_{item['id']}")
                    css = "post" if reveal else "post blurred"
                    st.markdown(f'<div class="{css}">{html.escape(item["text"])}</div>', unsafe_allow_html=True)
                st.caption(f"Why: {c.rationale}")
                if item["url"] and item["url"].startswith("https://"):
                    st.caption(item["url"])

            if item["source"] == "volunteer":
                reported = " · ".join(filter(None, [
                    item["location"] and f"location: {item['location']}",
                    item["targets"] and "targeted: " + ", ".join(item["targets"]),
                    item["kinds"] and "kind: " + ", ".join(item["kinds"]),
                    item["contact"] and "reporter can be contacted",
                ]))
                if reported:
                    st.caption(f"Reporter says: {reported}")
                if item["note"]:
                    st.caption(f"Reporter note: {item['note']}")

            note = st.text_input("Note", key=f"note_{item['id']}", label_visibility="collapsed", placeholder="Note (optional)")
            for col, (value, label) in zip(st.columns(len(DECISIONS)), DECISIONS.items()):
                if col.button(label, key=f"{value}_{item['id']}"):
                    db.save_decision(conn, item["id"], value, note, st.session_state.reviewer)
                    st.rerun()


def tracking():
    items = db.queue(conn, include_decided=True)
    if not items:
        st.info("No classified posts yet.")
        return
    flagged = [i for i in items if i["bucket"] != NOT_HARMFUL]

    left, right = st.columns(2)
    with left:
        st.subheader("Harm types")
        harm_counts = Counter(h for i in flagged for h in i["result"].harm_types)
        st.bar_chart(pd.Series(harm_counts, name="posts").sort_values(ascending=False), horizontal=True)
    with right:
        st.subheader("Channels by reach of flagged posts")
        reach = Counter()
        for i in flagged:
            reach[i["channel"] or i["platform"] or "unknown"] += i["views"] or 0
        st.bar_chart(pd.Series(reach, name="views").sort_values(ascending=False).head(10), horizontal=True)

    st.subheader("Decisions")
    st.write(dict(Counter(DECISIONS.get(i["decision"], "Awaiting review") for i in items)))
    st.caption("Next: recurrence clusters, spread over time and locations (tasks M5, M6, P7).")


def export():
    rows = db.export_decisions(conn)
    st.write(f"{len(rows)} reviewed posts. This file is the feedback dataset for improving the classifier.")
    st.download_button("Download decisions (JSON)", json.dumps(rows, ensure_ascii=False, indent=2),
                       file_name="decisions.json", mime="application/json", key="export")


def board():
    if not st.session_state.reviewer:
        go("login")
    with st.sidebar:
        st.header("Harmwatch")
        st.write(f"Signed in as **{st.session_state.reviewer}**")
        st.caption(f"Classifier: `{backend_name()}`")
        if st.button("Sign out", key="signout"):
            st.session_state.reviewer = None
            go("landing")
    st.title("Control board")
    tabs = st.tabs(["Review queue", "Tracking", "Export"])
    with tabs[0]:
        review_queue()
    with tabs[1]:
        tracking()
    with tabs[2]:
        export()


PAGES = {"landing": landing, "report": report_page, "thanks": thanks_page, "login": login_page, "board": board}
PAGES[st.session_state.page]()
