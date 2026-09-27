from harmwatch import dedup

LONG = "When we get to their villages their women will learn what it means to resist us"


def test_short_texts_never_group():
    assert dedup.fingerprints("Glory to Ukraine", []) == []


def test_exact_and_near_text_copies_share_a_group(tmp_path):
    conn = dedup.connect(tmp_path / "hw.db")
    group = dedup.new_group(conn)
    dedup.add_fingerprints(conn, group, dedup.fingerprints(LONG, []))

    same = "@someone " + LONG.upper() + "!!! https://t.me/x/1"
    assert dedup.find_group(conn, dedup.fingerprints(same, [])) == group  # same words once normalised
    for near in ("RT @someone: " + LONG, LONG.replace("villages", "village"), LONG + " 🔥🔥 repost everywhere"):
        assert dedup.find_group(conn, dedup.fingerprints(near, [])) == group  # near copies (SimHash)
    import itertools

    from harmwatch.seed import load_samples

    texts = [p["text"] for p in load_samples()]
    for a, b in itertools.combinations(texts, 2):  # the 20 samples are all different posts on the same topic
        fa, fb = dict(dedup.fingerprints(a, [])), dict(dedup.fingerprints(b, []))
        if "text_simhash" in fa and "text_simhash" in fb:
            assert (int(fa["text_simhash"], 16) ^ int(fb["text_simhash"], 16)).bit_count() > dedup.SIMHASH_MAX
    other = "The commission documented new cases and published its report on support services for survivors today"
    assert dedup.find_group(conn, dedup.fingerprints(other, [])) is None


def test_same_media_file_groups_whatever_the_caption(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8 same bytes")
    conn = dedup.connect(tmp_path / "hw.db")
    group = dedup.new_group(conn)
    dedup.add_fingerprints(conn, group, dedup.fingerprints("caption one", [dedup.MediaFile("image", img)]))
    assert dedup.find_group(conn, dedup.fingerprints("a different caption", [dedup.MediaFile("image", img)])) == group


def test_resized_image_is_a_near_copy(tmp_path):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    for i in range(0, 400, 40):
        draw.rectangle([i, (i * 7) % 250, i + 30, (i * 7) % 250 + 40], fill=(i % 255, 80, 160))
    img.save(tmp_path / "a.png")
    img.resize((200, 150)).save(tmp_path / "b.jpg", quality=70)  # re-encoded, smaller: different bytes

    conn = dedup.connect(tmp_path / "hw.db")
    group = dedup.new_group(conn)
    dedup.add_fingerprints(conn, group, dedup.fingerprints("", [dedup.MediaFile("image", tmp_path / "a.png")]))
    assert dedup.find_group(conn, dedup.fingerprints("", [dedup.MediaFile("image", tmp_path / "b.jpg")])) == group
