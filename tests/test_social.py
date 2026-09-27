from harmwatch import social


def test_facebook_search_item():
    post = social.parse_facebook({
        "post_id": "123", "message": "caption", "timestamp": 1758960000,
        "image": {"uri": "https://scontent.xx.fbcdn.net/v/p.jpg?x=1"},
        "video_files": {"video_sd_file": "https://video.xx.fbcdn.net/v/v.mp4"},
        "author": {"profile_picture": {"uri": "https://scontent.xx.fbcdn.net/avatar.jpg"}},
    })
    assert post.url == "https://www.facebook.com/123" and post.posted_at.startswith("2025-09-27")
    assert ("video", "https://video.xx.fbcdn.net/v/v.mp4") in post.media_urls
    assert ("image", "https://scontent.xx.fbcdn.net/v/p.jpg?x=1") in post.media_urls
    assert all("avatar" not in url for _, url in post.media_urls)


def test_instagram_item():
    post = social.parse_instagram({"id": "1", "shortCode": "abc", "caption": "c", "url": "https://www.instagram.com/p/abc/",
                                   "type": "Video", "videoUrl": "https://scontent.cdninstagram.com/v.mp4",
                                   "displayUrl": "https://scontent.cdninstagram.com/d.jpg", "videoViewCount": 50})
    assert post.media_urls[0] == ("video", "https://scontent.cdninstagram.com/v.mp4") and post.reach == 50


def test_tiktok_item():
    post = social.parse_tiktok({"id": "9", "text": "t", "webVideoUrl": "https://www.tiktok.com/@a/video/9",
                                "createTimeISO": "2026-09-27T10:00:00.000Z", "playCount": 1000,
                                "mediaUrls": ["https://api.apify.com/v2/key-value-stores/s/records/video-9"]})
    assert post.media_urls == [("video", "https://api.apify.com/v2/key-value-stores/s/records/video-9")]


def test_x_item_prefers_best_mp4():
    post = social.parse_x({"id": "7", "text": "t", "url": "https://x.com/a/status/7", "extendedEntities": {"media": [
        {"media_url_https": "https://pbs.twimg.com/thumb.jpg", "video_info": {"variants": [
            {"content_type": "video/mp4", "bitrate": 100, "url": "https://video.twimg.com/low.mp4"},
            {"content_type": "video/mp4", "bitrate": 900, "url": "https://video.twimg.com/high.mp4"},
            {"content_type": "application/x-mpegURL", "url": "https://video.twimg.com/pl.m3u8"}]}}]}})
    assert post.media_urls[0] == ("video", "https://video.twimg.com/high.mp4")


def test_urls_route_to_their_platform():
    assert social.adapter_for_url("https://m.facebook.com/story.php?id=1").platform == "facebook"
    assert social.adapter_for_url("https://twitter.com/a/status/1").platform == "x"
    assert social.adapter_for_url("https://example.org/post") is None


def test_downloads_only_from_platform_cdns(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="host not allowed"):
        social.download_media("https://evil.example/a.jpg", "image", tmp_path)
