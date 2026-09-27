"""Small Facebook collection proof of concept with media inside SQLite.

Install: pip install apify-client requests streamlit
CLI:     python icrc_social_collector.py --query Ukraine --max-posts 5
UI:      streamlit run icrc_social_collector.py -- --ui
Notebook: %run icrc_social_collector.py --query Ukraine --max-posts 5
Reuse:   python icrc_social_collector.py --run-id YOUR_COMPLETED_RUN_ID

The default output is collector.sqlite3. Its content_items table stores the
actual image/video bytes in a BLOB column. Use --format both for the optional
machine-readable Base64 CSV with caption, date_posted, content columns.
"""

from __future__ import annotations

import argparse
import base64
import csv
import getpass
import hashlib
import io
import json
import mimetypes
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ACTOR = "danek/facebook-search-ppr"
PLATFORM = "facebook"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_VIDEO_BYTES = 100 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/gif": ".gif",
    "video/mp4": ".mp4", "video/webm": ".webm",
}


def utc_timestamp(value):
    if value is None:
        return ""
    return datetime.fromtimestamp(int(value), timezone.utc).isoformat()


def initialize(db):
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            actor TEXT NOT NULL,
            query TEXT NOT NULL,
            input_json TEXT NOT NULL,
            dataset_id TEXT NOT NULL,
            result_count INTEGER NOT NULL,
            collected_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS posts (
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            caption TEXT NOT NULL,
            date_posted TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (platform, post_id)
        );
        CREATE TABLE IF NOT EXISTS media (
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            variant TEXT NOT NULL,
            source_url TEXT NOT NULL,
            local_path TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            PRIMARY KEY (platform, post_id, variant),
            FOREIGN KEY (platform, post_id) REFERENCES posts(platform, post_id)
        );
        CREATE TABLE IF NOT EXISTS content_items (
            id INTEGER PRIMARY KEY,
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            variant TEXT NOT NULL,
            caption TEXT NOT NULL,
            date_posted TEXT NOT NULL,
            media_type TEXT,
            content BLOB,
            sha256 TEXT,
            UNIQUE (platform, post_id, variant),
            FOREIGN KEY (platform, post_id) REFERENCES posts(platform, post_id)
        );
    """)


def collect(client, query, max_posts, recent, start_date, end_date, dataset_id, existing_run_id):
    if dataset_id and existing_run_id:
        raise ValueError("Specify either a dataset ID or a run ID, not both")
    if existing_run_id:
        earlier_run = client.run(existing_run_id).get()
        if earlier_run is None or earlier_run.status != "SUCCEEDED":
            raise RuntimeError("The selected Apify run was not found or did not succeed")
        dataset_id = earlier_run.default_dataset_id
        if not dataset_id:
            raise RuntimeError("The selected Apify run has no default dataset")
        config = {"reused_run_id": existing_run_id}
        run_id = existing_run_id
    elif dataset_id:
        config = {"imported_dataset_id": dataset_id}
        run_id = "dataset:" + dataset_id
    else:
        config = {
            "query": query,
            "search_type": "posts",
            "max_posts": max_posts,
            "recent_posts": recent,
        }
        if start_date:
            config["start_date"] = start_date
        if end_date:
            config["end_date"] = end_date
        run = client.actor(ACTOR).call(run_input=config)
        if run is None or run.status != "SUCCEEDED" or not run.default_dataset_id:
            raise RuntimeError(f"Actor run did not succeed: {getattr(run, 'status', None)}")
        run_id, dataset_id = run.id, run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())
    return run_id, dataset_id, config, items


def direct_image_urls(item):
    """Find direct CDN images in the known image and album-preview fields."""
    urls = []

    def visit(value):
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            parsed = urlsplit(value)
            host = (parsed.hostname or "").lower()
            if (parsed.scheme == "https"
                and (host == "fbcdn.net" or host.endswith(".fbcdn.net"))
                and parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
                and value not in urls):
                urls.append(value)

    visit(item.get("image"))
    visit(item.get("album_preview"))
    return urls


def save_results(db, run_id, dataset_id, config, query, items):
    now = datetime.now(timezone.utc).isoformat()
    warnings = []
    with db:
        db.execute("""
            INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                result_count=excluded.result_count,
                collected_at_utc=excluded.collected_at_utc
        """, (run_id, ACTOR, query, json.dumps(config), dataset_id, len(items), now))
        for item in items:
            post_id = item.get("post_id")
            if not post_id:
                raise ValueError("A result has no post_id; cannot deduplicate it safely")
            post_id = str(post_id)
            db.execute("""
                INSERT INTO posts VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(platform, post_id) DO UPDATE SET
                    caption=excluded.caption,
                    date_posted=excluded.date_posted,
                    raw_json=excluded.raw_json
            """, (PLATFORM, post_id, item.get("message") or "",
                  utc_timestamp(item.get("timestamp")),
                  json.dumps(item, ensure_ascii=False, default=str)))

            image_urls = direct_image_urls(item)
            discovered = {f"image_{index}": url for index, url in enumerate(image_urls)}
            if item.get("album_preview"):
                warnings.append(
                    f"Post {post_id} has an album preview: {len(image_urls)} direct image "
                    "link(s) found. The Actor may not expose the full album."
                )
            reported = item.get("images_count")
            if isinstance(reported, int) and reported > len(image_urls):
                warnings.append(
                    f"Post {post_id} reports {reported} images but only "
                    f"{len(image_urls)} direct image link(s) were found."
                )
            video_files = item.get("video_files") or {}
            if isinstance(video_files, dict):
                for field, variant in (("video_sd_file", "video_sd"),
                                       ("video_hd_file", "video_hd")):
                    if video_files.get(field):
                        discovered[variant] = video_files[field]
            for variant, url in discovered.items():
                db.execute("""
                    INSERT INTO media(platform, post_id, variant, source_url)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(platform, post_id, variant) DO UPDATE SET
                        source_url=excluded.source_url
                """, (PLATFORM, post_id, variant, url))
    return warnings


def download(url, destination_dir, is_video):
    """Download a single allowed CDN file without following redirects."""
    import requests

    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "fbcdn.net" or host.endswith(".fbcdn.net")):
        raise ValueError("Unexpected media host")
    cap = MAX_VIDEO_BYTES if is_video else MAX_IMAGE_BYTES
    temp_name = None
    try:
        with requests.get(url, stream=True, timeout=(5, 60), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if mime not in ALLOWED_TYPES or mime.startswith("video/") != is_video:
                raise ValueError(f"Unexpected content type: {mime}")
            length = response.headers.get("Content-Length")
            if length and int(length) > cap:
                raise ValueError("File exceeds configured size limit")
            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(dir=destination_dir, suffix=".part", delete=False) as tmp:
                temp_name = Path(tmp.name)
                for chunk in response.iter_content(chunk_size=262_144):
                    if chunk:
                        size += len(chunk)
                        if size > cap:
                            raise ValueError("File exceeds configured size limit")
                        digest.update(chunk)
                        tmp.write(chunk)
            if size == 0:
                raise ValueError("Empty media file")
            target = destination_dir / (digest.hexdigest() + ALLOWED_TYPES[mime])
            temp_name.replace(target)
            return target
    finally:
        if temp_name is not None:
            temp_name.unlink(missing_ok=True)


def ensure_media(db, output_dir, post_ids, video_quality):
    """Download all listed images and one preferred video version per post."""
    media_dir = output_dir / "downloaded_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    saved = 0
    for post_id in post_ids:
        rows = db.execute("""
            SELECT variant, source_url, local_path, status
            FROM media WHERE platform=? AND post_id=?
        """, (PLATFORM, post_id)).fetchall()
        by_variant = {row["variant"]: row for row in rows}
        chosen = [row for variant, row in sorted(by_variant.items())
                  if variant.startswith("image_")]
        videos = [by_variant[v] for v in ("video_hd", "video_sd") if v in by_variant]
        if videos:
            preferred = "video_hd" if video_quality == "hd" else "video_sd"
            chosen.append(by_variant.get(preferred) or videos[0])
        for row in chosen:
            variant = row["variant"]
            path = output_dir / row["local_path"] if row["local_path"] else None
            if row["status"] == "downloaded" and path and path.is_file():
                continue
            try:
                target = download(row["source_url"], media_dir, variant.startswith("video_"))
                relative = target.relative_to(output_dir).as_posix()
                with db:
                    db.execute("""
                        UPDATE media SET local_path=?, status='downloaded', error=NULL
                        WHERE platform=? AND post_id=? AND variant=?
                    """, (relative, PLATFORM, post_id, variant))
                saved += 1
            except Exception as exc:
                # Do not print signed source URLs or post text in errors.
                message = f"{type(exc).__name__}: {exc}"
                with db:
                    db.execute("""
                        UPDATE media SET status='failed', error=?
                        WHERE platform=? AND post_id=? AND variant=?
                    """, (message, PLATFORM, post_id, variant))
                errors.append(f"post {post_id}, {variant}: {message}")
    return saved, errors


def sync_sqlite_content(db, output_dir, post_ids, video_quality):
    """Copy the selected file bytes into SQLite BLOBs, including text-only posts."""
    count = 0
    with db:
        for post_id in post_ids:
            post = db.execute("""
                SELECT caption, date_posted FROM posts
                WHERE platform=? AND post_id=?
            """, (PLATFORM, post_id)).fetchone()
            media = db.execute("""
                SELECT variant, status, local_path FROM media
                WHERE platform=? AND post_id=?
            """, (PLATFORM, post_id)).fetchall()
            by_variant = {row["variant"]: row for row in media}
            chosen = [row for variant, row in sorted(by_variant.items())
                      if variant.startswith("image_")]
            preferred = "video_hd" if video_quality == "hd" else "video_sd"
            if preferred in by_variant:
                chosen.append(by_variant[preferred])
            elif "video_hd" in by_variant or "video_sd" in by_variant:
                chosen.append(by_variant.get("video_hd") or by_variant["video_sd"])

            keep_variants = [row["variant"] for row in chosen] or ["text"]
            # A rerun may change video quality or add images to a text-only post.
            previous_variants = {
                row[0] for row in db.execute(
                    "SELECT variant FROM content_items WHERE platform=? AND post_id=?",
                    (PLATFORM, post_id),
                )
            }
            if previous_variants != set(keep_variants):
                db.execute("""
                    DELETE FROM content_items WHERE platform=? AND post_id=?
                """, (PLATFORM, post_id))

            if not chosen:
                db.execute("""
                    INSERT INTO content_items
                    (platform, post_id, variant, caption, date_posted)
                    VALUES (?, ?, 'text', ?, ?)
                    ON CONFLICT(platform, post_id, variant) DO UPDATE SET
                        caption=excluded.caption, date_posted=excluded.date_posted
                """, (PLATFORM, post_id, post["caption"], post["date_posted"]))
                count += 1
                continue

            for item in chosen:
                path = output_dir / item["local_path"] if item["local_path"] else None
                if item["status"] != "downloaded" or not path or not path.is_file():
                    raise RuntimeError(f"Media not available for post {post_id}: {item['variant']}")
                mime = mimetypes.guess_type(path.name)[0]
                if mime not in ALLOWED_TYPES:
                    raise ValueError(f"Unsupported saved media type: {path.name}")
                size = path.stat().st_size
                fingerprint = path.stem  # downloader names files by SHA-256
                existing = db.execute("""
                    SELECT id, sha256, length(content), media_type
                    FROM content_items
                    WHERE platform=? AND post_id=? AND variant=?
                """, (PLATFORM, post_id, item["variant"])).fetchone()
                if existing and (existing["sha256"], existing[2], existing["media_type"]) == (fingerprint, size, mime):
                    db.execute("""
                        UPDATE content_items SET caption=?, date_posted=? WHERE id=?
                    """, (post["caption"], post["date_posted"], existing["id"]))
                else:
                    db.execute("""
                        INSERT INTO content_items
                        (platform, post_id, variant, caption, date_posted,
                         media_type, content, sha256)
                        VALUES (?, ?, ?, ?, ?, ?, zeroblob(?), ?)
                        ON CONFLICT(platform, post_id, variant) DO UPDATE SET
                            caption=excluded.caption,
                            date_posted=excluded.date_posted,
                            media_type=excluded.media_type,
                            content=excluded.content,
                            sha256=excluded.sha256
                    """, (PLATFORM, post_id, item["variant"], post["caption"],
                          post["date_posted"], mime, size, fingerprint))
                    content_id = db.execute("""
                        SELECT id FROM content_items
                        WHERE platform=? AND post_id=? AND variant=?
                    """, (PLATFORM, post_id, item["variant"])).fetchone()[0]
                    with path.open("rb") as source, db.blobopen("content_items", "content", content_id) as blob:
                        while chunk := source.read(256 * 1024):
                            blob.write(chunk)
                count += 1
    return count


def csv_prefix(caption, date_posted):
    """Use csv.writer to escape the first two cells for a streamed third cell."""
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerow([caption, date_posted])
    return buffer.getvalue().rstrip("\n")


def append_media_row(file, caption, date_posted, path):
    """Stream Base64 to the CSV instead of loading entire videos in memory."""
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in ALLOWED_TYPES:
        raise ValueError(f"Unknown saved media type: {path.name}")
    file.write(csv_prefix(caption, date_posted))
    file.write(f',"data:{mime};base64,')
    # A multiple of three bytes avoids padding between chunks.
    with path.open("rb") as source:
        while chunk := source.read(3 * 87_381):
            file.write(base64.b64encode(chunk).decode("ascii"))
    file.write('"\n')


def export_csv(db, output_dir, selected_post_ids, video_quality):
    """Export the current collection as caption,date_posted,content."""
    rows = []
    for post_id in selected_post_ids:
        post = db.execute("""
            SELECT caption, date_posted FROM posts
            WHERE platform=? AND post_id=?
        """, (PLATFORM, post_id)).fetchone()
        if post is None:
            raise RuntimeError(f"Post {post_id} was not saved")
        media = db.execute("""
            SELECT variant, status, local_path FROM media
            WHERE platform=? AND post_id=?
        """, (PLATFORM, post_id)).fetchall()
        by_variant = {row["variant"]: row for row in media}
        chosen = [row for variant, row in sorted(by_variant.items())
                  if variant.startswith("image_")]
        preferred = "video_hd" if video_quality == "hd" else "video_sd"
        if preferred in by_variant:
            chosen.append(by_variant[preferred])
        elif "video_hd" in by_variant or "video_sd" in by_variant:
            chosen.append(by_variant.get("video_hd") or by_variant["video_sd"])
        for item in chosen:
            path = output_dir / item["local_path"] if item["local_path"] else None
            if item["status"] != "downloaded" or not path or not path.is_file():
                raise RuntimeError(f"Media not available for post {post_id}: {item['variant']}")
        rows.append((post["caption"], post["date_posted"],
                     [output_dir / item["local_path"] for item in chosen]))

    csv_path = output_dir / "posts_with_content.csv"
    # Atomic export: an interrupted run does not replace an earlier good CSV.
    temp_path = csv_path.with_suffix(".csv.part")
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, lineterminator="\n")
            writer.writerow(["caption", "date_posted", "content"])
            for caption, date_posted, files in rows:
                if not files:
                    writer.writerow([caption, date_posted, ""])
                else:
                    for path in files:
                        append_media_row(file, caption, date_posted, path)
        temp_path.replace(csv_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return csv_path, sum(max(1, len(files)) for _, _, files in rows)


def pipeline(query, max_posts, recent, start_date, end_date,
             video_quality, output_dir, dataset_id=None, run_id=None,
             client=None, output_format="sqlite"):
    if not query.strip():
        raise ValueError("Search query is required")
    if max_posts < 1:
        raise ValueError("Maximum posts must be positive")
    if output_format not in ("sqlite", "both"):
        raise ValueError("Output format must be sqlite or both")
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if client is None:
        token = os.getenv("APIFY_TOKEN")
        if not token:
            if sys.stdin.isatty():
                token = getpass.getpass("Apify API token: ").strip()
            if not token:
                raise RuntimeError(
                    "Apify token required. Run this script in a terminal to enter it "
                    "when prompted, or set APIFY_TOKEN in the environment."
                )
        from apify_client import ApifyClient
        client = ApifyClient(token)

    run_id, retrieved_dataset_id, config, items = collect(
        client, query, max_posts, recent, start_date, end_date, dataset_id, run_id
    )
    current_post_ids = list(dict.fromkeys(str(item["post_id"]) for item in items if item.get("post_id")))
    with sqlite3.connect(output_dir / "collector.sqlite3") as db:
        db.row_factory = sqlite3.Row
        initialize(db)
        warnings = save_results(db, run_id, retrieved_dataset_id, config, query, items)
        # Export every post accumulated in the database, across earlier runs.
        all_post_ids = [row[0] for row in db.execute(
            "SELECT post_id FROM posts WHERE platform=? ORDER BY date_posted, post_id",
            (PLATFORM,),
        )]
        downloaded, failures = ensure_media(db, output_dir, all_post_ids, video_quality)
        if failures:
            raise RuntimeError("Media download failed; output was not completed:\n" + "\n".join(failures))
        row_count = sync_sqlite_content(db, output_dir, all_post_ids, video_quality)
        csv_path = None
        if output_format == "both":
            csv_path, _ = export_csv(db, output_dir, all_post_ids, video_quality)
    db_path = output_dir / "collector.sqlite3"
    return {"sqlite": str(db_path), "csv": str(csv_path) if csv_path else None,
            "posts_in_this_run": len(current_post_ids),
            "total_posts_in_database": len(all_post_ids), "content_items": row_count,
            "new_downloads": downloaded, "dataset_id": retrieved_dataset_id,
            "database_size_mb": round(db_path.stat().st_size / (1024 ** 2), 2),
            "coverage_warnings": warnings}


def run_ui():
    import streamlit as st

    st.title("Social media collection · proof of concept")
    st.caption("Available platform: Facebook. Collector: danek/facebook-search-ppr.")
    st.info("The Actor lists a five-result limit for free users. Your account, Actor settings, and live pricing may differ. The maximum below is a requested cap, not a platform request quota.")
    with st.form("collection"):
        token = st.text_input("Apify API token", type="password",
                              help="Used for this run; the script does not store it in SQLite.")
        st.selectbox("Platform", ["Facebook"])
        query = st.text_input("Search terms", "Ukraine")
        max_posts = st.number_input("Maximum posts requested", min_value=1, max_value=1000, value=5)
        recent = st.checkbox("Prefer recent posts", value=True)
        start_date = st.text_input("Start date (optional, YYYY-MM-DD)")
        end_date = st.text_input("End date (optional, YYYY-MM-DD)")
        quality = st.selectbox("Video quality", ["sd", "hd"])
        output_format = st.selectbox("Output", ["sqlite", "both"],
                                     format_func=lambda value: "SQLite (media inside database)" if value == "sqlite" else "SQLite and Base64 CSV")
        dataset_id = st.text_input("Existing Apify dataset ID (optional; avoids a new Actor run)")
        existing_run_id = st.text_input("Existing Apify run ID (optional; avoids a new Actor run)")
        output_dir = st.text_input("Output folder", "icrc_collection")
        submitted = st.form_submit_button("Collect and save content")
    if submitted:
        try:
            from apify_client import ApifyClient
            client = ApifyClient(token) if token else None
            with st.spinner("Collecting and exporting…"):
                result = pipeline(query, int(max_posts), recent, start_date or None,
                                  end_date or None, quality, output_dir,
                                  dataset_id or None, existing_run_id or None,
                                  client=client, output_format=output_format)
            st.success("Completed")
            st.json(result)
            for warning in result["coverage_warnings"]:
                st.warning(warning)
            st.caption("The content_items table contains the media bytes in its content BLOB column.")
            if result["csv"] and Path(result["csv"]).stat().st_size <= 10 * 1024 * 1024:
                st.download_button(
                    "Download CSV",
                    data=Path(result["csv"]).read_bytes(),
                    file_name="posts_with_content.csv",
                    mime="text/csv",
                )
            elif result["csv"]:
                st.caption("The CSV exceeds 10 MB; open it directly from the output folder shown above.")
        except Exception as exc:
            st.error(str(exc))

    db_path = Path(output_dir).expanduser() / "collector.sqlite3"
    if db_path.is_file():
        st.subheader("Preview stored content")
        with sqlite3.connect(db_path) as preview_db:
            try:
                metadata = preview_db.execute("""
                    SELECT id, caption, date_posted, media_type
                    FROM content_items ORDER BY date_posted DESC, id DESC LIMIT 50
                """).fetchall()
            except sqlite3.OperationalError:
                metadata = []
        if metadata:
            selection = st.selectbox(
                "Choose an item",
                options=range(len(metadata)),
                format_func=lambda index: (
                    f"{metadata[index][2]} · {metadata[index][3] or 'text'} · "
                    f"{metadata[index][1][:80]}"
                ),
            )
            if st.button("Show selected item"):
                with sqlite3.connect(db_path) as preview_db:
                    row = preview_db.execute("""
                        SELECT caption, date_posted, media_type, content
                        FROM content_items WHERE id=?
                    """, (metadata[selection][0],)).fetchone()
                st.write(row[0])
                media_type, content = row[2], row[3]
                if media_type and media_type.startswith("image/"):
                    st.image(content)
                elif media_type and media_type.startswith("video/"):
                    st.video(content, format=media_type)


def main():
    # When the entire script is pasted into a notebook cell, __name__ is
    # '__main__', but sys.argv belongs to the Jupyter kernel (including -f).
    # %run changes sys.argv[0] to the script name, so explicit flags still work.
    notebook_cell = Path(sys.argv[0]).name == "ipykernel_launcher.py"
    arguments = [] if notebook_cell else sys.argv[1:]
    if "--ui" in arguments:
        run_ui()
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="Ukraine")
    parser.add_argument("--max-posts", type=int, default=5)
    parser.add_argument("--recent", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--video-quality", choices=["sd", "hd"], default="sd")
    parser.add_argument("--format", choices=["sqlite", "both"], default="sqlite",
                        help="Store media in SQLite; optionally also export the Base64 CSV")
    parser.add_argument("--dataset-id", help="Use an existing Apify dataset; skip the paid Actor run")
    parser.add_argument("--run-id", help="Reuse a completed Apify run; skip starting a new Actor run")
    parser.add_argument("--output-dir", default="icrc_collection")
    args = parser.parse_args(arguments)
    result = pipeline(args.query, args.max_posts, args.recent, args.start_date,
                      args.end_date, args.video_quality, args.output_dir,
                      args.dataset_id, args.run_id, output_format=args.format)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
