"""ICRC review platform (Streamlit).

    streamlit run app.py
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

st.markdown(
    """
    <style>
      .chip {display:inline-block;padding:2px 8px;border-radius:4px;color:#fff;font-size:12px;font-weight:600;margin-right:6px}
      .label {display:inline-block;padding:1px 6px;border:1px solid #8792a1;border-radius:4px;font-size:12px;margin:0 4px 4px 0}
      .blurred {filter: blur(6px); user-select:none}
      .post {padding:10px 12px;border-left:3px solid #8792a1;background:rgba(135,146,161,.08);border-radius:4px}
    </style>
    """,
    unsafe_allow_html=True,
)

conn = db.connect()

# --- Sign-in ------------------------------------------------------------------

if "role" not in st.session_state:
    st.session_state.role = None

with st.sidebar:
    st.header("Harmwatch")
    if st.session_state.role is None:
        role = st.radio("I am", ["Volunteer", "ICRC analyst"], key="role_choice")
        password = st.text_input("ICRC password", type="password", key="pw") if role == "ICRC analyst" else ""
        if st.button("Sign in", key="signin"):
            if role == "ICRC analyst" and password != os.getenv("ICRC_PASSWORD", "demo"):
                st.error("Wrong password.")
            else:
                st.session_state.role = role
                st.rerun()
    else:
        st.write(f"Signed in as **{st.session_state.role}**")
        st.caption(f"Classifier: `{backend_name()}`")
        if st.button("Sign out", key="signout"):
            st.session_state.role = None
            st.rerun()

if st.session_state.role is None:
    st.title("Harmwatch")
    st.write("Flags harmful content related to sexual violence for review by ICRC analysts. Sign in from the sidebar.")
    st.stop()


# --- Views --------------------------------------------------------------------

def report_form():
    st.subheader("Report a post")
    st.caption("Paste the text of a post you think is harmful. Do not upload photos or videos.")
    with st.form("report", clear_on_submit=True):
        text = st.text_area("Post text", key="r_text")
        link = st.text_input("Link to the post (optional)", key="r_link")
        channel = st.text_input("Channel (optional)", key="r_channel")
        note = st.text_input("Why are you reporting it? (optional)", key="r_note")
        if st.form_submit_button("Send report") and text.strip():
            post_id = db.add_post(conn, source="volunteer", text=text.strip(), channel=channel or None,
                                  url=link or None, note=note or None, reporter="web")
            if post_id is None:
                st.info("This post was already reported.")
            else:
                post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
                classify_post(conn, post)
                st.success("Thank you. The post was added to the review queue.")


def chip(bucket: str) -> str:
    label, color = BUCKET_STYLE[bucket]
    return f'<span class="chip" style="background:{color}">{label}</span>'


def review_queue():
    items = db.queue(conn)
    counts = Counter(i["bucket"] for i in items)
    cols = st.columns(4)
    for col, bucket in zip(cols, BUCKET_STYLE):
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
                item["views"] is not None and f"{item['views']:,} views",
                item["forwards"] is not None and f"{item['forwards']:,} forwards",
                item["source"] == "volunteer" and "reported by a volunteer",
            ]))
            st.markdown(f"{chip(item['bucket'])} <small>{html.escape(meta)}</small>", unsafe_allow_html=True)

            if item["bucket"] == ESCALATE:
                st.error("Possible involvement of a child. The text is hidden. Escalate to the legal team; do not share.")
            else:
                st.markdown(f"**Summary:** {html.escape(c.summary)}")
                labels = "".join(f'<span class="label">{h}</span>' for h in c.harm_types) or '<span class="label">no harm type</span>'
                st.markdown(
                    f"{labels}<br><small>tone: {c.tone} · claim: {c.claim_status} · victims: {', '.join(c.victims)}"
                    f" · potential: {c.harm_potential}/3 · confidence: {c.confidence}</small>",
                    unsafe_allow_html=True,
                )
                reveal = st.toggle("Show post text", key=f"reveal_{item['id']}")
                css = "post" if reveal else "post blurred"
                st.markdown(f'<div class="{css}">{html.escape(item["text"])}</div>', unsafe_allow_html=True)
                st.caption(f"Why: {c.rationale}")
                if item["url"] and item["url"].startswith("https://"):
                    st.caption(item["url"])
                if item["note"]:
                    st.caption(f"Volunteer note: {item['note']}")

            note = st.text_input("Note", key=f"note_{item['id']}", label_visibility="collapsed", placeholder="Note (optional)")
            buttons = st.columns(len(DECISIONS))
            for col, (value, label) in zip(buttons, DECISIONS.items()):
                if col.button(label, key=f"{value}_{item['id']}"):
                    db.save_decision(conn, item["id"], value, note, "icrc")
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
            reach[i["channel"] or "unknown"] += i["views"] or 0
        st.bar_chart(pd.Series(reach, name="views").sort_values(ascending=False).head(10), horizontal=True)

    st.subheader("Decisions")
    decided = Counter(DECISIONS.get(i["decision"], "Awaiting review") for i in items)
    st.write(dict(decided))
    st.caption("Next: recurrence clusters, spread over time and locations (tasks M5, M6, P7).")


def export():
    rows = db.export_decisions(conn)
    st.write(f"{len(rows)} reviewed posts. This file is the feedback dataset for improving the classifier.")
    st.download_button("Download decisions (JSON)", json.dumps(rows, ensure_ascii=False, indent=2),
                       file_name="decisions.json", mime="application/json", key="export")


if st.session_state.role == "Volunteer":
    report_form()
else:
    tabs = st.tabs(["Review queue", "Tracking", "Report a post", "Export"])
    with tabs[0]:
        review_queue()
    with tabs[1]:
        tracking()
    with tabs[2]:
        report_form()
    with tabs[3]:
        export()
